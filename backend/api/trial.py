"""Free trial builds on Vyskar's own Anthropic key, for people without one.

Off unless FREE_TRIAL_BUILDS is above 0. Then:
- each person gets FREE_TRIAL_BUILDS builds; a person is the browser's
  random visitor id, and an IP address gets three times that, since offices
  and colleges share one
- all trial builds together stop at FREE_TRIAL_DAILY_CAP a day (UTC)
- databases of trial apps are deleted after TRIAL_DATABASE_HOURS, because
  the free Supabase plan allows only two

Counts are kept in a JSON file next to the workspaces. Fly has no volume
here, so a deploy resets them; the spending limit on the Anthropic account
is the hard cap behind this.
"""

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from api.env import env_int

IP_MULTIPLIER = 3
TRIAL_DATABASE_HOURS = 24


@dataclass(frozen=True)
class TrialConfig:
    builds_per_person: int = 0
    daily_cap: int = 50

    @property
    def enabled(self) -> bool:
        return self.builds_per_person > 0

    @classmethod
    def from_env(cls) -> "TrialConfig":
        return cls(
            builds_per_person=env_int("FREE_TRIAL_BUILDS", 0),
            daily_cap=env_int("FREE_TRIAL_DAILY_CAP", 50),
        )


def _today(now: float) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(now))


class TrialLedger:
    """Who used how many trial builds, and which trial databases exist."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._data = self._load()

    def _load(self) -> dict:
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            data = {}
        data.setdefault("visitors", {})
        data.setdefault("ips", {})
        data.setdefault("days", {})
        data.setdefault("databases", [])
        data.setdefault("bonus", {})  # visitor: extra builds, earned once by feedback
        return data

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data))
        tmp.replace(self.path)

    def builds_left(
        self, config: TrialConfig, visitor: str, ip: str, now: float | None = None
    ) -> int:
        """Trial builds this person may still start now; 0 when off or used up."""
        if not config.enabled or not visitor:
            return 0
        now = time.time() if now is None else now
        with self._lock:
            used = self._data["visitors"].get(visitor, 0)
            by_ip = self._data["ips"].get(ip, 0)
            today = self._data["days"].get(_today(now), 0)
            bonus = self._data["bonus"].get(visitor, 0)
        return max(
            0,
            min(
                config.builds_per_person + bonus - used,
                config.builds_per_person * IP_MULTIPLIER + bonus - by_ip,
                config.daily_cap - today,
            ),
        )

    def bonus_used(self, visitor: str) -> bool:
        with self._lock:
            return visitor in self._data["bonus"]

    def grant_bonus(self, visitor: str, builds: int) -> bool:
        """Extra free builds, once per visitor. False when already given."""
        if not visitor or builds <= 0:
            return False
        with self._lock:
            if visitor in self._data["bonus"]:
                return False
            self._data["bonus"][visitor] = builds
            self._save()
            return True

    def record_build(self, visitor: str, ip: str, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self._lock:
            for table, key in (("visitors", visitor), ("ips", ip), ("days", _today(now))):
                self._data[table][key] = self._data[table].get(key, 0) + 1
            self._save()

    def record_database(self, name: str, now: float | None = None) -> None:
        if not name:
            return
        now = time.time() if now is None else now
        with self._lock:
            self._data["databases"].append({"name": name, "created": now})
            self._save()

    def expired_databases(self, now: float | None = None) -> list[str]:
        now = time.time() if now is None else now
        cutoff = now - TRIAL_DATABASE_HOURS * 3600
        with self._lock:
            return [d["name"] for d in self._data["databases"] if d["created"] <= cutoff]

    def forget_database(self, name: str) -> None:
        with self._lock:
            self._data["databases"] = [d for d in self._data["databases"] if d["name"] != name]
            self._save()


def sweep_databases(ledger: TrialLedger, delete, now: float | None = None) -> list[str]:
    """Delete trial databases older than TRIAL_DATABASE_HOURS. A failed delete
    is kept to try again next time. Returns the names deleted."""
    deleted = []
    for name in ledger.expired_databases(now):
        try:
            delete(name)
        except Exception:
            continue
        ledger.forget_database(name)
        deleted.append(name)
    return deleted
