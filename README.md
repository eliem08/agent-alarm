# agent-alarm

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
