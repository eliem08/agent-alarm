import argparse
import json
import sys

from .core import MODES, Alarm

COLORS = {"low": "", "medium": "", "high": "!", "critical": "!!!"}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="agent-alarm")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch")
    w.add_argument("events", help="JSONL file, or - for stdin")
    w.add_argument("--mode", choices=sorted(MODES), default="home")
    w.add_argument("--known", nargs="*", default=["boss@acme.com"])
    w.add_argument("--allow-domain", nargs="*", default=[])
    a = ap.parse_args(argv)
    alarm = Alarm(a.mode, a.known, a.allow_domain)
    fh = sys.stdin if a.events == "-" else open(a.events, encoding="utf-8")
    with fh:
        for line in fh:
            if not line.strip():
                continue
            decision = alarm.check(json.loads(line))
            for al in decision["alerts"]:
                print(f"{COLORS[al.severity]:>3} [{al.severity.upper():<8}] {al.ts} {al.agent:<10} {al.sensor:<18} {al.detail}"
                      + ("  -> BLOCKED" if decision["block"] else ""))
    counts = {}
    for al in alarm.alerts:
        counts[al.severity] = counts.get(al.severity, 0) + 1
    print(f"\n{len(alarm.alerts)} alerts in {a.mode} mode: {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
