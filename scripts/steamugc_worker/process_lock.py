"""A Windows named mutex also serializes workers surviving a backend crash."""
import ctypes as c
from contextlib import contextmanager

from binding import SteamFailure


@contextmanager
def publication_lock():
    kernel = c.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateMutexW
    create.argtypes, create.restype = [c.c_void_p, c.c_int, c.c_wchar_p], c.c_void_p
    wait = kernel.WaitForSingleObject
    wait.argtypes, wait.restype = [c.c_void_p, c.c_uint32], c.c_uint32
    release, close = kernel.ReleaseMutex, kernel.CloseHandle
    release.argtypes, release.restype = [c.c_void_p], c.c_int
    close.argtypes, close.restype = [c.c_void_p], c.c_int
    handle = create(None, False, "Local\\RemisSteamUGCPublication")
    if not handle:
        raise SteamFailure("steam_lock_failed")
    acquired = False
    try:
        acquired = wait(handle, 0) in {0, 0x80}
        if not acquired:
            raise SteamFailure("steam_worker_busy")
        yield
    finally:
        if acquired:
            release(handle)
        close(handle)
