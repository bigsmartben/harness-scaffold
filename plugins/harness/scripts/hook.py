"""Compatibility wrapper for hosts that require a plugin-local hook script."""

from harness_core.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["hook"]))
