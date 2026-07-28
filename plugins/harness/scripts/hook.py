"""Plugin-local hook entrypoint."""

from harness_core.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["hook"]))
