<!-- sell-kit:start -->
# Agent Alarm

[![CI](https://github.com/eliem08/agent-alarm/actions/workflows/ci.yml/badge.svg)](https://github.com/eliem08/agent-alarm/actions/workflows/ci.yml)

> **Alerts when your AI agent does something it should not.**

**Who it's for:** Individuals and teams giving agents access to email, money and files.

**The problem:** Agents act fast and quietly, so a bad purchase, mass delete or data upload is discovered only after the damage is done.

**What you get:** Sensors over every agent action with home and away modes: big spends, new recipients, destructive commands, exfiltration and bursts, with inline blocking.

## Quickstart

Customers receive a release archive with the wheel and the examples. Python 3.10+ and no other dependencies.

```bash
pip install agent_alarm-0.1.0-py3-none-any.whl
agent-alarm watch examples/events.jsonl --mode away
```

## Pricing

Every plan starts with a 14-day free trial. Prices in USD, billed monthly unless noted.

| Plan | Price | Includes |
|---|---|---|
| **Personal** | $7 per month | 1 agent; Home and away modes; Inline blocking |
| **Pro** | $29 per month | 10 agents; Custom thresholds; Alert history |
| **Team** | $149 per month | Unlimited agents; Shared policies; Priority support |

To start a trial or buy a plan, email **sales@YOUR-DOMAIN.com**.

## Licence

Proprietary. Copyright (c) 2026 eliem08. All rights reserved. Use requires a paid plan or an active trial; see [LICENSE](LICENSE).
<!-- sell-kit:end -->

## What it does

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

- Push / SMS alerts with one-tap "pause agent" (pairs with agentwarden revoke)
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
