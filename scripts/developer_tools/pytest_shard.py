"""Opt-in deterministic CI partitioning; every collected node belongs to one shard."""
import hashlib

import pytest


def pytest_addoption(parser):
    group = parser.getgroup("remis-sharding")
    group.addoption("--remis-shard-count", type=int, default=1)
    group.addoption("--remis-shard-index", type=int, default=0)


def pytest_configure(config):
    count = config.getoption("remis_shard_count")
    index = config.getoption("remis_shard_index")
    if count < 1 or not 0 <= index < count:
        raise pytest.UsageError("Require shard count >= 1 and 0 <= index < count")


def pytest_collection_modifyitems(config, items):
    count = config.getoption("remis_shard_count")
    index = config.getoption("remis_shard_index")
    selected, deselected = [], []
    for item in items:
        owner = int.from_bytes(hashlib.sha256(item.nodeid.encode("utf-8")).digest()[:8], "big") % count
        (selected if owner == index else deselected).append(item)
    items[:] = selected
    if deselected:
        config.hook.pytest_deselected(items=deselected)
