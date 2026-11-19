"""Zero-dependency client for a hosted agent-alarm. Check each action before the agent takes it.

    from agent_alarm.client import AgentAlarm, Blocked

    alarm = AgentAlarm("https://alarm.example.com", api_key="sk_...")
    try:
        alarm.require({"agent": "ops-bot", "action": "payment", "target": "acme.com", "amount": 1200})
        pay()
    except Blocked as e:
        log.warning("blocked: %s", e.alerts)

It fails closed: if the alarm cannot be reached or answers unexpectedly, `require` raises instead of allowing,
unless you pass fail_open=True (then a network failure lets the action through and is reported in `.errors`).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone


class Blocked(Exception):
    def __init__(self, alerts: list):
        self.alerts = alerts
        super().__init__("; ".join(f"{a['sensor']}: {a['detail']}" for a in alerts) or "blocked")


class AlarmUnavailable(Exception):
    pass


class AgentAlarm:
    def __init__(self, url: str, api_key: str, timeout: float = 5.0, fail_open: bool = False, opener=None):
        if not url.startswith(("https://", "http://127.0.0.1", "http://localhost")):
            raise ValueError("url must be https:// (plain http only for localhost testing)")
        self.url = url.rstrip("/") + "/events"
        self.key, self.timeout, self.fail_open = api_key, timeout, fail_open
        self.open = opener or urllib.request.urlopen
        self.errors = 0

    def check(self, event: dict) -> dict:
        """Send one event; returns {"block": bool, "alerts": [...]}. Adds a UTC timestamp if missing."""
        ev = {"ts": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds"), **event}
        req = urllib.request.Request(
            self.url,
            data=json.dumps(ev).encode(),
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
        )
        try:
            with self.open(req, timeout=self.timeout) as r:
                res = json.loads(r.read())
            if not isinstance(res, dict) or not isinstance(res.get("block"), bool):
                raise AlarmUnavailable(f"unexpected answer: {res!r:.200}")
            return res
        except (urllib.error.URLError, OSError, ValueError, AlarmUnavailable) as e:
            self.errors += 1
            if self.fail_open:
                return {"block": False, "alerts": [], "error": str(e)}
            raise AlarmUnavailable(f"agent-alarm unreachable or invalid: {e}") from None

    def require(self, event: dict) -> list:
        """Raise Blocked if the alarm blocks the action; otherwise return any lower-severity alerts."""
        res = self.check(event)
        if res["block"]:
            raise Blocked(res.get("alerts", []))
        return res.get("alerts", [])
