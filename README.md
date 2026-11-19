# Liveslide

Liveslide is a Verify-before-Warn landslide early warning capstone for Northeast India. It combines daily rainfall and terrain features, cell-level risk scores, a volunteer report queue, an agent flow that pauses at officer approval, and a control-room dashboard. All alert dispatch is mocked in this build; no public messages are sent.

## Run locally

1. Copy `.env.example` to `.env` and change secrets before use.
2. Install Docker Compose v2, Python 3.11–3.13, Node 20 and (for mobile) Flutter.
3. For local Python development, run `make install-dev`. Then run `make up` and `make seed`.
4. Run `make test` for the API and model checks. Open the API at <http://localhost:8000/docs>, agents at <http://localhost:8100/docs>, and the officer dashboard at <http://localhost:3000>.

Demo accounts all use password `liveslide-dev`:

- `officer@example.test` opens the officer desk for report review, risk cell inspection, and alert approval.
- `volunteer@example.test` opens the community reporting page to submit photo/location reports and review that account's submission history.
- `admin@example.test` opens the admin console for record counts, report/alert inspection, and audit-chain verification.

These accounts and all seeded records are synthetic and for local development only.

The 1 km EPSG:4326 grid is an approximation: latitude spacing is `1 / 111.32` degrees and longitude spacing is computed at the region centre as `1 / (111.32 × cos(latitude))`. Cell area varies slightly; use projected geometry for area calculations. The demo grid uses 30 rows by 30 columns to match the requested synthetic region, so its cell spacing is approximate.


The contracts are initial drafts inferred from the build PDF because the shared contract files were not in the repository. Have the team review `contracts/` before integrating changes.

## Basic workflows

- The officer dashboard signs in against the API, lists score cells, reviews submitted photos, and lets an officer accept/reject reports and alert drafts.
- The frontend routes accounts to separate officer, volunteer, and admin workspaces. Officer-only decisions remain enforced by API role checks.
- Volunteers can upload a photo, add a plain-language place name, attach GPS when permission is available, and see their report history. Place-name-only reports are marked for officer location verification. For offline-first capture, use the Flutter field app described below.
- Admins can inspect the complete report and alert registers and recheck audit integrity; they do not perform officer approvals.
- The officer can start an agent run from a high risk, non-synthetic score. The LangGraph gate either closes a low score or creates a draft; only an officer approval can resume the run. The default `DISPATCH_MODE=mock` appends a local log record, never a public message.
- The Flutter source app signs in as a volunteer, captures a photo and GPS position, stores submissions in a local SQLite outbox, and uploads queued reports on explicit sync. Android emulator API defaults to `10.0.2.2:8000`; set `--dart-define=API_BASE=http://<device-reachable-host>:8000/api/v1` for other devices. Generate platform runners with `flutter create --project-name liveslide_field --platforms android,ios .` from `apps/field` before running it.
- The read-only MCP inspector is available with `docker compose -f infra/docker-compose.yml exec agents python -m liveslide_agents.mcp_tools`; it exposes run listing/status only.

The included demo records are deliberately synthetic. The API will reject them for operational agent runs. Insert properly sourced, non-synthetic scores before using the draft flow. Deploy with TLS and replace every local secret before connecting real users.
