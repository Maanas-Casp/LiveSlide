# Basic agent workflow

The agent service runs a small LangGraph gate. A risk probability below `0.80` closes without an alert draft. A probability at or above `0.80` creates an API alert draft with a 12-hour validity period and English/Hindi starter copy. This mirrors the synthetic demo `WARN` band only; the threshold and language need review before any real pilot.

The workflow pauses at `waiting_for_approval`. An authenticated officer must approve or reject the draft in the dashboard. Rejections stop the run. Approvals resume it once; with `DISPATCH_MODE=mock` the service appends a JSON line to the local dispatch log. Synthetic inputs are allowed only in mock mode and carry a `synthetic: true` fact and dispatch-log flag. Any other mode does not send messages and records that dispatch is disabled.

The MCP server exposes only `list_recent_runs` and `get_run_status`. There is no MCP approval or dispatch tool. Synthetic scores are rejected at the API boundary, and every draft/approval/rejection is recorded in the API's append-only audit chain.
