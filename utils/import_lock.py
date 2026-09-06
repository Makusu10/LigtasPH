"""Best-effort inter-process lock for the boot-time dataset import (GH #7).

Under multi-worker servers (gunicorn) every worker runs create_app() and
would otherwise parse + upsert the 868-feature file concurrently against one
SQLite file. Non-blocking by design: if the lock cannot be acquired (busy or
unsupported platform), the caller proceeds and logs — the importer is
idempotent, so availability always wins over serialization.
"""
import os


def _lock_path(db_path):
    return (str(db_path or ":memory:") or ":memory:") + ".import.lock"


class import_lock:
    """Non-blocking lock file. Use as ``with import_lock(db_path) as locked:``."""

    def __init__(self, db_path):
        self._path = _lock_path(db_path)
        self._fh = None

    def acquire(self):
        try:
            parent = os.path.dirname(os.path.abspath(self._path))
            os.makedirs(parent, exist_ok=True)
            self._fh = open(self._path, "a+b")  # noqa: PTH123 — lock sentinel
            try:
                import fcntl  # POSIX
            except ImportError:  # Windows
                import msvcrt

                msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except Exception:
            self.release()
            return False

    def release(self):
        try:
            if self._fh is not None:
                try:
                    self._fh.close()
                except Exception:
                    pass
        finally:
            self._fh = None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()
        return False
