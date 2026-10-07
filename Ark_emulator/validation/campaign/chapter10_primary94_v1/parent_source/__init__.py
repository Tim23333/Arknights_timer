"""Independent rule-driven simulation substrate."""
from .content.compiler import Compiler, CompileError

__version__ = "2.0.0"


def __getattr__(name):
    if name == "Engine":
        from .adapters.api import Engine
        return Engine
    raise AttributeError(name)


__all__ = ["Compiler", "CompileError", "Engine"]
