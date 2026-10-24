# agent-alarm

[![CI](https://github.com/eliem08/agent-alarm/actions/workflows/ci.yml/badge.svg)](https://github.com/eliem08/agent-alarm/actions/workflows/ci.yml)

> **ADT for your personal agent** — alerts when your agent does something it shouldn't.

Your agent has your inbox, your card and your files. Most of the time it's
fine. `agent-alarm` is the home-security system for the times it isn't:
it watches the agent's action stream and sounds the alarm on spending
spikes, emails to strangers, destructive commands, data leaving the house
and 3 a.m. activity.

## What the MVP does

- **Event stream** (JSONL): `{ts, agent, action, target, amount?, bytes?}`
  — emitted by your agent framework or by agent-tracer
- **Sensors** (rules), each with a severity:
  - `big_spend` single payment over threshold; `spend_velocity` daily total over budget
  - `new_recipient` email/message to a contact never seen before
  - `destructive` deletes, `DROP TABLE`, `rm -rf`, force-push, bulk archive
  - `exfiltration` uploads above N MB to a domain not on the allowlist
  - `sensitive_access` touching `.ssh`, password vaults, tax/medical folders
  - `off_hours` activity in quiet hours; `burst` > N actions/minute
- **Arming modes**: `home` (normal thresholds) and `away` (owner unreachable —
  stricter: lower thresholds, every payment alerts)
- **Responses**: alert, or `block` for critical sensors when used inline (`check()` before acting)
- Baseline learning: known recipients / domains seeded from history

## Quickstart

```bash
pip install -e .
agent-alarm watch examples/events.jsonl --mode away
```

```python
from agent_alarm import Alarm
alarm = Alarm(mode="home", known_recipients={"boss@acme.com"})
decision = alarm.check({"ts": "...", "agent": "inbox-bot", "action": "send_email", "target": "wire@unknown.biz"})
if decision["block"]: ...
```

## Roadmap

- Push / SMS alerts with one-tap "pause agent" (pairs with agent-okta revoke)
- Learned per-agent baselines instead of static thresholds
- Monitoring centre: human reviewers for high-severity alerts (subscription)

## Development

Zero runtime dependencies; Python 3.10+.

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m unittest discover -s tests -t .           # unit + CLI smoke tests
ruff check . && ruff format --check .               # lint + format
```

```
agent_alarm/core.py       domain logic (pure, importable, fully tested)
agent_alarm/__main__.py   CLI (`agent-alarm ...` / `python -m agent_alarm ...`)
tests/                unit tests + generated CLI smoke tests
examples/             sample inputs used by the docs and smoke tests
```

CI runs lint and tests on Ubuntu and Windows across Python 3.10, 3.12 and 3.13.
Design, data model, trade-offs and production path: **[ARCHITECTURE.md](ARCHITECTURE.md)**.

Part of the [agent-economy](https://github.com/eliem08/agent-economy) portfolio (idea #24).
