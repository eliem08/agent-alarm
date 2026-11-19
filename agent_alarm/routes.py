"""Hosted endpoint: POST /events. An agent (or its gateway) sends each action before doing it and gets back
whether to block it, with the alerts raised. Uses the same API keys, rate limit and quota as the rest of the API.

Body: one event as a JSON object, or several as JSON lines. Answer: {"block": bool, "alerts": [...]} for one
event, {"results": [...], "block": any} for several.

Configuration (environment of the server):
  ALARM_MODE          home or away (default home)
  ALARM_KNOWN         comma-separated recipients that never count as new
  ALARM_ALLOW_DOMAINS comma-separated upload destinations that never count as exfiltration
  AGENT_ALARM_WEBHOOK https Slack/Discord/other webhook for alerts (sent in the background)
  ALARM_NOTIFY_MIN    lowest severity sent to the webhook (default high)

State (daily spend, uploads, bursts, contacts) is kept in the data folder so a restart does not reset a
budget, and every event with its alerts is appended to the event log that `alerts` reads.
"""

from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone

from .core import MODES, Alarm

STATE_FILE = "agent-alarm-state.json"
LOG_FILE = "agent-alarm-alerts.jsonl"  # the file `alerts --store` is pinned to on the server
MAX_EVENTS = 500
_lock = threading.Lock()


def _csv(name: str) -> list[str]:
    return [x.strip() for x in os.environ.get(name, "").split(",") if x.strip()]


def _notify(alerts: list, blocked: bool):
    url = os.environ.get("AGENT_ALARM_WEBHOOK", "")
    if not url or not alerts:
        return
    from .notify import Notifier, WebhookError

    try:
        n = Notifier(url, os.environ.get("ALARM_NOTIFY_MIN", "high"))
    except (WebhookError, KeyError):
        return

    def send():
        for al in alerts:
            n(al, blocked)

    threading.Thread(target=send, daemon=True).start()  # never make the agent wait on Slack


def _parse(body: bytes) -> list:
    text = body.decode("utf-8", errors="replace").strip()
    if not text:
        raise ValueError("send one event as a JSON object, or several as JSON lines")
    if text.startswith("{") and "\n" not in text:
        return [json.loads(text)]
    events = [json.loads(line) for line in text.splitlines() if line.strip()]
    if len(events) > MAX_EVENTS:
        raise ValueError(f"at most {MAX_EVENTS} events per call")
    return events


def events(handler, body: bytes):
    caller = handler.api_caller("events")
    if caller is None:
        return None
    started = time.monotonic()
    try:
        evs = _parse(body)
    except ValueError as e:
        handler.gate.record(caller, "events", 400, 0)
        return 400, "application/json; charset=utf-8", json.dumps({"error": str(e)}).encode()
    mode = os.environ.get("ALARM_MODE", "home")
    if mode not in MODES:
        mode = "home"
    state_path = handler.data_dir / STATE_FILE
    results, raised = [], []
    with _lock:
        try:
            doc = json.loads(state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            doc = {}
        alarm = Alarm.from_dict(doc, mode, _csv("ALARM_KNOWN"), _csv("ALARM_ALLOW_DOMAINS"))
        received = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with open(handler.data_dir / LOG_FILE, "a", encoding="utf-8") as log:
            for i, ev in enumerate(evs):
                try:
                    d = alarm.check(ev)
                except (ValueError, KeyError, TypeError) as e:
                    results.append({"index": i, "error": f"bad event: {e}", "block": True})  # fail closed
                    continue
                alerts = [al.__dict__ for al in d["alerts"]]
                results.append({"block": d["block"], "alerts": alerts})
                raised.append((d["alerts"], d["block"]))
                log.write(json.dumps({"received": received, "event": ev, "block": d["block"], "alerts": alerts}) + "\n")
        tmp = state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(alarm.to_dict()), encoding="utf-8")
        os.replace(tmp, state_path)
    for alerts, blocked in raised:
        _notify(alerts, blocked)
    handler.gate.record(caller, "events", 200, int((time.monotonic() - started) * 1000))
    out = (
        results[0]
        if len(evs) == 1 and len(results) == 1
        else {
            "results": results,
            "block": any(r["block"] for r in results),
        }
    )
    return 200, "application/json; charset=utf-8", json.dumps(out).encode()


ROUTES = {"/events": events}
