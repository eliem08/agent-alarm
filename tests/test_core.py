import json
import pathlib
import unittest

from agent_alarm import Alarm

EVENTS = [json.loads(l) for l in (pathlib.Path(__file__).resolve().parent.parent / "examples" / "events.jsonl").read_text().splitlines()]


def ev(action, target, ts="2026-10-24T12:00:00", **kw):
    return {"ts": ts, "agent": "a", "action": action, "target": target, **kw}


class Tests(unittest.TestCase):
    def test_example_stream(self):
        alarm = Alarm("home", known_recipients=["boss@acme.com"])
        for e in EVENTS:
            alarm.evaluate(e)
        sensors = {a.sensor for a in alarm.alerts}
        self.assertTrue({"big_spend", "new_recipient", "destructive", "exfiltration", "sensitive_access", "off_hours"} <= sensors)
        self.assertNotIn("payment_while_away", sensors)

    def test_away_mode_is_stricter(self):
        home, away = Alarm("home"), Alarm("away")
        self.assertEqual(home.evaluate(ev("payment", "shop.com", amount=60)), [])
        self.assertEqual(away.evaluate(ev("payment", "shop.com", amount=60))[0].sensor, "big_spend")

    def test_block_on_critical(self):
        alarm = Alarm("home")
        self.assertTrue(alarm.check(ev("shell", "git push --force origin main"))["block"])
        self.assertFalse(alarm.check(ev("read_file", "notes.txt"))["block"])

    def test_new_recipient_only_once_and_daily_budget(self):
        alarm = Alarm("home")
        self.assertEqual(len(alarm.evaluate(ev("send_email", "x@y.com"))), 1)
        self.assertEqual(alarm.evaluate(ev("send_email", "X@y.com")), [])
        for _ in range(3):
            out = alarm.evaluate(ev("payment", "shop", amount=400))
        self.assertIn("spend_velocity", {a.sensor for a in out})

    def test_burst(self):
        alarm = Alarm("away")
        out = []
        for i in range(12):
            out = alarm.evaluate(ev("read_file", "f", ts=f"2026-10-24T12:00:{i:02d}"))
        self.assertIn("burst", {a.sensor for a in out})


if __name__ == "__main__":
    unittest.main()
