Fresh greenfield repo — only `prd.json`, `state.json`, `.claude/settings.json`, and the observability scaffold exist. No source, no manifest, no `progress.txt`, no `skills/`. This is iteration 1 (no prior failure). Here is the plan.

## Context

Greenfield personal app: Flask + SQLite, uv-managed (acceptance requires `uv run pytest -q`). No existing source to match, so I set conventions: the standard Flask **application-factory** pattern (`create_app`) so tests can inject a temp DB and uploads dir without a live server. Three concerns must be isolatable for testing: the Claude vision call (mocked in tests — no key/network), EXIF reading (Pillow), and SQLite access. Vision uses the Anthropic Python SDK, model `claude-sonnet-4-6` (configurable via app config / `MODEL` env). The Anthropic client must be constructed **lazily inside** the call function, never at import, or tests/import-time break without `ANTHROPIC_API_KEY`. This ticket is the upload slice only — no dashboard, timeline, or edit/delete (those are GH-2+).

## Approach

Use Flask's app-factory + a `runs` blueprint with three routes: `GET /` (home/upload form), `POST /upload` (save photo → extract via Claude + EXIF → render an editable confirmation page, **persist nothing yet**), `POST /save` (read possibly-edited form fields → insert row). This two-step upload→confirm→save flow directly satisfies the "extraction unclear → user corrects before saving" criterion. The Claude call lives in one tiny function `vision.extract_run_stats(path, model)` whose internal `_call_claude_vision` is the only thing touching the SDK/network, so tests monkeypatch `extract_run_stats` and run offline. I rejected doing extraction-and-save in a single route (no chance for the user to correct misreads, and it couples the network call to persistence, making the happy-path test require a real key) and rejected an ORM like SQLAlchemy (overkill for one table; raw `sqlite3` with a `schema.sql` is lighter and matches "SQLite schema" literally).

## Steps

1. Create `pyproject.toml` (project `fitness-tracker`, requires-python >=3.11) with deps `flask`, `anthropic`, `pillow`, and dev/test dep `pytest` — done when `uv run pytest -q` resolves the env and collects 0+ tests without import errors.
2. Create `app/db.py` with `get_db()`/`close_db()` (sqlite3, `row_factory = sqlite3.Row`, path from `app.config["DATABASE"]`) and `init_db(app)` that executes `app/schema.sql` — done when calling `init_db` creates a `runs` table.
3. Create `app/schema.sql` defining `runs`: `id` PK, `photo_path TEXT NOT NULL`, `distance REAL`, `duration REAL`, `pace REAL`, `run_at TEXT`, `note TEXT`, `calories INTEGER`, `incline REAL`, `exif_date_missing INTEGER NOT NULL DEFAULT 0`, `created_at TEXT` — done when every acceptance-criterion field is a column (covers note + EXIF-missing flag + optional calories/incline).
4. Create `app/exif.py` with `read_datetime_original(path) -> datetime | None` using `PIL.Image.getexif()` and tag id `36867` (`DateTimeOriginal`), parsing `"%Y:%m:%d %H:%M:%S"`, returning `None` on absence/parse error — done when it returns a datetime for an EXIF-tagged image and `None` otherwise.
5. Create `app/vision.py`: private `_call_claude_vision(image_bytes, media_type, model)` that lazily builds `anthropic.Anthropic()`, sends a base64 image block + a text prompt asking for JSON `{distance, duration, pace, calories, incline}`, and parses the JSON from the response; public `extract_run_stats(path, model)` reads the file, calls it, and derives `pace = duration/distance` when `pace` is missing but both present — done when the SDK is touched only inside `_call_claude_vision` and `extract_run_stats` returns the dict.
6. Create `app/__init__.py` with `create_app(test_config=None)`: set `DATABASE`, `UPLOAD_FOLDER`, `MODEL` (default `claude-sonnet-4-6` from env), ensure upload dir exists, call `init_db`, register the blueprint, register `close_db` teardown — done when `GET /` returns 200 (criterion 1).
7. Create `app/routes.py` blueprint: `GET /` renders `index.html`; `POST /upload` saves the file with `werkzeug.utils.secure_filename` to `UPLOAD_FOLDER`, calls `extract_run_stats` + `read_datetime_original` (falling back to `datetime.now()` with `exif_date_missing=1` when `None`), renders `confirm.html` with values prefilled and `photo_path` in a hidden field; `POST /save` inserts a `runs` row from form fields and redirects to `/` — done when the upload→confirm→save flow inserts one row and the photo file remains on disk (criteria 3,4,5,6).
8. Create `templates/index.html` (with `<meta name="viewport">` and a form `enctype="multipart/form-data"` containing `<input type="file" accept="image/*" name="photo">`) and `templates/confirm.html` (a `POST /save` form with editable `<input>`s for every extracted field + `note` + the hidden `photo_path`) — done when both render and contain the named fields (criteria 3,5).
9. Create `tests/conftest.py` (app fixture using a `tempfile` DB + temp upload dir via `create_app(test_config=...)`, plus a `client` fixture) and `tests/test_app.py`: (a) `GET /` is 200; (b) `POST /upload` with monkeypatched `app.routes.extract_run_stats` returning a fixed dict renders confirm with the values and does **not** hit the network; (c) `POST /save` inserts a row retrievable from the DB — done when `uv run pytest -q` is green (criteria 7,8).

