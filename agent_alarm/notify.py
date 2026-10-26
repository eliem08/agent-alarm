"""Deliver alerts to Slack, Discord or any HTTPS webhook.

The payload carries both "text" (Slack) and "content" (Discord) plus the structured alert, so one URL
format works everywhere. Because the hosted API passes options straight through, a webhook URL is
untrusted input: only https is allowed, and hosts that resolve to private, loopback, link-local or
reserved addresses are refused (no SSRF into the server's own network).
"""

import ipaddress
import json
import socket
import urllib.parse
import urllib.request

from .core import SEVERITY_RANK, Alert


class WebhookError(ValueError):
    pass


def check_url(url: str, resolve=socket.getaddrinfo) -> str:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise WebhookError("webhook must be an https:// URL")
    try:
        infos = resolve(parts.hostname, parts.port or 443, proto=socket.IPPROTO_TCP)
    except OSError as e:
        raise WebhookError(f"webhook host does not resolve: {parts.hostname}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise WebhookError(f"webhook host {parts.hostname} points at a non-public address")
    return url


def payload(al: Alert, blocked: bool) -> dict:
    line = f"[{al.severity.upper()}] {al.agent}: {al.sensor} - {al.detail}" + (" (BLOCKED)" if blocked else "")
    return {
        "text": line,
        "content": line[:2000],
        "alert": {**al.__dict__, "blocked": blocked},
    }


def _post(url: str, body: dict):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "User-Agent": "agent-alarm"}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        r.read(1024)


class Notifier:
    """Sends alerts at or above `min_severity`; delivery failures are counted, never fatal to the watch."""

    def __init__(self, url: str, min_severity: str = "high", post=_post, resolve=socket.getaddrinfo):
        self.url = check_url(url, resolve)
        self.min = SEVERITY_RANK[min_severity]
        self.post = post
        self.sent = self.failed = 0

    def __call__(self, al: Alert, blocked: bool):
        if SEVERITY_RANK[al.severity] < self.min:
            return
        try:
            self.post(self.url, payload(al, blocked))
            self.sent += 1
        except OSError:
            self.failed += 1
