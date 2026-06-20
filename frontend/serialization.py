"""JSON (de)serialization for sPot domain objects.

This replaces ``pickle`` for everything stored in Redis. ``pickle.loads`` on data
read from Redis is a remote-code-execution vector if Redis is ever reachable by an
attacker; JSON has no such risk and is also forward/backward compatible across code
changes (a renamed attribute degrades gracefully instead of crashing).

Domain classes opt in with the ``@register`` decorator and must expose ``__slots__``.
Objects are encoded as a small dict carrying a ``__type__`` tag plus their slot
values; lists, dicts, ``None`` and JSON primitives pass through recursively.

Stdlib-only and side-effect-free, so it is safe to import anywhere (including tests).
"""
from __future__ import annotations

import json
from typing import Any

# name -> class, populated by the @register decorator
_REGISTRY: dict[str, type] = {}


def register(cls: type) -> type:
    """Class decorator: make ``cls`` serializable. Returns the class unchanged."""
    _REGISTRY[cls.__name__] = cls
    return cls


def _slots_of(cls: type) -> list[str]:
    slots: list[str] = []
    for klass in cls.__mro__:
        for name in getattr(klass, "__slots__", ()):
            if name not in slots:
                slots.append(name)
    return slots


def _encode(obj: Any) -> Any:
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_encode(x) for x in obj]
    name = type(obj).__name__
    if name in _REGISTRY:
        encoded: dict[str, Any] = {"__type__": name}
        for slot in _slots_of(type(obj)):
            encoded[slot] = _encode(getattr(obj, slot, None))
        return encoded
    if isinstance(obj, dict):
        return {k: _encode(v) for k, v in obj.items()}
    raise TypeError("serialization: unsupported type %r" % name)


def _construct(cls: type, fields: dict[str, Any]) -> Any:
    # Build without calling __init__ so we don't depend on its signature; works
    # fine with __slots__.
    obj = cls.__new__(cls)  # type: ignore[call-overload]
    for key, value in fields.items():
        setattr(obj, key, value)
    return obj


def _decode(data: Any) -> Any:
    if isinstance(data, list):
        return [_decode(x) for x in data]
    if isinstance(data, dict):
        type_name = data.get("__type__")
        if type_name is not None:
            cls = _REGISTRY.get(type_name)
            if cls is None:
                raise TypeError("serialization: unknown type %r" % type_name)
            fields = {k: _decode(v) for k, v in data.items() if k != "__type__"}
            return _construct(cls, fields)
        return {k: _decode(v) for k, v in data.items()}
    return data


def dumps(obj: Any) -> str:
    """Serialize ``obj`` (a registered object, list, dict, or primitive) to a JSON str."""
    return json.dumps(_encode(obj))


def loads(raw: str | bytes | bytearray | None) -> Any:
    """Deserialize what ``dumps`` produced. Accepts str/bytes/None; ``None`` -> ``None``."""
    if raw is None:
        return None
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    return _decode(json.loads(raw))
