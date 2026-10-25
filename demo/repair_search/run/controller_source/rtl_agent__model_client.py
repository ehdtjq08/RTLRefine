"""Nebius OpenAI-compatible HTTP API; no simulated success path."""
from __future__ import annotations

import json
import os
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .common import ROOT
from .budget import BudgetError, BudgetLedger
from .model_settings import ModelSettings


class ModelError(RuntimeError):
    pass


def load_local_env(path: Path = ROOT / ".env") -> None:
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or key not in {"NEBIUS_API_KEY", "NEBIUS_BASE_URL", "NEBIUS_MODEL_ID"}:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if value:
            os.environ.setdefault(key, value)


def save_model_id(model_id: str, path: Path = ROOT / ".env") -> None:
    """Persist a catalog-selected ID without printing or truncating credentials."""
    BudgetLedger().rate(model_id)
    lines = path.read_text().splitlines() if path.is_file() else []
    lines = [line for line in lines if line.partition("=")[0].strip() != "NEBIUS_MODEL_ID"]
    lines.append("NEBIUS_MODEL_ID=" + model_id)
    fd, temporary = tempfile.mkstemp(prefix=".env.setup-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as file:
            file.write("\n".join(lines) + "\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class NebiusClient:
    def __init__(self, *, timeout: float = 120, settings: ModelSettings | None = None):
        load_local_env()
        self.api_key = os.environ.get("NEBIUS_API_KEY", "").strip()
        self.model_id = os.environ.get("NEBIUS_MODEL_ID", "").strip()
        self.base_url = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/").rstrip("/") + "/"
        parsed = urllib.parse.urlsplit(self.base_url)
        if (parsed.scheme != "https" or parsed.netloc != "api.tokenfactory.nebius.com"
                or parsed.path != "/v1/" or parsed.query or parsed.fragment):
            raise ModelError("NEBIUS_BASE_URL must be https://api.tokenfactory.nebius.com/v1/")
        if not self.api_key:
            raise ModelError("NEBIUS_API_KEY is missing; configure .env locally")
        self.timeout = timeout
        self.opener = urllib.request.build_opener(_NoRedirect)
        self.inference_requests = 0
        self.last_cost = None
        self.execution_origin = "live_nebius"
        self.settings = settings or ModelSettings.load()

    def redact(self, value):
        if isinstance(value, str):
            return value.replace(self.api_key, "[REDACTED]")
        if isinstance(value, dict):
            return {str(self.redact(k)): self.redact(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.redact(v) for v in value]
        return value

    def _request(self, endpoint: str, payload: dict | None = None) -> dict:
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(self.base_url + endpoint, data=data,
                                         headers={"Authorization": "Bearer " + self.api_key,
                                                  "Content-Type": "application/json"})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                body = response.read(2 * 1024**2 + 1)
                if len(body) > 2 * 1024**2:
                    raise ModelError("Provider response exceeded 2 MiB")
                result = json.loads(body)
                if not isinstance(result, dict):
                    raise ModelError("Provider returned a non-object response")
                return self.redact(result)
        except urllib.error.HTTPError as exc:
            raise ModelError(f"Nebius HTTP {exc.code}; check account, model access, quota, and rate limits") from None
        except urllib.error.URLError as exc:
            import socket
            if isinstance(exc.reason, socket.gaierror):
                raise ModelError("Nebius DNS resolution failed in this execution environment; the API key has not been validated") from None
            raise ModelError("Nebius connection failed or timed out; no automatic retry was made") from None
        except (TimeoutError, OSError):
            raise ModelError("Nebius connection failed or timed out; no automatic retry was made") from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ModelError("Nebius response was not valid JSON") from None

    def list_models(self) -> list[str]:
        result = self._request("models")
        data = result.get("data")
        if not isinstance(data, list):
            raise ModelError("Model listing did not contain a data array")
        return sorted({item["id"] for item in data
                       if isinstance(item, dict) and isinstance(item.get("id"), str)})

    def verify_model(self) -> None:
        if not self.model_id.lower().startswith("nvidia/"):
            raise ModelError("Set NEBIUS_MODEL_ID to an NVIDIA-owned model from the account's /models listing")
        if self.model_id not in self.list_models():
            raise ModelError("Configured NVIDIA model is absent from the account's current model listing")

    def generate(self, messages: list[dict], *, max_tokens: int = 4096) -> dict:
        if not self.model_id.lower().startswith("nvidia/"):
            raise ModelError("A verified NVIDIA model ID is required")
        self.last_cost = None
        try:
            ledger = BudgetLedger()
            reservation = ledger.reserve(self.model_id, max_tokens)
        except (BudgetError, OSError, ValueError) as exc:
            raise ModelError("Request not sent: " + str(exc)) from None
        self.inference_requests += 1
        try:
            payload = {"model": self.model_id, "messages": messages, "max_tokens": max_tokens,
                       "temperature": self.settings.temperature, "top_p": self.settings.top_p,
                       "chat_template_kwargs": {"enable_thinking": self.settings.enable_thinking}}
            if self.settings.json_mode:
                payload["response_format"] = {"type": "json_object"}
            response = self._request("chat/completions", payload)
        except ModelError:
            try:
                self.last_cost = ledger.settle(reservation["request_id"], None)
            except (BudgetError, OSError, ValueError):
                self.last_cost = {"request_id": reservation["request_id"], "state": "uncertain",
                                  "reserved_usd": reservation["reserved_usd"], "estimated_usd": None}
            raise
        try:
            self.last_cost = ledger.settle(reservation["request_id"], response.get("usage"))
        except (BudgetError, OSError, ValueError):
            raise ModelError("Usage could not be settled; conservative budget reservation remains") from None
        return response
