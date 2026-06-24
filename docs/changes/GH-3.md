# GH-3 — Dashboard: list runs + distance bar chart + pace/duration trends

## What shipped

Adds a read-only `/dashboard` page that lists all saved runs most-recent-first
and renders three Chart.js charts (distance bar, pace line, duration line) from
live `runs` table rows. Empty state is handled with a prompt to log the first
run. Runs with `exif_date_missing = 1` are included in all charts and the table
but are visually flagged (italic row, asterisk on date, orange bar/point). A
link to the dashboard was added to the home page.

## Surface changes

### Endpoints / APIs

**`GET /dashboard`** — `app/routes.py`

Queries `SELECT id, run_at, distance, duration, pace, note, exif_date_missing FROM runs ORDER BY run_at DESC`, serialises the chronologically-sorted subset as a `chart_data` JSON object (keys: `labels`, `distances`, `paces`, `durations`, `estimated`), and renders `dashboard.html`. No auth required (consistent with the rest of the app).

### Components / pages

**`app/templates/dashboard.html`** (new)

- Empty state: plain message with link to upload.
- Run table: all columns from the ticket (date, distance, duration, pace, note); estimated rows styled `.estimated` (italic, grey) with a `*` tooltip on the date cell.
- Distance bar chart (`distanceChart` canvas): Chart.js bar chart, estimated bars rendered orange.
- Pace line chart (`paceChart` canvas): Chart.js line chart; estimated points rendered as orange triangles.
- Duration line chart (`durationChart` canvas): Chart.js line chart; same estimated-point style.
- Chart.js loaded via CDN (`chart.js@4`); no build step.

**`app/templates/index.html`** (modified)

Added one `<p><a href="/dashboard">View dashboard →</a></p>` link above the upload form.

## How it was verified

| Acceptance criterion | Evidence |
|---|---|
| `/dashboard` lists runs most-recent-first, showing date/distance/duration/pace/note | `test_dashboard_shows_run_and_chart`: inserts a row and asserts `"8.5"` and `"morning run"` appear in the response HTML |
| Distance bar chart renders from real rows | Same test asserts `"distanceChart"` in HTML; route serialises `distances` from live DB rows |
| Pace and duration trend charts render from real rows | Same test asserts `"paceChart"` and `"durationChart"` in HTML |
| Empty state handled gracefully | `test_dashboard_empty_state`: asserts status 200 and `"No runs saved yet"` without inserting any rows |
| Estimated-date runs plotted and marked | `estimated` array in `chart_data` drives orange colouring and triangle point-style in the JS; table rows get `.estimated` class |
| Test asserts 200 + chart containers + known run values | `test_dashboard_shows_run_and_chart` asserts all three canvas ids plus `"8.5"` and `"morning run"` |
| `uv run pytest -q` is green | 7/7 passed (test stage output) |

## Review notes

- `chart_data` is injected via `{{ chart_data | safe }}`. The only user-controlled field reaching `labels` is `run_at`, which is stored as an ISO datetime string by the existing save flow. XSS risk is low, but a future hardening pass could escape `</script>` sequences in the serialised JSON.
- Chart.js is loaded from `cdn.jsdelivr.net`. A CSP or offline-first requirement would need a local copy.

## File map

```
app/routes.py              — added GET /dashboard route and chart_data serialisation
app/templates/dashboard.html — new dashboard page with run table and three Chart.js charts
app/templates/index.html   — added "View dashboard" nav link
tests/test_app.py          — added test_dashboard_empty_state and test_dashboard_shows_run_and_chart
```
