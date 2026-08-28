"""Process-wide coordination for vanilla reference database mutations."""

from functools import wraps
import threading


REFERENCE_DB_WRITE_LOCK = threading.RLock()


def serialized_reference_write(method):
    @wraps(method)
    def locked(*args, **kwargs):
        with REFERENCE_DB_WRITE_LOCK:
            return method(*args, **kwargs)

    return locked
