"""Read-only MCP tools for inspecting agent runs. No dispatch/write tool is exposed."""
from .main import connect

try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - reported when launched without optional runtime
    raise RuntimeError("Install the agents service dependencies to run its MCP server") from exc

mcp = FastMCP("liveslide-readonly")


@mcp.tool()
def list_recent_runs(limit: int = 20) -> list[dict]:
    """List recent workflow status and alert IDs; does not expose personal data."""
    safe_limit = min(max(int(limit), 1), 100)
    db = connect()
    rows = db.execute("SELECT id, cell_id, risk_p, status, alert_id, created_at FROM runs ORDER BY created_at DESC LIMIT ?",
                      (safe_limit,)).fetchall()
    db.close()
    return [dict(row) for row in rows]


@mcp.tool()
def get_run_status(run_id: str) -> dict:
    """Read one run's status; this tool cannot approve or dispatch it."""
    db = connect()
    row = db.execute("SELECT id, cell_id, risk_p, status, alert_id, created_at, updated_at FROM runs WHERE id=?",
                     (run_id,)).fetchone()
    db.close()
    return dict(row) if row else {"error": "run_not_found"}


if __name__ == "__main__":
    mcp.run()
