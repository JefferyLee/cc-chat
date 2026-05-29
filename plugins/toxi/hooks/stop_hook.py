#!/usr/bin/env python3
"""Compatibility shim for already-loaded old Codex Stop hook configs.

Current plugin releases do not register a Stop hook because Codex displays a
generic "Stop hook (completed)" line after every turn. This file stays silent so
older Codex sessions that already loaded a Stop hook command do not fail with a
missing-file error.
"""


def main() -> None:
    return


if __name__ == "__main__":
    main()
