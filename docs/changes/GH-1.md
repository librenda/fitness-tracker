# GH-1 — End-to-end photo upload slice

## What shipped

This ticket delivers the full end-to-end slice for logging a treadmill run from
a phone photo. A Flask application is created from scratch with a SQLite
database, a mobile-friendly upload form, Claude vision extraction behind an
isolatable function, EXIF datetime reading with a missing-date flag, an editable
confirmation page, and a save step that persists the row and retains the photo
on disk.

---

## Surface changes

### Endpoints / APIs

| Method | Path | What it does |
|--------|------|--------------|
| `GET` | `/` | Renders the upload form (`index.html`). No auth. |
| `POST` | `/upload` | Receives the multipart photo, saves it to `instance/uploads/<uuid>_<filename>`, calls `extract_run_stats()` for vision extraction, reads EXIF `DateTimeOriginal`, and renders `confirm.html` pre-filled. |
| `POST` | `/save` | Accepts the (possibly user-edited) confirm form, inserts one row into `runs`, and redirects to `/`. |

### Schemas & data

**`runs` table** (`app/schema.sql`):

| Column | Type | Notes |
|--------|------|-------|
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | |
| `photo_path` | `TEXT NOT NULL` | Absolute path on disk |
| `distance` | `REAL` | km or miles, nullable |
| `duration` | `REAL` | minutes, nullable |
| `pace` | `REAL` | min/unit, nullable; derived in vision layer when absent |
| `run_at` | `TEXT` | ISO-8601 datetime string from EXIF or upload time |
| `note` | `TEXT` | Free-text "how the run felt", nullable |
| `calories` | `INTEGER` | Optional, nullable |
| `incline` | `REAL` | Optional, nullable |
| `exif_date_missing` | `INTEGER NOT NULL DEFAULT 0` | 1 when EXIF was absent and upload time was used |
| `created_at` | `TEXT NOT NULL DEFAULT (datetime('now'))` | Row insertion time |

### Components / pages

**`app/templates/index.html`** — Home page. Contains a single `<form>` with
`<input type="file" accept="image/*" capture="environment">` for mobile camera
access. Submits `multipart/form-data` to `POST /upload`.

**`app/templates/confirm.html`** — Confirmation page. Pre-fills all extracted
values (distance, duration, pace, calories, incline, run datetime) as editable
`<input>` fields. Carries `photo_path` and `exif_date_missing` as hidden fields.
Renders a yellow warning banner when `exif_date_missing` is truthy.
Submits to `POST /save`.

---

## Behavior & breaking changes

This is a net-new application; there are no prior callers. Notable behavioral
decisions:

- **EXIF sub-IFD lookup.** `exif.py` reads tag `36867` (DateTimeOriginal) from
  the Exif sub-IFD (`0x8769`) via Pillow's `get_ifd()`. It falls back to IFD0
  tag `306` before treating the date as missing. A naive top-level `exif.get()`
  call fails for many real-world JPEGs because `DateTimeOriginal` lives in the
  sub-IFD, not IFD0 directly.

- **UUID-prefixed upload filenames.** Saved as `<uuid4_hex>_<secure_filename>`
  to prevent collisions when the same filename is uploaded twice.

- **Pace derivation.** When Claude returns distance and duration but no pace,
  `vision.py` computes `pace = duration / distance`, guarding against
  `ZeroDivisionError`.

---

## How it was verified

| Acceptance criterion | Test evidence |
|----------------------|---------------|
| Flask app skeleton + home page renders without error | `test_home_returns_200` — `GET /` → HTTP 200, response contains `<input` |
| SQLite schema (all required columns) | `test_save_inserts_row` — `SELECT *` after `/save` asserts `row["distance"]` and `row["note"]` are present; schema created by `init_db` during fixture setup |
| Mobile-friendly upload form | `test_home_returns_200` asserts `<input` in body; `index.html` contains `accept="image/*" capture="environment"` (verified by diff) |
| Claude vision extracted on upload | `test_upload_mocked_vision` — monkeypatches `extract_run_stats` to `_FAKE_STATS`; confirm page contains `5.0`, `30.0`, `300` |
| Confirmation page pre-filled and editable | `test_upload_mocked_vision` — asserts extracted values appear in response HTML and `photo_path` hidden field is present |
| `/save` persists row and retains photo | `test_save_inserts_row` — asserts row exists in DB with `distance == 5.0`, `note == "felt good"`, and `os.path.exists(photo_path)` is true |
| Vision isolated / pytest green without live API key | `test_upload_mocked_vision`, `test_save_inserts_row`, `test_upload_exif_date_not_missing` — all monkeypatch `app.routes.extract_run_stats`; `_call_claude_vision` is never called |
| EXIF DateTimeOriginal read correctly | `test_read_datetime_original_reads_exif_subifd` — builds a synthetic JPEG with `DateTimeOriginal` in the Exif sub-IFD; asserts returned datetime is 2026-06-21 08:30; `test_upload_exif_date_not_missing` posts that JPEG via `/upload` and asserts `exif_date_missing` hidden field is `0` |

All 5 tests passed (`uv run pytest -q`, 0.04 s).

---

## Review notes

- **Unit key ambiguity.** The Claude prompt asks for distance in "km or miles"
  and pace in "min/km or min/mile" without enforcing a unit. The schema stores
  raw floats with no unit column. The user can correct values on the confirm
  page, but a future ticket should add explicit unit tracking or lock the prompt
  to one system.

- **No auth.** Single-user, no authentication — by design for this ticket.
  Noted here because `photo_path` is passed through a hidden form field and
  written directly to the DB; a multi-user deployment would need to validate
  ownership.

- **README / architecture docs not updated.** Those files did not exist before
  this ticket. A follow-up should add a `README.md` covering setup (`uv sync`,
  `ANTHROPIC_API_KEY`, `flask run`).

---

## File map

```
app/__init__.py          — Flask application factory; wires DB, uploads dir, blueprint
app/db.py               — SQLite connection helpers (get_db, init_db, close_db)
app/schema.sql          — CREATE TABLE IF NOT EXISTS runs (all columns)
app/exif.py             — read_datetime_original(): Exif sub-IFD lookup with IFD0 fallback
app/vision.py           — extract_run_stats() public entry point; _call_claude_vision() isolated inner call
app/routes.py           — GET /, POST /upload, POST /save endpoints
app/templates/index.html    — Mobile upload form
app/templates/confirm.html  — Editable confirmation page with EXIF-missing warning
pyproject.toml          — Project manifest: flask, anthropic, pillow deps; pytest config
tests/conftest.py       — pytest fixtures: app (in-memory DB) and client
tests/test_app.py       — 5 tests covering all acceptance criteria
```
