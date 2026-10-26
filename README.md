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

## Web app and API

Every command is also a JSON API endpoint and a browser form, served by the built-in web app.

```bash
agent-alarm-web --port 8000          # then open http://127.0.0.1:8000
agent-alarm-web keys create --label "first customer"   # prints an API key (stored hashed)
docker build -t agent-alarm . && docker run -p 8000:8000 -e API_KEYS=sk_... -v agent-alarm-data:/data agent-alarm
```

Every API call needs `Authorization: Bearer <key>` once any key exists; a server on a public address refuses to start without one. Calls are rate-limited per key (60/min, `--rate`) and metered: `agent-alarm-web usage` prints calls per key for billing.

Endpoints: `POST /api/watch`, plus `GET /healthz` and `GET /api/spec` (machine-readable field list).
Files are sent as `{"name": ..., "content": ...}`, folders as `{"files": [...]}` or a base64 zip.

## Deploy and sell

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/eliem08/agent-alarm)

`render.yaml` (one click, above) and `fly.toml` (`fly launch --copy-config`) both run the Dockerfile with a persistent `/data` volume and a `/healthz` check.
To sell self-serve, set four variables and point a Stripe webhook at `https://<your-host>/billing/webhook` (events `checkout.session.completed` and `customer.subscription.deleted`):

| Variable | Example |
|---|---|
| `STRIPE_SECRET_KEY` | `sk_live_...` |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` |
| `STRIPE_PRICES` | `team=price_123,business=price_456` |
| `PUBLIC_URL` | `https://agent-alarm.example.com` |

Buyers pick a plan on `/pricing`, pay on Stripe Checkout and see their API key once on the success page. Cancelling the subscription revokes the key. A selling server always requires a key.

## Pricing

Every plan starts with a 14-day free trial. Prices in USD, billed monthly unless noted.

| Plan | Price | Includes |
|---|---|---|
| **Personal** | $7 per month | 1 agent; Home and away modes; Inline blocking |
| **Pro** | $29 per month | 10 agents; Custom thresholds; Alert history |
| **Team** | $149 per month | Unlimited agents; Shared policies; Priority support |

To start a trial or buy a plan, [request access](https://github.com/eliem08/agent-alarm/issues/new?title=Agent%20Alarm%20trial&labels=sales).

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
