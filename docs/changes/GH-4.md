# GH-4 — Photo timeline view of post-run photos

## What shipped

Adds a `/timeline` page that displays each saved run's post-run photo as a
date-ordered thumbnail list (most recent first), with run date and key stats
(distance, pace) beneath each image. A companion `/photos/<filename>` route
serves files from the upload folder, guarded so only filenames that appear in a
`runs` row are served. Navigation links to the timeline were added to the home
page and dashboard. The feature builds directly on the existing `runs` table and
upload infrastructure from GH-1 with no schema changes.

## Surface changes

### Endpoints / APIs

**`GET /photos/<filename>`** — `app/routes.py`

Queries all `photo_path` values from `runs`, derives the set of allowed
basenames, and calls `send_from_directory(UPLOAD_FOLDER, filename)` only if
`filename` is in that set; otherwise returns 404. The `<filename>` segment uses
Flask's default string converter (no slashes), so sub-path traversal cannot
reach the handler. No auth required (single-user app).

**`GET /timeline`** — `app/routes.py`

Queries `SELECT id, photo_path, run_at, distance, pace, exif_date_missing FROM
runs ORDER BY run_at DESC`, maps each row to a dict adding
`filename = os.path.basename(photo_path)`, and renders `timeline.html`.

### Components / pages

**`app/templates/timeline.html`** (new)

- Empty state: message with link to upload when no runs exist.
- Timeline list: one `<li class="timeline-item">` per run, ordered by `run_at
  DESC` (from the query). Each item has a 120×90 thumbnail `<img>` wrapped in
  an `<a href="{{ url_for('runs.photo', filename=run.filename) }}">` for
  full-size access, with `run.run_at`, `run.distance`, and `run.pace` rendered
  beneath.
- Runs with `exif_date_missing` receive the `.estimated` CSS class (italic/grey)
  and an asterisk on the date.
- Nav links back to home and to `/dashboard`.

**`app/templates/index.html`** (modified)

Added `<a href="/timeline">Photo timeline →</a>` to the top nav line (alongside
the existing dashboard link).

**`app/templates/dashboard.html`** (modified)

Added `<a href="/timeline">Photo timeline</a>` to the dashboard `<nav>` bar.

## How it was verified

| Acceptance criterion | Evidence |
|---|---|
| `/timeline` page linked from home and dashboard, thumbnails in date-ordered list most recent first | `test_timeline_shows_run_photo`: inserts a row with `run_at = "2026-06-20T07:00"`, GETs `/timeline`, asserts 200 and `"abc_run.jpg"` in HTML; ORDER BY run_at DESC in query; nav links verified by template inspection |
| Each item shows run date and key stats (distance, pace) | `test_timeline_shows_run_photo` asserts `"6.2"` (distance) and `"5.6"` (pace) appear in the 200 response |
| Clicking a thumbnail opens the full-size photo | Template wraps `<img>` in `<a href="{{ url_for('runs.photo', filename=…) }}">` pointing to the `/photos/<filename>` route, which `test_photo_route_serves_and_blocks` confirms returns 200 with real file bytes |
| Photos served safely — no path traversal, only files referenced by a `runs` row | `test_photo_route_serves_and_blocks`: GET `/photos/testphoto.jpg` (row present) → 200; GET `/photos/nonexistent.jpg` (no row) → 404; string converter blocks slashes; `send_from_directory` normalises the path |
| Empty state renders cleanly | `test_timeline_empty_state`: GET `/timeline` with no rows returns 200 and `"No photos yet"` in HTML |
| Test asserts `/timeline` returns 200 and references a known saved photo using the SQLite fixture | `test_timeline_shows_run_photo` uses the `app`/`client` fixtures from `conftest.py`, inserts a row with `photo_path = os.path.join(upload_folder, "abc_run.jpg")`, and asserts the basename appears in the rendered HTML |
| `uv run pytest -q` is green | Test stage output: 10 passed in 0.09s |

## Review notes

- The `/photos/<filename>` route re-queries `runs` on every request to rebuild
  the allowed-basename set. For a single-user app with a small table this is
  fine; a future pass could cache the set or switch to a single keyed query.
- Stored `photo_path` values are absolute host paths. The route extracts only
  the basename via `os.path.basename`, which is safe, but if a future migration
  changes the upload folder location the stored paths would need updating. The
  pattern is already established by GH-1.
- Visual appearance was verified by template/markup inspection; Playwright was
  not available this session for browser-level rendering.

## File map

```
app/routes.py                — added GET /photos/<filename> (guarded file serving) and GET /timeline routes
app/templates/timeline.html  — new page: date-ordered thumbnail timeline with empty state
app/templates/index.html     — added "Photo timeline" nav link
app/templates/dashboard.html — added "Photo timeline" nav link to dashboard nav bar
tests/test_app.py            — added test_timeline_empty_state, test_timeline_shows_run_photo, test_photo_route_serves_and_blocks
```
