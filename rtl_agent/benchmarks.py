"""Immutable benchmark registry. Models never choose tool commands or ports."""
from dataclasses import dataclass
from pathlib import Path

from .common import ROOT


@dataclass(frozen=True)
class Port:
    name: str
    direction: str
    width: int
    signed: bool


@dataclass(frozen=True)
class Benchmark:
    name: str
    title: str
    description: str
    ports: tuple[Port, ...]
    exhaustive: bool = False

    @property
    def directory(self) -> Path:
        return ROOT / "benchmarks" / self.name

    @property
    def inputs(self) -> tuple[Port, ...]:
        return tuple(port for port in self.ports if port.direction == "input")

    @property
    def output(self) -> Port:
        return next(port for port in self.ports if port.direction == "output")


REGISTRY = {
    "adder_tree": Benchmark("adder_tree", "Signed adder tree", "Exact sum of four signed INT8 inputs.",
                            tuple(Port(name, "input", 8, True) for name in ("a", "b", "c", "d")) +
                            (Port("sum", "output", 10, True),)),
    "requantize": Benchmark("requantize", "INT8 saturation", "Arithmetic shift and signed INT8 saturation.",
                            (Port("x", "input", 16, True), Port("y", "output", 8, True)), True),
    "fp4_product": Benchmark("fp4_product", "FP4 E2M1 product", "Exact scaled-integer product of two E2M1 codes.",
                             (Port("a", "input", 4, False), Port("b", "input", 4, False),
                              Port("product", "output", 9, True)), True),
}


def get_benchmark(name: str = "adder_tree") -> Benchmark:
    try:
        return REGISTRY[name]
    except KeyError:
        raise ValueError(f"Unknown benchmark: {name}") from None


def render_script(name: str, benchmark: Benchmark) -> str:
    if name not in {"inspect.ys", "equivalence.ys", "synth.ys"}:
        raise ValueError("Unknown trusted script")
    return (ROOT / "scripts" / name).read_text().replace("__TOP__", benchmark.name)
