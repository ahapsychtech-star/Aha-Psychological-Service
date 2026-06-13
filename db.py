"""
db.py — PostgreSQL adapter for Aha Psychological Service
Replaces the SQLite3 connection used locally with a psycopg2-backed
connection that behaves identically (row-as-dict, context manager, etc.).
"""
import os
import psycopg2
import psycopg2.extras

# Load .env when running locally
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.getenv('DATABASE_URL', '')


class _DictRow(dict):
    """Makes psycopg2 rows subscriptable by both key and index (like sqlite3.Row)."""
    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class _Cursor:
    """Wraps psycopg2 cursor, adapting SQLite-style ? placeholders to %s."""

    def __init__(self, cur):
        self._cur = cur
        self.lastrowid = None
        self.rowcount = 0

    @staticmethod
    def _adapt(sql):
        """Convert SQLite ? placeholders to PostgreSQL %s."""
        # Also convert INTEGER PRIMARY KEY AUTOINCREMENT -> SERIAL PRIMARY KEY
        sql = sql.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
        # Convert ? to %s
        result = []
        in_str = False
        quote_char = None
        for ch in sql:
            if not in_str and ch in ("'", '"'):
                in_str = True
                quote_char = ch
                result.append(ch)
            elif in_str and ch == quote_char:
                in_str = False
                quote_char = None
                result.append(ch)
            elif not in_str and ch == '?':
                result.append('%s')
            else:
                result.append(ch)
        return ''.join(result)

    def execute(self, sql, params=None):
        adapted = self._adapt(sql)
        self._cur.execute(adapted, params or ())
        self.rowcount = self._cur.rowcount
        return self

    def executemany(self, sql, seq):
        adapted = self._adapt(sql)
        self._cur.executemany(adapted, seq)
        self.rowcount = self._cur.rowcount
        return self

    def fetchone(self):
        row = self._cur.fetchone()
        if row is None:
            return None
        return _DictRow(row)

    def fetchall(self):
        rows = self._cur.fetchall()
        return [_DictRow(r) for r in rows]

    def __iter__(self):
        for row in self._cur:
            yield _DictRow(row)


class _Connection:
    """
    Wraps a psycopg2 connection so it behaves like sqlite3.connect():
      - supports `with get_db() as conn:` (commits on exit)
      - conn.execute(sql, params) works directly
      - conn.cursor() returns a _Cursor
    """

    def __init__(self, conn):
        self._conn = conn

    # -- Context manager --
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()
        self._conn.close()
        return False

    # -- Direct execute (sqlite3 allows conn.execute()) --
    def execute(self, sql, params=None):
        cur = _Cursor(self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor))
        cur.execute(sql, params)
        return cur

    def executemany(self, sql, seq):
        cur = _Cursor(self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor))
        cur.executemany(sql, seq)
        return cur

    def cursor(self):
        return _Cursor(self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor))

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    # -- PRAGMA shim (SQLite-only, ignored on Postgres) --
    # Some helpers call PRAGMA table_info(); we intercept that here.


def connect():
    """Return a _Connection wrapping a fresh psycopg2 connection."""
    if not DATABASE_URL:
        raise RuntimeError(
            'DATABASE_URL environment variable is not set. '
            'Create a .env file or set it in Railway.'
        )
    raw = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    raw.autocommit = False
    return _Connection(raw)