## Acceptance criteria mapping

- "Flask app skeleton with SQLite database and a home page that renders without error." -> steps 2,6,8; verified by test (a) `GET / == 200`.
- "SQLite schema for a run entry: photo path, distance, duration, pace, run datetime (EXIF), note, optional calories/incline, EXIF-date-missing flag." -> step 3; verified by schema columns + test (c) reads them back.
- "Mobile-friendly upload form (`<input type=\"file\" accept=\"image/*\">`) that saves the photo to local disk." -> steps 7,8; verified by test (b) confirming saved file path + `accept`/viewport present in template.
- "On upload, app calls Claude vision for distance/duration/pace and reads EXIF DateTimeOriginal." -> steps 4,5,7; verified by test (b) (mocked vision invoked) and step-4 EXIF behavior.
- "Confirmation page shows extracted values pre-filled and editable." -> steps 7,8; verified by test (b) asserting prefilled values appear in `confirm.html`.
- "On confirm, entry persisted to SQLite and photo retained on disk." -> step 7; verified by test (c) row exists + uploaded file still present.
- "Claude vision call isolated behind a small function, stubbed/mocked in tests; pytest passes without live key/network." -> steps 5,9; verified by test (b) monkeypatching `extract_run_stats` (lazy client = no key needed at import).
- "`uv run pytest -q` is green." -> steps 1,9; verified by the full suite passing.

## Risks

1. **Anthropic client constructed at import/module load** would make every test and even `GET /` fail without `ANTHROPIC_API_KEY`. Mitigation (already in step 5): build the client *inside* `_call_claude_vision` only; tests patch `extract_run_stats` above it. If a failure trace shows an auth error during collection, move client construction deeper.
2. **EXIF access is inconsistent** across Pillow versions/images (`getexif()` vs legacy `_getexif()`, missing tag). Step 4 must wrap reads in try/except and treat any miss as `None` → fallback path with `exif_date_missing=1`; don't let a malformed EXIF block 500 the upload.
3. **`uv` dependency resolution / offline env**: if `anthropic` or `pillow` can't be added, `uv run pytest` fails at setup. They must be declared in `pyproject.toml` (step 1); since vision is mocked, the suite itself needs no network — if `uv sync` fails, that's the signal, not the tests.

```json
{
  "stage": "plan",
  "ticket_id": "GH-1",
  "outcome": "success",
  "exit_signal": false,
  "summary": "Plan for end-to-end photo upload slice: Flask app-factory + sqlite3 runs table, upload→confirm→save flow, lazy-constructed Claude vision call isolated for mocking, Pillow EXIF with fallback flag, pytest suite. All 8 acceptance criteria mapped.",
  "failure_reason": null,
  "files_changed": 0,
  "suggested_tools": [],
  "system_repair_suggested": false
}
```