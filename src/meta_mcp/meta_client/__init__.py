"""Convenience exports for Meta client utilities."""

from __future__ import annotations

from importlib import import_module
from pkgutil import iter_modules
from typing import Any

__all__: list[str] = []


def _export_module(module_name: str) -> None:
    module = import_module(f"{__name__}.{module_name}")
    exports = getattr(module, "__all__", None)
    if exports is None:
        exports = [name for name in dir(module) if not name.startswith("_")]
    for name in exports:
        globals()[name] = getattr(module, name)
    __all__.extend(exports)


for module_info in iter_modules(__path__):  # type: ignore[name-defined]
    if module_info.name.startswith("_"):
        continue
    _export_module(module_info.name)


def __getattr__(name: str) -> Any:  # pragma: no cover - fallback access
    if name in globals():
        return globals()[name]
    raise AttributeError(name)


__all__ = tuple(__all__)
