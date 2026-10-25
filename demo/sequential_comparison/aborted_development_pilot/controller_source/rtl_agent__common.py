from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCHMARK = ROOT / "benchmarks" / "adder_tree"
STAGES = ("policy", "lint", "interface", "simulation", "equivalence", "synthesis")


def evaluation_code_hashes() -> dict[str, str]:
    names = ("validator.py", "evaluator.py", "pipeline.py", "tool_runner.py", "tool_paths.py", "benchmarks.py")
    return {name: sha256((ROOT / "rtl_agent" / name).read_bytes()) for name in names}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def new_run_dir(command: str, output: str | None = None) -> Path:
    if output:
        path = Path(output).resolve()
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        path = ROOT / "results" / f"{stamp}_{command}"
    path.mkdir(parents=True, exist_ok=False)
    return path


@dataclass(frozen=True)
class Limits:
    per_tool_timeout_seconds: int = 120
    per_run_timeout_seconds: int = 1800
    max_iterations: int = 6
    max_model_requests_per_run: int = 6
    max_completion_tokens: int = 16384
    max_total_tokens: int = 200000
    max_source_bytes: int = 65536
    random_seed: int = 20261021
    random_vectors: int = 4096

    def __post_init__(self):
        for key, value in self.__dict__.items():
            if type(value) is not int or value < 1:
                raise ValueError(f"{key} must be a positive integer")

    @classmethod
    def load(cls):
        return cls(**json.loads((ROOT / "configs" / "default.json").read_text()))
