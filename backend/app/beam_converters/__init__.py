"""Converters from simulator files to the canonical beam model (argus.beam-model/1, docs/beam-model-format.md).

They sit outside the hub's core on purpose: the hub reads only the canonical representation, and a converter
is a pure function from a file's text to a canonical document — no database, no ledger. The same code can
run in the Accelerator Model Toolbox, a CI job or here, behind `POST /v1/beam-model/convert`, where the
result is shown to a person before anything is imported.

A converter declares a name, the file names it reads and how to recognise its text, and turns text into a
canonical dict. Add one by writing a module in this package that calls `register(...)`:

    from app.beam_converters import Converter, register
    register(Converter(name="bmad", label="Bmad lattice", extensions=(".bmad",),
                       detect=lambda text: "parameter[" in text.lower(), convert=my_convert))

MAD-X (sequence or LINE files, and TFS twiss tables) and Elegant (.lte) are provided.
"""
from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, field
from typing import Callable, Optional


class ConversionError(ValueError):
    """A file a converter cannot read, said in a way a person can act on."""


@dataclass
class Options:
    """What the person can say that a simulator file does not: the model's id and name, the system, the
    topology (`auto` reads it from the bends: a full turn is a ring), the beam, which beam line to use when a
    file defines several, and whether to keep markers and drifts as elements."""
    model_id: Optional[str] = None
    model_name: Optional[str] = None
    version: Optional[str] = None
    system_id: Optional[str] = None
    system_kind: Optional[str] = None
    topology: str = "auto"
    beamline: Optional[str] = None
    species: Optional[str] = None
    reference_energy: Optional[float] = None
    keep_markers: bool = False
    keep_drifts: bool = False
    name_hints: bool = True
    extra: dict = field(default_factory=dict)


@dataclass
class Converter:
    name: str
    label: str
    extensions: tuple
    detect: Callable[[str], bool]
    convert: Callable[[str, str, Options], dict]


_REGISTRY: dict[str, Converter] = {}


def register(converter: Converter) -> None:
    _REGISTRY[converter.name] = converter


def converters() -> list[Converter]:
    _load()
    return sorted(_REGISTRY.values(), key=lambda c: c.name)


def find(filename: str, text: str, name: Optional[str] = None) -> Converter:
    """The converter for a file: the one named, else by extension, else the one that recognises the text."""
    _load()
    if name:
        if name not in _REGISTRY:
            raise ConversionError(f"no converter called {name}; there are {sorted(_REGISTRY)}")
        return _REGISTRY[name]
    lower = (filename or "").lower()
    by_ext = [c for c in _REGISTRY.values() if any(lower.endswith(e) for e in c.extensions)]
    if len(by_ext) == 1:
        return by_ext[0]
    by_text = [c for c in (by_ext or _REGISTRY.values()) if c.detect(text)]
    if len(by_text) == 1:
        return by_text[0]
    raise ConversionError(f"cannot tell which simulator wrote {filename or 'this file'}: choose one of "
                          f"{sorted(_REGISTRY)}")


def convert(filename: str, text: str, options: Optional[Options] = None, name: Optional[str] = None) -> dict:
    conv = find(filename, text, name)
    return conv.convert(text, filename, options or Options())


_LOADED = False


def _load() -> None:
    global _LOADED
    if _LOADED:
        return
    for m in pkgutil.iter_modules(__path__):
        if not m.name.startswith("_") and m.name != "common":
            importlib.import_module(f"{__name__}.{m.name}")
    _LOADED = True
