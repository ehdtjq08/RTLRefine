"""Recorded inference controls; no unbounded provider parameters."""
import json
import math
from dataclasses import asdict, dataclass

from .common import ROOT


@dataclass(frozen=True)
class ModelSettings:
    temperature: float = 1.0
    top_p: float = 0.95
    enable_thinking: bool = True
    json_mode: bool = True
    api_timeout_seconds: int = 240

    def __post_init__(self):
        if (type(self.temperature) not in (int, float) or not math.isfinite(self.temperature)
                or not 0 < self.temperature <= 2):
            raise ValueError("temperature must be finite and in (0, 2]")
        if type(self.top_p) not in (int, float) or not math.isfinite(self.top_p) or not 0 < self.top_p <= 1:
            raise ValueError("top_p must be finite and in (0, 1]")
        if type(self.enable_thinking) is not bool or type(self.json_mode) is not bool:
            raise ValueError("Thinking and JSON-mode settings must be booleans")
        if type(self.api_timeout_seconds) is not int or not 1 <= self.api_timeout_seconds <= 600:
            raise ValueError("API timeout must be between 1 and 600 seconds")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def load(cls):
        return cls(**json.loads((ROOT / "configs/model.json").read_text()))
