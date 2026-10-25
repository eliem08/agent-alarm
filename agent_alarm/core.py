"""Rule-based alarm system over an agent's action stream."""

from __future__ import annotations

import math
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urlparse

__all__ = ["Alert", "Alarm", "MODES"]

MODES = {
    "home": {"big_spend": 500, "daily_budget": 1000, "upload_mb": 50, "burst_per_min": 30, "quiet": (0, 6)},
    "away": {"big_spend": 50, "daily_budget": 200, "upload_mb": 5, "burst_per_min": 10, "quiet": (22, 8)},
}
DESTRUCTIVE_RE = re.compile(
    r"rm\s+(-\w*r\w*f|-\w*f\w*r|-r\s+-f|-f\s+-r|--recursive)|drop\s+(table|database)|truncate\s+table"
    r"|git\s+push\b[^\n]*(\s-f\b|--force)|delete_all|bulk_delete|format\s+c:|mkfs",
    re.I,
)
DESTRUCTIVE_ACTIONS = {
    "delete_file",
    "delete_email",
    "delete_repo",
    "bulk_archive",
    "cancel_subscription",
    "close_account",
}
SENSITIVE_RE = re.compile(
    r"(\.ssh|id_rsa|id_ed25519|\.aws/credentials|\.env\b|1password|keychain|bitwarden|/tax|/medical|passport)", re.I
)
SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


@dataclass
class Alert:
    sensor: str
    severity: str
    agent: str
    detail: str
    ts: str


def _host(target: str) -> str:
    if "://" in target:
        return (urlparse(target).hostname or "").lower()
    if "@" in target:
        return target.split("@", 1)[1].lower()
    return target.lower()


class Alarm:
    def __init__(self, mode: str = "home", known_recipients=(), allowed_domains=(), block_at: str = "critical"):
        self.mode = mode
        self.known = {r.lower() for r in known_recipients}
        self.allowed = {d.lower() for d in allowed_domains}
        self.block_at = block_at
        self.daily = defaultdict(float)
        self.uploaded = defaultdict(float)  # (agent, host, day) -> MB, so many small uploads still add up
        self.recent = defaultdict(deque)
        self.alerts: list[Alert] = []

    @property
    def cfg(self):
        return MODES[self.mode]

    def _quiet(self, ts: datetime) -> bool:
        a, b = self.cfg["quiet"]
        return (a <= ts.hour < b) if a < b else (ts.hour >= a or ts.hour < b)

    def evaluate(self, ev: dict) -> list[Alert]:
        if not isinstance(ev, dict):
            raise ValueError(f"each event must be a JSON object, got {ev!r:.60}")
        ts = datetime.fromisoformat(ev["ts"])
        agent, target = ev.get("agent", "?"), str(ev.get("target", ""))
        action = str(ev.get("action", "")).strip().lower()  # "Payment" / "DELETE_FILE" must not dodge a sensor
        out = []

        def alert(sensor, sev, detail):
            out.append(Alert(sensor, sev, agent, detail, ev["ts"]))

        if action in {"payment", "purchase", "transfer"}:
            try:
                amt = float(ev.get("amount", 0))
            except (TypeError, ValueError):
                amt = math.nan
            day = (agent, ts.date())
            if not (math.isfinite(amt) and amt >= 0):
                # nan would slip under every threshold and poison the daily total; negatives would reset it
                alert("invalid_amount", "critical", f"amount {ev.get('amount')!r} to {target}")
                amt = 0.0
            self.daily[day] += amt
            if amt >= self.cfg["big_spend"]:
                alert(
                    "big_spend", "critical" if amt >= 2 * self.cfg["big_spend"] else "high", f"${amt:,.2f} to {target}"
                )
            elif self.mode == "away":
                alert("payment_while_away", "medium", f"${amt:,.2f} to {target}")
            if self.daily[day] > self.cfg["daily_budget"]:
                alert("spend_velocity", "high", f"${self.daily[day]:,.2f} today exceeds ${self.cfg['daily_budget']:,}")
        if action in {"send_email", "send_message", "share"} and target.lower() not in self.known:
            alert("new_recipient", "high" if self.mode == "away" else "medium", f"first contact with {target}")
            self.known.add(target.lower())
        if action in DESTRUCTIVE_ACTIONS or DESTRUCTIVE_RE.search(target):
            alert("destructive", "critical", f"{action}: {target}")
        if action in {"upload", "http_post", "share_file"}:
            try:
                mb = float(ev.get("bytes", 0)) / 1e6
            except (TypeError, ValueError):
                mb = math.inf
            mb = mb if math.isfinite(mb) and mb >= 0 else math.inf  # unparseable size: assume the worst
            host = _host(target)
            if host not in self.allowed:
                key = (agent, host, ts.date())
                self.uploaded[key] += mb
                if mb >= self.cfg["upload_mb"]:
                    alert("exfiltration", "critical", f"{mb:.1f} MB to {host}")
                elif self.uploaded[key] >= self.cfg["upload_mb"]:
                    alert("exfiltration", "critical", f"{self.uploaded[key]:.1f} MB to {host} today in small uploads")
        if SENSITIVE_RE.search(target):
            alert("sensitive_access", "high", f"{action} {target}")
        if self._quiet(ts):
            alert("off_hours", "low" if self.mode == "home" else "medium", f"{action} at {ts:%H:%M}")
        q = self.recent[agent]
        q.append(ts)
        while q and ts - q[0] > timedelta(minutes=1):
            q.popleft()
        if len(q) > self.cfg["burst_per_min"]:
            alert("burst", "medium", f"{len(q)} actions in the last minute")

        self.alerts.extend(out)
        return out

    def check(self, ev: dict) -> dict:
        alerts = self.evaluate(ev)
        worst = max((SEVERITY_RANK[a.severity] for a in alerts), default=0)
        return {"block": worst >= SEVERITY_RANK[self.block_at], "alerts": alerts}
