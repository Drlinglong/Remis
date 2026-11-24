"""Serialize complete operations on an ArchiveManager's shared connection.

Raw connection access is internal: bridges must use this boundary too. The
reentrant lock also covers nested lookups, initialization, migrations and close.
"""
from functools import wraps


def archive_operation(operation):
    @wraps(operation)
    def serialized(manager, *args, **kwargs):
        with manager._operation_lock:
            return operation(manager, *args, **kwargs)
    return serialized
