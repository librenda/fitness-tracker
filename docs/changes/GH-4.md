# GH-4 — Photo timeline view of post-run photos

## What shipped

Added a `/timeline` page that displays post-run photos as a date-ordered grid (most recent first), complementing the numeric dashboard. Each item shows the run's thumbnail, date, distance, and pace; clicking opens the full-size photo. Photos are served through a new `/photos/<filename>` route that allowlists only filenames referenced by a `runs` row, blocking path traversal via Flask's default string converter and a DB-basename check.

## Surface changes

### Endpoints / APIs

**`GET /timeline`**
Queries `runs` ordered `run_at DESC`, attaches `photo_filename = os.path.basename(photo_path)` to each row dict, and renders `timeline.html`. Returns 200. No auth.

**`GET /photos/<filename>`**
Builds an allowlist of `os.path.basename(photo_path)` values for all `runs` rows. If `filename` is not in the allowlist, aborts 404. Otherwise delegates to `send_from_directory(UPLOAD_FOLDER, filename)`. Flask's default `<filename>` string converter rejects `/`, preventing directory traversal via the URL segment. No auth.

### Components / pages

**`app/templates/timeline.html`** (new)
Self-contained HTML page (inline styles, matching project convention). Renders a CSS grid of timeline cards when runs exist, or a "No photos yet" paragraph for the empty state. Each card: thumbnail `<img>` wrapped in an `<a>` to the full-size photo URL; caption with `run_at` date (with `*` marker and `title` tooltip when `exif_date_missing`), distance (km), and pace (min/km). Nav links back to `/` and `/dashboard`.

**`app/templates/index.html`** and **`app/templates/dashboard.html`**
Nav bar extended with a "Photo timeline" link pointing to `/timeline`.

## Behavior & breaking changes

None. All changes are additive. Existing routes (`/`, `/dashboard`, `/upload`, `/save`) are unchanged.

## How it was verified

| Acceptance criterion | Test evidence |
|---|---|
| `/timeline` page linked from home/dashboard shows date-ordered thumbnails | `test_timeline_shows_run_and_photo` — inserts a `runs` row with `run_at="2026-06-22T09:00"` and `ORDER BY run_at DESC` in the query; `GET /timeline` → 200, `fname` in HTML. Nav links verified in template diff. |
| Each item shows run date and key stats (distance, pace) | `test_timeline_shows_run_and_photo` — asserts `"7.2"` (distance) in rendered HTML; pace rendered via same template path. |
| Clicking thumbnail opens full-size photo | `test_photo_serving_guarded` — `GET /photos/guard_test.jpg` (referenced file) → 200. Template wraps `<img>` in `<a href="{{ url_for('runs.photo', ...) }}">`. |
| Photos served safely (no traversal; only DB-referenced files) | `test_photo_serving_guarded` — `GET /photos/not_in_db.jpg` → 404. Flask `<filename>` converter blocks `/` in the segment; allowlist check blocks unreferenced names. |
| Empty state renders cleanly | `test_timeline_empty_state` — `GET /timeline` with empty DB → 200, `"No photos yet"` in HTML. |
| Test asserts `/timeline` 200 and references a known saved photo using SQLite fixture | `test_timeline_shows_run_and_photo` — uses `app`/`client` fixtures, writes real file to `UPLOAD_FOLDER`, inserts row, asserts `fname` in HTML. |
| `uv run pytest -q` is green | Test stage: 10 passed in 0.09 s (7 pre-existing + 3 new). |

## Review notes

- The `/photos/<filename>` allowlist is rebuilt from the DB on every request. For a single-user app with a small `runs` table this is negligible; it would need caching if the table grew large.
- Visual rendering was verified via markup review only — no browser/Playwright check was performed. The reviewer may want to spot-check the grid layout on mobile.
- `prd.json` `status` field updated to `"in_progress"` by the harness; that change is included in the diff but carries no semantic meaning for the merge.

## File map

```
app/routes.py                — added /timeline and /photos/<filename> routes; imported abort, send_from_directory
app/templates/timeline.html  — new template: photo grid with empty state, date+stats caption
app/templates/index.html     — added Photo timeline nav link
app/templates/dashboard.html — added Photo timeline nav link
tests/test_app.py            — 3 new tests: empty state, timeline with run+photo, guarded photo serving
prd.json                     — GH-4 status set to in_progress (harness bookkeeping)
```
