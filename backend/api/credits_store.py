"""Paid build credits, kept in SQLite on Fly's volume so they survive deploys.

A visitor (the browser's random id) buys packs of builds. Balance = builds
paid for - builds started. Each payment id is counted once, however often the
browser or the webhook reports it.
"""

import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
create table if not exists orders (
  order_id text primary key, visitor text not null, pack text not null,
  builds integer not null, amount integer not null, created real not null
);
create table if not exists payments (
  payment_id text primary key, order_id text not null references orders,
  visitor text not null, builds integer not null, created real not null
);
create table if not exists uses (
  job_id text primary key, visitor text not null, created real not null
);
"""


class CreditStore:
    def __init__(self, path: Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False, isolation_level=None)
        self._db.execute("pragma journal_mode=wal")
        self._db.executescript(SCHEMA)
        self._lock = threading.Lock()

    def add_order(self, order_id: str, visitor: str, pack: str, builds: int, amount: int) -> None:
        with self._lock:
            self._db.execute(
                "insert into orders values (?, ?, ?, ?, ?, ?)",
                (order_id, visitor, pack, builds, amount, time.time()),
            )

    def order(self, order_id: str) -> dict | None:
        with self._lock:
            row = self._db.execute(
                "select visitor, pack, builds, amount from orders where order_id = ?", (order_id,)
            ).fetchone()
        if row is None:
            return None
        return dict(zip(("visitor", "pack", "builds", "amount"), row, strict=True))

    def record_payment(self, payment_id: str, order_id: str) -> bool:
        """Adds the order's builds to its visitor. False when this payment was
        already counted or the order is unknown."""
        order = self.order(order_id)
        if order is None:
            return False
        with self._lock:
            cursor = self._db.execute(
                "insert or ignore into payments values (?, ?, ?, ?, ?)",
                (payment_id, order_id, order["visitor"], order["builds"], time.time()),
            )
        return cursor.rowcount == 1

    def balance(self, visitor: str) -> int:
        if not visitor:
            return 0
        with self._lock:
            paid = self._db.execute(
                "select coalesce(sum(builds), 0) from payments where visitor = ?", (visitor,)
            ).fetchone()[0]
            used = self._db.execute(
                "select count(*) from uses where visitor = ?", (visitor,)
            ).fetchone()[0]
        return paid - used

    def use(self, visitor: str, job_id: str) -> bool:
        """Spend one build, atomically. False when there is none left."""
        with self._lock:
            self._db.execute("begin immediate")
            try:
                paid = self._db.execute(
                    "select coalesce(sum(builds), 0) from payments where visitor = ?", (visitor,)
                ).fetchone()[0]
                used = self._db.execute(
                    "select count(*) from uses where visitor = ?", (visitor,)
                ).fetchone()[0]
                if paid - used <= 0:
                    self._db.execute("rollback")
                    return False
                self._db.execute(
                    "insert into uses values (?, ?, ?)", (job_id, visitor, time.time())
                )
                self._db.execute("commit")
                return True
            except Exception:
                self._db.execute("rollback")
                raise
