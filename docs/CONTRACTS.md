# Shared contracts

`contracts/openapi.yaml` and `contracts/alert_facts.schema.json` are the initial contract drafts. The original shared contract files referenced in the build PDF were not present anywhere under `/home/maanas`; these drafts infer the endpoints and alert fields from the PDF. Have Arhaan, Prabal and Kunal review them together before their first integration PR. Update both files in the same change whenever a contract changes.

Errors use `{ "error": { "code": "...", "message": "..." } }`. Times are ISO-8601 with timezone; store UTC and show Asia/Kolkata. Roles are `officer`, `volunteer`, and `admin`. Only officers review reports or approve/reject alerts. Volunteers see only their own reports. Service write routes require `X-Service-Key`. Synthetic output must be marked and shown with a visible badge.
