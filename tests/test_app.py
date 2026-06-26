import io
import os
import pytest
from PIL import Image
from app.db import get_db
from app.exif import read_datetime_original


_FAKE_STATS = {
    "distance": 5.0,
    "duration": 30.0,
    "pace": 6.0,
    "calories": 300,
    "incline": 1.0,
}

_TINY_JPEG = (
    b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
    b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
    b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\x1e\xff"
    b"\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f"
    b"\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5"
    b"\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x01"
    b"}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07\"q\x142\x81\x91"
    b"\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&"
    b"'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85\x86\x87\x88"
    b"\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6"
    b"\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4"
    b"\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1"
    b"\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7"
    b"\xf8\xf9\xfa\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xf5\x0e\xff\xd9"
)


_EXIF_DT_STR = "2026:06:21 08:30:00"


def _make_jpeg_with_exif(dt_str=_EXIF_DT_STR) -> bytes:
    img = Image.new("RGB", (1, 1), color=(255, 0, 0))
    exif = img.getexif()
    exif.get_ifd(0x8769)[36867] = dt_str  # DateTimeOriginal in Exif sub-IFD
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


def test_read_datetime_original_reads_exif_subifd(tmp_path):
    jpeg_bytes = _make_jpeg_with_exif()
    path = tmp_path / "exif_run.jpg"
    path.write_bytes(jpeg_bytes)
    dt = read_datetime_original(str(path))
    assert dt is not None
    assert dt.year == 2026 and dt.month == 6 and dt.day == 21
    assert dt.hour == 8 and dt.minute == 30


def test_upload_exif_date_not_missing(client, monkeypatch):
    import app.routes as routes_module

    monkeypatch.setattr(routes_module, "extract_run_stats", lambda path, model: _FAKE_STATS)

    jpeg_bytes = _make_jpeg_with_exif()
    data = {"photo": (io.BytesIO(jpeg_bytes), "exif_run.jpg")}
    resp = client.post("/upload", data=data, content_type="multipart/form-data")

    assert resp.status_code == 200
    html = resp.data.decode()
    # exif_date_missing hidden field must be 0
    assert 'name="exif_date_missing" value="0"' in html


def test_home_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"<input" in resp.data


def test_upload_mocked_vision(client, monkeypatch):
    import app.routes as routes_module

    monkeypatch.setattr(routes_module, "extract_run_stats", lambda path, model: _FAKE_STATS)

    data = {"photo": (io.BytesIO(_TINY_JPEG), "run.jpg")}
    resp = client.post("/upload", data=data, content_type="multipart/form-data")

    assert resp.status_code == 200
    html = resp.data.decode()
    assert "5.0" in html      # distance
    assert "30.0" in html     # duration
    assert "300" in html      # calories
    assert "photo_path" in html  # hidden field present


def test_dashboard_empty_state(client):
    resp = client.get("/dashboard")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Dashboard" in html
    assert "No runs saved yet" in html


def test_dashboard_shows_run_and_chart(app, client):
    with app.app_context():
        from app.db import get_db
        db = get_db()
        db.execute(
            """INSERT INTO runs
               (photo_path, distance, duration, pace, run_at, note,
                calories, incline, exif_date_missing)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("/fake/path.jpg", 8.5, 45.0, 5.3, "2026-06-21T08:30", "morning run",
             400, 0.5, 0),
        )
        db.commit()

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "distanceChart" in html
    assert "paceChart" in html
    assert "durationChart" in html
    assert "8.5" in html
    assert "morning run" in html


def test_timeline_empty_state(client):
    resp = client.get("/timeline")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "No photos yet" in html


def test_timeline_shows_run_and_photo(app, client):
    with app.app_context():
        upload_folder = app.config["UPLOAD_FOLDER"]
        fname = "test_run_photo.jpg"
        fpath = os.path.join(upload_folder, fname)
        with open(fpath, "wb") as f:
            f.write(_TINY_JPEG)
        from app.db import get_db
        db = get_db()
        db.execute(
            """INSERT INTO runs
               (photo_path, distance, duration, pace, run_at, note,
                calories, incline, exif_date_missing)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (fpath, 7.2, 40.0, 5.5, "2026-06-22T09:00", None, 350, 0.0, 0),
        )
        db.commit()

    resp = client.get("/timeline")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert fname in html
    assert "7.2" in html


