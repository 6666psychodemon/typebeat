"""
Founder CLI for invite requests.

  python -m radio.invite_admin list
  python -m radio.invite_admin list pending
  python -m radio.invite_admin grant user@example.com
  python -m radio.invite_admin deny user@example.com
  python -m radio.invite_admin invites
"""

from __future__ import annotations

import argparse
import json
import sys

from . import auth_db


def _print_rows(rows: list[dict]) -> None:
    if not rows:
        print("(none)")
        return
    for r in rows:
        note = (r.get("note") or "").replace("\n", " ")
        extra = f"  note={note!r}" if note else ""
        print(
            f"{r.get('id'):>4}  {r.get('status'):<8}  {r.get('email')}"
            f"  {r.get('created_at', '')}{extra}"
        )


def main(argv: list[str] | None = None) -> int:
    auth_db.init_db()
    parser = argparse.ArgumentParser(description="TypeBeat radio invite admin")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List invite requests")
    p_list.add_argument(
        "status",
        nargs="?",
        choices=("pending", "invited", "denied"),
        help="Optional status filter",
    )

    p_grant = sub.add_parser("grant", help="Grant invite for an email")
    p_grant.add_argument("email")

    p_deny = sub.add_parser("deny", help="Deny a pending request")
    p_deny.add_argument("email")

    sub.add_parser("invites", help="List granted invites")

    p_json = sub.add_parser("json", help="Dump requests + invites as JSON")
    p_json.add_argument(
        "status",
        nargs="?",
        choices=("pending", "invited", "denied"),
    )

    args = parser.parse_args(argv)

    if args.cmd == "list":
        rows = auth_db.list_invite_requests(args.status)
        _print_rows(rows)
        return 0

    if args.cmd == "grant":
        result = auth_db.grant_invite(args.email)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.cmd == "deny":
        result = auth_db.deny_invite_request(args.email)
        print(json.dumps(result, indent=2))
        return 0 if result.get("ok") else 1

    if args.cmd == "invites":
        rows = auth_db.list_invites()
        _print_rows(rows)
        return 0

    if args.cmd == "json":
        payload = {
            "requests": auth_db.list_invite_requests(args.status),
            "invites": auth_db.list_invites(),
        }
        print(json.dumps(payload, indent=2))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
