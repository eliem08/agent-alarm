import argparse
import contextlib
import csv
import json
import os
import sys

from .core import MODES, Alarm

COLORS = {"low": "", "medium": "", "high": "!", "critical": "!!!"}


def build_parser():
    ap = argparse.ArgumentParser(prog="agent-alarm")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch")
    w.add_argument("events", help="JSONL file, or - for stdin")
    w.add_argument("--mode", choices=sorted(MODES), default="home")
    w.add_argument("--known", nargs="*", default=["boss@acme.com"])
    w.add_argument("--allow-domain", nargs="*", default=[])
    return ap


def _run(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    alarm = Alarm(a.mode, a.known, a.allow_domain)
    with contextlib.ExitStack() as stack:
        fh = sys.stdin if a.events == "-" else stack.enter_context(open(a.events, encoding="utf-8-sig"))
        for line in fh:
            if not line.strip():
                continue
            decision = alarm.check(json.loads(line))
            for al in decision["alerts"]:
                print(
                    f"{COLORS[al.severity]:>3} [{al.severity.upper():<8}] {al.ts} {al.agent:<10} {al.sensor:<18} {al.detail}"
                    + ("  -> BLOCKED" if decision["block"] else "")
                )
    counts = {}
    for al in alarm.alerts:
        counts[al.severity] = counts.get(al.severity, 0) + 1
    print(f"\n{len(alarm.alerts)} alerts in {a.mode} mode: {counts}")
    return 0


def main(argv=None):
    """Run the CLI; a bad input file or argument exits 2 with a one-line error instead of a traceback.

    Set AGENT_ECONOMY_DEBUG=1 to see the full traceback.
    """
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    try:
        return _run(argv)
    except (OSError, ValueError, KeyError, csv.Error) as e:
        if os.environ.get("AGENT_ECONOMY_DEBUG"):
            raise
        msg = e.args[0] if isinstance(e, KeyError) and e.args else e
        print(f"error: {msg}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
