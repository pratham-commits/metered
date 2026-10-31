import os
from contextlib import contextmanager

from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(conninfo=os.environ["DATABASE_URL"], min_size=1, max_size=4)
    return _pool


@contextmanager
def connection():
    with pool().connection() as conn:
        yield conn
        conn.commit()


def ping() -> None:
    with connection() as conn:
        conn.execute("SELECT 1")
