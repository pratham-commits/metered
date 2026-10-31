import hashlib
from bisect import bisect_right


class HashRing:
    def __init__(self, nodes: list[str], vnodes: int = 100):
        if not nodes:
            raise ValueError("ring needs at least one node")
        self.vnodes = vnodes
        self._ring: dict[int, str] = {}
        self._keys: list[int] = []
        for node in nodes:
            self.add(node)

    def _pos(self, key: str) -> int:
        return int(hashlib.md5(key.encode("utf-8")).hexdigest(), 16)

    def add(self, node: str) -> None:
        for i in range(self.vnodes):
            self._ring[self._pos(f"{node}#{i}")] = node
        self._keys = sorted(self._ring)

    def owner(self, key: str) -> str:
        pos = self._pos(key)
        idx = bisect_right(self._keys, pos)
        if idx == len(self._keys):
            idx = 0
        return self._ring[self._keys[idx]]

    def ownership(self, keys: list[str]) -> dict[str, str]:
        return {key: self.owner(key) for key in keys}


def nodes_from_env(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]
