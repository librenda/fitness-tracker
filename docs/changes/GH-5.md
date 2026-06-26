# GH-5 — Edit and delete saved run entries

## What shipped

Added edit and delete actions for existing run entries. A new `GET/POST /runs/<id>/edit` route renders a pre-filled form and commits updated field values to SQLite. A new `POST /runs/<id>/delete` route removes the database row and, if the stored photo path falls within the configured upload folder, deletes the file from disk. Both routes return a clean 404 for unknown run IDs. The dashboard table gained an "Actions" column surfacing these operations per row.

## Surface changes

### Endpoints / APIs

**`GET /runs/<int:run_id>/edit`**
Fetches the run row from SQLite; aborts 404 if not found. Renders `edit.html` with all editable fields pre-populated from the row. No auth required.

**`POST /runs/<int:run_id>/edit`**
Accepts form fields `distance`, `duration`, `pace`, `run_at`, `note`, `calories`, `incline`. Updates the row via a parameterized `UPDATE` query using `_float_or_none` / `_int_or_none` helpers (same coercion as the save flow). Redirects to `/dashboard` on success; 404 if the run doesn't exist.

**`POST /runs/<int:run_id>/delete`**
Deletes the `runs` row first, then conditionally removes the photo file using a `realpath` containment check against `UPLOAD_FOLDER`. Redirects to `/dashboard` on success; 404 if the run doesn't exist.

### Components / pages

**`edit.html`** — New standalone page (`app/templates/edit.html`) with a single form matching the confirm-page field layout: `run_at` (datetime-local), `distance`, `duration`, `pace`, `calories`, `incline` (number inputs), and `note` (textarea). All inputs pre-populated from the `run` dict passed by the route. POSTs to the same URL via `method="post"`.

**`dashboard.html`** — Added an "Actions" column (header and per-row cell) to the run table. Each row renders an `<a href="/runs/{{ run.id }}/edit">Edit</a>` link and a minimal `<form>` with a delete button. The delete button carries an `onclick="return confirm(...)"` JS guard before submitting. No additional page or route is required for the confirmation step.

## Behavior & breaking changes

The dashboard table now has an additional "Actions" column; any external test or scraper that asserted a fixed column count will need updating. No other observable behavior changed for existing data or routes.

## How it was verified

| Acceptance criterion | Evidence |
|---|---|
| Each run has Edit and Delete actions on the dashboard | `test_edit_run_updates_row` and `test_delete_run_removes_row_and_file` both POST to the new routes; markup inspection of dashboard response confirmed the "Actions" column renders. |
| Edit opens a pre-filled form and persists to SQLite | `test_edit_run_updates_row` — POSTs updated values; asserts `row["distance"] == 10.0`, `row["note"] == "updated note"`, `row["calories"] == 500`. |
| Delete removes the row and associated photo file | `test_delete_run_removes_row_and_file` — writes a real JPEG to `UPLOAD_FOLDER`, inserts a row pointing to it, POSTs delete; asserts `row is None` and `not os.path.exists(fpath)`. |
| Delete is guarded against files outside the upload folder | Implemented via `os.path.realpath` check (`real_photo.startswith(real_upload + os.sep)`); covered implicitly by the delete test (photo inside folder is removed; a path outside would be skipped). |
| Non-existent run ID returns 404, not 500 | `test_edit_delete_nonexistent_run_returns_404` — asserts `resp_edit.status_code == 404` and `resp_delete.status_code == 404` for ID 99999. |
| Tests cover edit updates row and delete removes row+file | `test_edit_run_updates_row`, `test_delete_run_removes_row_and_file` — both use `_insert_run()` helper against the SQLite test fixture. |
| `uv run pytest -q` is green | 13 passed in 0.10s (reported by test stage). |

## Review notes

- `edit.html` duplicates the field layout from `confirm.html` rather than extracting a shared Jinja2 partial. This is a known non-blocking issue; a future cleanup could unify them.
- Dashboard action links use hardcoded URL strings (`/runs/{{ run.id }}/edit`) rather than `url_for`. Safe under the current single-blueprint layout, but worth migrating if the app prefix ever changes.
- The delete route removes the photo file **after** committing the row deletion. If `os.remove` raises an unexpected error the row is already gone; the file would remain orphaned. Acceptable for a single-user app with no rollback requirement.

## File map

```
app/routes.py            — Added edit_run (GET/POST) and delete_run (POST) route handlers
app/templates/edit.html  — New edit form template pre-filled from run row
app/templates/dashboard.html — Added Actions column with Edit link and Delete form per row
tests/test_app.py        — Added _insert_run helper and three new test functions
```
