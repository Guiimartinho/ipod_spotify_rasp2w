"""A tiny in-memory stand-in for redis.Redis.

Implements just the subset of the redis-py API that datastore.py uses, so the test
suite needs no running Redis server and no third-party packages. Keys/values behave
like redis-py defaults: keys are returned as bytes, values are stored and returned as
bytes.
"""

import fnmatch


def _to_str(key):
    if isinstance(key, (bytes, bytearray)):
        return key.decode("utf-8")
    return str(key)


def _to_bytes(value):
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if isinstance(value, str):
        return value.encode("utf-8")
    return str(value).encode("utf-8")


class FakeRedis:
    def __init__(self):
        self._store = {}

    def ping(self):
        return True

    def set(self, key, value):
        self._store[_to_str(key)] = _to_bytes(value)
        return True

    def get(self, key):
        return self._store.get(_to_str(key))

    def keys(self, pattern="*"):
        pattern = _to_str(pattern)
        return [k.encode("utf-8") for k in self._store if fnmatch.fnmatch(k, pattern)]

    def scan_iter(self, match=None, **_kwargs):
        pattern = _to_str(match) if match is not None else "*"
        for k in list(self._store.keys()):
            if fnmatch.fnmatch(k, pattern):
                yield k.encode("utf-8")

    def delete(self, *keys):
        removed = 0
        for key in keys:
            if self._store.pop(_to_str(key), None) is not None:
                removed += 1
        return removed

    def flushdb(self):
        self._store.clear()
        return True


class RaisingRedis:
    """A client whose every operation raises, to exercise degraded-mode paths."""

    class _Err(Exception):
        pass

    def _boom(self, *_a, **_k):
        raise RaisingRedis._Err("redis is down")

    ping = set = get = keys = scan_iter = delete = flushdb = _boom