def test_photo_serving_guarded(app, client):
    with app.app_context():
        upload_folder = app.config["UPLOAD_FOLDER"]
        fname = "guard_test.jpg"
        fpath = os.path.join(upload_folder, fname)
        with open(fpath, "wb") as f:
            f.write(_TINY_JPEG)
        from app.db import get_db
        db = get_db()
        db.execute(
            """INSERT INTO runs
               (photo_path, distance, duration, pace, run_at, note,
                calories, incline, exif_date_missing)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (fpath, 5.0, 30.0, 6.0, "2026-06-23T07:00", None, 300, 0.0, 0),
        )
        db.commit()

    resp_ok = client.get(f"/photos/{fname}")
    assert resp_ok.status_code == 200

    resp_bad = client.get("/photos/not_in_db.jpg")
    assert resp_bad.status_code == 404


def test_save_inserts_row(app, client, monkeypatch, tmp_path):
    import app.routes as routes_module

    monkeypatch.setattr(routes_module, "extract_run_stats", lambda path, model: _FAKE_STATS)

    # First upload to get photo on disk
    data = {"photo": (io.BytesIO(_TINY_JPEG), "run2.jpg")}
    resp = client.post("/upload", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200

    # Find the photo path from the confirm page
    html = resp.data.decode()
    start = html.find('name="photo_path" value="') + len('name="photo_path" value="')
    end = html.find('"', start)
    photo_path = html[start:end]

    # Now POST to /save
    save_data = {
        "photo_path": photo_path,
        "distance": "5.0",
        "duration": "30.0",
        "pace": "6.0",
        "calories": "300",
        "incline": "1.0",
        "run_at": "2026-06-21T08:00",
        "note": "felt good",
        "exif_date_missing": "0",
    }
    resp2 = client.post("/save", data=save_data)
    assert resp2.status_code in (302, 200)

    # Verify the row exists
    with app.app_context():
        row = get_db().execute("SELECT * FROM runs WHERE photo_path = ?", (photo_path,)).fetchone()
    assert row is not None
    assert row["distance"] == 5.0
    assert row["note"] == "felt good"
    # Photo file still on disk
    assert os.path.exists(photo_path)


def _insert_run(app, photo_path):
    with app.app_context():
        db = get_db()
        db.execute(
            """INSERT INTO runs
               (photo_path, distance, duration, pace, run_at, note,
                calories, incline, exif_date_missing)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (photo_path, 5.0, 30.0, 6.0, "2026-06-21T08:00", "original note", 300, 1.0, 0),
        )
        db.commit()
        return db.execute("SELECT id FROM runs WHERE photo_path = ?", (photo_path,)).fetchone()["id"]


def test_edit_run_updates_row(app, client):
    run_id = _insert_run(app, "/fake/edit_test.jpg")

    resp = client.post(
        f"/runs/{run_id}/edit",
        data={
            "distance": "10.0",
            "duration": "60.0",
            "pace": "6.0",
            "run_at": "2026-06-22T09:00",
            "note": "updated note",
            "calories": "500",
            "incline": "2.0",
        },
    )
    assert resp.status_code in (302, 200)

    with app.app_context():
        row = get_db().execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    assert row["distance"] == 10.0
    assert row["duration"] == 60.0
    assert row["note"] == "updated note"
    assert row["calories"] == 500


def test_delete_run_removes_row_and_file(app, client):
    upload_folder = app.config["UPLOAD_FOLDER"]
    fname = "delete_test.jpg"
    fpath = os.path.join(upload_folder, fname)
    with open(fpath, "wb") as f:
        f.write(_TINY_JPEG)

    run_id = _insert_run(app, fpath)

    resp = client.post(f"/runs/{run_id}/delete")
    assert resp.status_code in (302, 200)

    with app.app_context():
        row = get_db().execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    assert row is None
    assert not os.path.exists(fpath)


def test_edit_delete_nonexistent_run_returns_404(app, client):
    resp_edit = client.get("/runs/99999/edit")
    assert resp_edit.status_code == 404

    resp_delete = client.post("/runs/99999/delete")
    assert resp_delete.status_code == 404
