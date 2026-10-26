import socket
import unittest

from agent_alarm.core import Alert
from agent_alarm.notify import Notifier, WebhookError, check_url, payload


def resolver(ip):
    return lambda host, port, proto=0: [(socket.AF_INET, socket.SOCK_STREAM, proto, "", (ip, port))]


ALERT = Alert("money", "critical", "shopper", "card charge $900", "2026-01-01T03:00:00")


class NotifyTests(unittest.TestCase):
    def test_only_public_https_webhooks_are_accepted(self):
        self.assertTrue(check_url("https://hooks.slack.com/services/x", resolver("34.1.2.3")))
        for url, ip in [
            ("http://hooks.slack.com/x", "34.1.2.3"),
            ("https://internal/x", "10.0.0.5"),
            ("https://localhost/x", "127.0.0.1"),
            ("https://metadata/x", "169.254.169.254"),
            ("https://v6/x", "::1"),
            ("file:///etc/passwd", "34.1.2.3"),
        ]:
            with self.subTest(url=url), self.assertRaises(WebhookError):
                check_url(url, resolver(ip))

    def test_payload_works_for_slack_and_discord(self):
        body = payload(ALERT, blocked=True)
        self.assertIn("CRITICAL", body["text"])
        self.assertIn("BLOCKED", body["content"])
        self.assertEqual(body["alert"]["sensor"], "money")

    def test_threshold_and_failures_never_stop_the_watch(self):
        sent = []
        n = Notifier(
            "https://hooks.example.com/x", "high", post=lambda u, b: sent.append(b), resolve=resolver("34.1.2.3")
        )
        n(Alert("x", "low", "a", "d", "t"), False)
        n(ALERT, False)
        self.assertEqual((len(sent), n.sent), (1, 1))

        def broken(url, body):
            raise OSError("connection refused")

        n.post = broken
        n(ALERT, False)
        self.assertEqual(n.failed, 1)


if __name__ == "__main__":
    unittest.main()
