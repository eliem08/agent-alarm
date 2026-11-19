"""Hosted /events endpoint, persistent totals, the alerts command and the fail-closed client."""

import contextlib
import io
import json
import os
import pathlib
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest import mock

from agent_alarm import routes
from agent_alarm.__main__ import main
from agent_alarm.client import AgentAlarm, AlarmUnavailable, Blocked
from agent_alarm.web import make_server

KEY = "sk_alarm_test"


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = main(list(argv))
    return code, out.getvalue()


def pay(amount, ts="2026-11-18T14:00:00", agent="ops-bot"):
    return {"ts": ts, "agent": agent, "action": "payment", "target": "acme.com", "amount": amount}


class EventsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = pathlib.Path(self.tmp.name)
        self.env = mock.patch.dict(os.environ, {"ALARM_MODE": "home", "AGENT_ALARM_WEBHOOK": ""})
        self.env.start()
        self.start()

    def start(self):
        self.srv = make_server("127.0.0.1", 0, self.data, KEY)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def stop(self):
        self.srv.shutdown()
        self.srv.server_close()

    def tearDown(self):
        self.stop()
        self.env.stop()
        self.tmp.cleanup()

    def post(self, body, key=KEY):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        req = urllib.request.Request(self.url + "/events", data=data, headers={"Authorization": f"Bearer {key}"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            with e:
                return e.code, json.loads(e.read())

    def test_needs_a_key_and_blocks_a_critical_action(self):
        self.assertEqual(self.post(pay(10), key="wrong")[0], 401)
        status, res = self.post(pay(10))
        self.assertEqual((status, res["block"], res["alerts"]), (200, False, []))
        status, res = self.post(pay(1200))  # home mode: 500 is big, 1,000+ is critical
        self.assertTrue(res["block"])
        self.assertEqual(res["alerts"][0]["sensor"], "big_spend")

    def test_daily_budget_survives_a_restart(self):
        for _ in range(2):
            self.assertFalse(self.post(pay(400))[1]["block"])
        self.stop()
        self.start()  # same data folder
        _, res = self.post(pay(400))
        self.assertIn("spend_velocity", [a["sensor"] for a in res["alerts"]])  # 1,200 today > 1,000

    def test_batch_and_bad_events_fail_closed(self):
        lines = "\n".join(json.dumps(e) for e in (pay(5), {"agent": "x"}, pay(2000))).encode()
        status, res = self.post(lines)
        self.assertEqual(status, 200)
        self.assertTrue(res["block"])
        self.assertFalse(res["results"][0]["block"])
        self.assertIn("bad event", res["results"][1]["error"])
        self.assertTrue(res["results"][1]["block"])
        self.assertEqual(self.post(b"   ")[0], 400)

    def test_alerts_are_logged_and_listed(self):
        self.post(pay(1200))
        self.post({"ts": "2026-11-18T14:01:00", "agent": "ops-bot", "action": "delete_repo", "target": "infra"})
        code, out = run("alerts", "--store", str(self.data / routes.LOG_FILE), "--min", "critical")
        self.assertEqual(code, 0)
        self.assertIn("big_spend", out)
        self.assertIn("destructive", out)
        self.assertIn("-> BLOCKED", out)
        _, out = run("alerts", "--store", str(self.data / "missing.jsonl"))
        self.assertIn("0 alert(s)", out)

    def test_webhook_gets_the_alert_without_making_the_agent_wait(self):
        sent = threading.Event()

        class FakeNotifier:
            def __init__(self, url, min_severity):
                self.url = url

            def __call__(self, al, blocked):
                sent.set()

        hook = {"AGENT_ALARM_WEBHOOK": "https://hooks.example.com/x"}
        with mock.patch.dict(os.environ, hook), mock.patch("agent_alarm.notify.Notifier", FakeNotifier):
            self.post(pay(1200))
            self.assertTrue(sent.wait(5))

    def test_client_require_and_fail_closed(self):
        alarm = AgentAlarm(self.url, KEY)
        self.assertEqual(alarm.require(pay(10)), [])
        with self.assertRaises(Blocked) as e:
            alarm.require(pay(5000))
        self.assertIn("big_spend", str(e.exception))
        down = AgentAlarm("http://127.0.0.1:9", KEY, timeout=1)
        with self.assertRaises(AlarmUnavailable):
            down.require(pay(1))
        self.assertEqual(AgentAlarm("http://127.0.0.1:9", KEY, timeout=1, fail_open=True).require(pay(1)), [])
        with self.assertRaises(ValueError):
            AgentAlarm("http://alarm.example.com", KEY)


if __name__ == "__main__":
    unittest.main()
