I have everything I need. Sandbox blocks execution (consistent with prior stages), but the code, the failure diagnosis, and the library versions are clear. Writing the plan.

---

## Context

This is **iteration 2**, a retry. Iteration 1 shipped a working upload→confirm→save slice (7/8 criteria verified, 3 tests green), but the review stage caught a real bug that the test suite masked. The feature touches `app/exif.py` (EXIF datetime read), `app/routes.py` (`/upload` wiring), `app/db.py` (unused import), and `tests/test_app.py` (only exercises the EXIF-less fallback). Constraints: Pillow **12.2.0** is installed (`piexif` is **not**), so any test fixture with embedded EXIF must be built with Pillow only; tests must stay network-free (vision already mocked via `monkeypatch.setattr(routes_module, "extract_run_stats", ...)`). The bug: `app/exif.py:11-12` reads `DateTimeOriginal` (36867) from the top-level/IFD0 dict via `getexif().get(36867)`, but that tag lives in the Exif sub-IFD (pointer `0x8769`), so every real photo falls back to `datetime.now()` and sets `exif_date_missing=1`, breaking acceptance criterion 4.

## Approach

Fix `read_datetime_original` to look in the right place: read tag 36867 from the **Exif sub-IFD** via `getexif().get_ifd(ExifTags.IFD.Exif)`, and if absent fall back to the IFD0 `DateTime` tag (306), then return `None` (the existing upload-time-fallback path in `routes.py` already handles `None` correctly and is still desired when no datetime exists at all). I use Pillow's `ExifTags` symbolic constants rather than magic numbers for readability and to match the "match surrounding code" convention. Then I add a test that builds a JPEG with a genuinely embedded `DateTimeOriginal` (using `Image.Exif()` with `exif[ExifTags.IFD.Exif] = {DateTimeOriginal: "..."}`) and asserts both the unit function and the full `/upload` flow keep `exif_date_missing=0`. I rejected the alternative of writing the date only to the top-level IFD0 `DateTime` tag in the test fixture: that would pass even against the *buggy* code path and so would not prove the fix — the test must exercise the sub-IFD specifically. Secondary cleanups (unused `click` import; duplicate-filename overwrite) are folded in as small, independently-verifiable steps.

## Steps

1. Fix EXIF read in `app/exif.py` — replace the IFD0 lookup with `exif = img.getexif(); raw = exif.get_ifd(ExifTags.IFD.Exif).get(ExifTags.Base.DateTimeOriginal)`, and if falsy fall back to `exif.get(ExifTags.Base.DateTime)` (306, IFD0); parse with the existing `_EXIF_FMT`; keep the `try/except` returning `None`. Add `from PIL import ExifTags`. Done when the function returns the embedded datetime for a sub-IFD photo and still returns `None` for an EXIF-less image.
2. Remove the unused `import click` in `app/db.py:2`. Done when the import is gone and `app/db.py` still imports cleanly (no other reference to `click` in the file).
3. Make on-disk filenames collision-safe in `app/routes.py:32-34` — prefix `secure_filename(photo.filename)` with a short unique token (e.g. `uuid.uuid4().hex[:8] + "_"`), add `import uuid`. Done when two uploads of the same filename produce two distinct files on disk (no overwrite) and the saved `photo_path` still points at the real file.
4. Add an EXIF-bearing test fixture + helper in `tests/test_app.py` — a function that builds an in-memory JPEG with `Image.Exif()`, setting `exif[ExifTags.IFD.Exif] = {ExifTags.Base.DateTimeOriginal: "2024:01:02 03:04:05"}` and saving via `img.save(buf, "JPEG", exif=exif)`. Done when the helper produces bytes that, re-opened, expose 36867 through `get_ifd(ExifTags.IFD.Exif)`.
5. Add `test_read_datetime_original_reads_exif` in `tests/test_app.py` — write the EXIF JPEG from step 4 to `tmp_path`, call `read_datetime_original`, assert it equals `datetime(2024, 1, 2, 3, 4, 5)`. Done when the test passes against the fixed `exif.py` (and would fail against the old IFD0-only code).
6. Add `test_upload_keeps_exif_date` in `tests/test_app.py` — monkeypatch `extract_run_stats` as the other tests do, POST the EXIF JPEG to `/upload`, assert `200` and that the confirm HTML contains `name="exif_date_missing" value="0"` and the `run_at` value `2024-01-02T03:04`. Done when the assertion passes, proving criterion 4 end-to-end.
7. Run `uv run pytest -q`. Done when all tests (the original 3 plus the 2–3 new ones) are green.

