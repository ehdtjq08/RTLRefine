"""Cross-process, persistent estimates; reserve before every paid request.

Prices are public quotes, not an account-billing API. Unknown outcomes retain
their conservative reservation, including after a controller crash.
"""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

from .common import ROOT


class BudgetError(RuntimeError):
    pass


def _micro_usd(amount) -> int:
    value = Decimal(str(amount))
    if not value.is_finite() or value < 0:
        raise BudgetError("Budget values must be finite nonnegative USD amounts")
    return int((value * 1_000_000).to_integral_value(rounding=ROUND_CEILING))


def _cost(rate: dict, input_tokens: int, output_tokens: int) -> int:
    # USD / million tokens is numerically micro-USD / token.
    value = (Decimal(rate["input_per_million"]) * input_tokens +
             Decimal(rate["output_per_million"]) * output_tokens)
    return int(value.to_integral_value(rounding=ROUND_CEILING))


class BudgetLedger:
    def __init__(self, path: Path | None = None, *, policy: dict | None = None,
                 pricing: dict | None = None):
        self.path = path or ROOT / ".state" / "spend.json"
        self.policy = policy if policy is not None else json.loads((ROOT / "configs/budget.json").read_text())
        self.pricing = pricing if pricing is not None else json.loads((ROOT / "configs/pricing.json").read_text())
        self.phase = self.policy["default_phase"]
        self.total_cap = _micro_usd(self.policy["total_budget_usd"])
        self.phase_caps = {key: _micro_usd(value) for key, value in self.policy["phase_budgets_usd"].items()}
        if self.phase not in self.phase_caps:
            raise BudgetError("Unknown default budget phase")
        if sum(self.phase_caps.values()) + _micro_usd(self.policy.get("unallocated_safety_buffer_usd", 0)) > self.total_cap:
            raise BudgetError("Budget allocations exceed the total cap")

    def rate(self, model_id: str) -> dict:
        # Model IDs remain case-sensitive, matching the provider catalog.
        value = self.pricing["models"].get(model_id)
        if value is None:
            raise BudgetError("No verified price for this model ID; add its current official rate before inference")
        if (type(value.get("context_tokens")) is not int or value["context_tokens"] <= 0 or
                any(not Decimal(value[key]).is_finite() or Decimal(value[key]) < 0
                    for key in ("input_per_million", "output_per_million"))):
            raise BudgetError("Invalid model pricing configuration")
        return value

    def quote(self, model_id: str, output_tokens: int) -> dict:
        rate = self.rate(model_id)
        if type(output_tokens) is not int or not 1 <= output_tokens <= rate["context_tokens"]:
            raise BudgetError("Output token limit is outside the priced context bound")
        maximum = _cost(rate, rate["context_tokens"], output_tokens)
        return {"model_id": model_id, "phase": self.phase,
                "reserved_usd": maximum / 1_000_000, "reserved_micro_usd": maximum,
                "max_input_tokens": rate["context_tokens"], "max_output_tokens": output_tokens,
                "rate": rate, "pricing_verified_on": rate.get("verified_on", self.pricing.get("verified_on")),
                "pricing_source": rate.get("source", self.pricing.get("source"))}

    @contextmanager
    def _locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(self.path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
        with os.fdopen(fd, "r+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                if self.path.exists():
                    try:
                        ledger = json.loads(self.path.read_text())
                    except (OSError, ValueError) as exc:
                        raise BudgetError("Budget ledger is unreadable; refusing to reset spend history") from exc
                    if (ledger.get("schema") != 1 or not isinstance(ledger.get("entries"), list) or
                            not isinstance(ledger.get("phase_caps"), dict) or
                            type(ledger.get("total_cap")) is not int):
                        raise BudgetError("Unsupported budget ledger; manual review required")
                else:
                    ledger = {"schema": 1, "total_cap": self.total_cap,
                              "phase_caps": self.phase_caps.copy(), "entries": []}
                yield ledger
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _save(self, ledger: dict) -> None:
        fd, temporary = tempfile.mkstemp(prefix=".spend-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as file:
                json.dump(ledger, file, indent=2, sort_keys=True)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @staticmethod
    def _accounted(entry: dict) -> int:
        amount = entry.get("estimated_micro_usd") if entry.get("state") == "settled" else entry.get("reserved_micro_usd")
        if type(amount) is not int or amount < 0:
            raise BudgetError("Corrupt spend entry; refusing inference")
        return amount

    def _summary(self, ledger: dict) -> dict:
        used = sum(self._accounted(item) for item in ledger["entries"])
        phase_used = {phase: sum(self._accounted(item) for item in ledger["entries"] if item["phase"] == phase)
                      for phase in self.phase_caps}
        total_cap = min(self.total_cap, ledger["total_cap"])
        phases = {phase: min(cap, ledger["phase_caps"].get(phase, 0)) for phase, cap in self.phase_caps.items()}
        return {"total_cap_usd": total_cap / 1_000_000, "accounted_usd": used / 1_000_000,
                "remaining_usd": max(0, total_cap - used) / 1_000_000,
                "phase": self.phase, "phase_cap_usd": phases[self.phase] / 1_000_000,
                "phase_accounted_usd": phase_used[self.phase] / 1_000_000,
                "phase_remaining_usd": max(0, phases[self.phase] - phase_used[self.phase]) / 1_000_000,
                "requests": len(ledger["entries"]),
                "unsettled_requests": sum(item["state"] != "settled" for item in ledger["entries"]),
                "pricing_verified_on": self.pricing.get("verified_on")}

    def summary(self) -> dict:
        with self._locked() as ledger:
            return self._summary(ledger)

    def reserve(self, model_id: str, output_tokens: int) -> dict:
        quote = self.quote(model_id, output_tokens)
        with self._locked() as ledger:
            summary = self._summary(ledger)
            amount = quote["reserved_micro_usd"]
            total_used = sum(self._accounted(item) for item in ledger["entries"])
            phase_used = sum(self._accounted(item) for item in ledger["entries"] if item["phase"] == self.phase)
            if (total_used + amount > min(self.total_cap, ledger["total_cap"]) or
                    phase_used + amount > min(self.phase_caps[self.phase], ledger["phase_caps"].get(self.phase, 0))):
                raise BudgetError(f"Budget reservation rejected: ${quote['reserved_usd']:.6f} required; "
                                  f"${summary['phase_remaining_usd']:.6f} remains in {self.phase}")
            entry = {**quote, "request_id": uuid.uuid4().hex, "state": "reserved",
                     "created_at": datetime.now(timezone.utc).isoformat(),
                     "estimated_micro_usd": None, "usage": None}
            ledger["entries"].append(entry)
            self._save(ledger)
            return entry.copy()

    def settle(self, request_id: str, usage) -> dict:
        with self._locked() as ledger:
            entry = next((item for item in ledger["entries"] if item["request_id"] == request_id), None)
            if entry is None:
                raise BudgetError("Unknown budget reservation")
            if entry["state"] == "settled":
                if entry["usage"] != usage:
                    raise BudgetError("A settled request cannot be rewritten")
            else:
                valid = (isinstance(usage, dict) and
                         all(type(usage.get(key)) is int and usage[key] >= 0
                             for key in ("prompt_tokens", "completion_tokens", "total_tokens")) and
                         usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"] and
                         usage["prompt_tokens"] <= entry["max_input_tokens"] and
                         usage["completion_tokens"] <= entry["max_output_tokens"])
                if valid:
                    entry.update(state="settled", usage=usage,
                                 estimated_micro_usd=_cost(entry["rate"], usage["prompt_tokens"], usage["completion_tokens"]))
                else:
                    entry["state"] = "uncertain"
                self._save(ledger)
            return {"request_id": request_id, "state": entry["state"], "phase": entry["phase"],
                    "reserved_usd": entry["reserved_micro_usd"] / 1_000_000,
                    "estimated_usd": (entry["estimated_micro_usd"] / 1_000_000
                                      if entry["estimated_micro_usd"] is not None else None),
                    "pricing_verified_on": entry["pricing_verified_on"]}
