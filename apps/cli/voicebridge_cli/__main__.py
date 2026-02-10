from __future__ import annotations

import argparse
import sys

from voicebridge_cli.export_cmd import export_cmd
from voicebridge_cli.meeting_cmd import meeting_cmd


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="voicebridge", description="VoiceBridge CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_meeting = sub.add_parser("meeting", help="Run Meeting mode (mic)")
    p_meeting.add_argument("--profile", default="Meeting", help="Profile name (default: Meeting)")
    p_meeting.add_argument("--profiles-dir", default=None, help="Override profiles dir (optional)")
    p_meeting.add_argument("--settings", default=None, help="Override settings.yml path (optional)")
    p_meeting.add_argument("--device", default=None, help="Override input device name (optional)")
    p_meeting.set_defaults(func=meeting_cmd)

    p_export = sub.add_parser("export", help="Export a session to Markdown")
    p_export.add_argument("--session", required=True, help="Session id")
    p_export.add_argument("--storage", default=None, help="Storage root (optional)")
    p_export.set_defaults(func=export_cmd)

    args = parser.parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