## Acceptance criteria mapping

- "Flask app skeleton with a SQLite database and a home page that renders without error." -> unchanged from iter01; verified by `test_home_returns_200`.
- "SQLite schema for a run entry (photo path, distance, duration, pace, run datetime, note, optional calories/incline, exif-missing flag)." -> unchanged; verified by `test_save_inserts_row` reading back the row.
- "Mobile-friendly upload form (`<input type=\"file\" accept=\"image/*\">`)." -> unchanged; verified by `test_home_returns_200` asserting `<input` present (template already has `accept="image/*"` per iter01).
- "On upload, app calls Claude vision and reads EXIF `DateTimeOriginal`." -> steps 1, 6; verified by `test_upload_keeps_exif_date` (EXIF read) + existing `test_upload_mocked_vision` (vision call).
- "Confirmation page shows extracted values pre-filled and editable." -> unchanged; verified by `test_upload_mocked_vision`.
- "On confirm, entry persisted to SQLite and photo retained on disk." -> unchanged (step 3 keeps photo retention intact); verified by `test_save_inserts_row` (`os.path.exists(photo_path)`).
- "Claude vision call isolated behind a small function, stubbed/mocked in tests." -> unchanged; verified by the `monkeypatch.setattr(..., "extract_run_stats", ...)` in upload/save/new tests.
- "`uv run pytest -q` is green." -> step 7; verified by the test-stage run.

## Risks

1. **Pillow sub-IFD write may not round-trip as expected in the test fixture (step 4).** I could not execute Python to confirm (sandbox denies command execution, as it did in review/test stages). If `exif[ExifTags.IFD.Exif] = {...}; img.save(..., exif=exif)` does not persist 36867 on re-open in Pillow 12.2.0, the implementer should (a) confirm by opening the saved bytes and printing `get_ifd(ExifTags.IFD.Exif)`, and if empty, (b) fall back to embedding via the IFD0 `DateTime` tag (`exif[ExifTags.Base.DateTime] = "..."`) **and** ensure step 1's IFD0 fallback reads it — but prefer the sub-IFD path since that is the actual bug being fixed. Do not declare success until a test genuinely fails against the old `getexif().get(36867)` code.
2. **`run_at` string-format assertion in step 6 is brittle.** `routes.py` formats with `strftime("%Y-%m-%dT%H:%M")`, so seconds are dropped → expect `2024-01-02T03:04`, not `...03:04:05`. If the assert fails, check the exact `value="..."` rendered in `confirm.html` rather than loosening the test.
3. **Filename-uniqueness change (step 3) could break the existing `test_save_inserts_row` path-extraction.** That test scrapes `photo_path` from the confirm HTML and re-POSTs it, so it is agnostic to the prefix — but verify the hidden `photo_path` field still carries the full prefixed path after the change.

```json
{
  "stage": "plan",
  "ticket_id": "GH-1",
  "outcome": "success",
  "exit_signal": false,
  "summary": "Retry plan targeting the iter01 review bug: fix EXIF read to use the Exif sub-IFD (0x8769) with IFD0 DateTime fallback, add a real embedded-EXIF test proving exif_date_missing stays 0 through /upload, drop unused click import, and make on-disk filenames collision-safe.",
  "failure_reason": null,
  "files_changed": 0,
  "suggested_tools": [],
  "system_repair_suggested": false
}
```