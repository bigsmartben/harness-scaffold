from pathlib import Path

guide = Path("docs/operator-guide.md").read_text(encoding="utf-8")
assert "GET /api/v2/status" in guide, "operator guide must use the v2 status endpoint"
assert "GET /api/v1/status" not in guide, "operator guide still contains the obsolete endpoint"
print("docs check passed: operator guide uses /api/v2/status")
