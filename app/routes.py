import os
import uuid
from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    url_for,
)
from werkzeug.utils import secure_filename

from .db import get_db
from .exif import read_datetime_original
from .vision import extract_run_stats

bp = Blueprint("runs", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/upload", methods=["POST"])
def upload():
    photo = request.files.get("photo")
    if not photo or photo.filename == "":
        return redirect(url_for("runs.index"))

    filename = secure_filename(photo.filename)
    upload_folder = current_app.config["UPLOAD_FOLDER"]
    photo_path = os.path.join(upload_folder, filename)
    photo.save(photo_path)

    model = current_app.config["MODEL"]
    stats = extract_run_stats(photo_path, model)

    run_dt = read_datetime_original(photo_path)
    exif_date_missing = 0
    if run_dt is None:
        run_dt = datetime.now()
        exif_date_missing = 1

    return render_template(
        "confirm.html",
        photo_path=photo_path,
        distance=stats.get("distance") or "",
        duration=stats.get("duration") or "",
        pace=stats.get("pace") or "",
        calories=stats.get("calories") or "",
        incline=stats.get("incline") or "",
        run_at=run_dt.strftime("%Y-%m-%dT%H:%M"),
        exif_date_missing=exif_date_missing,
    )


@bp.route("/save", methods=["POST"])
def save():
    db = get_db()
    db.execute(
        """INSERT INTO runs
           (photo_path, distance, duration, pace, run_at, note,
            calories, incline, exif_date_missing)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            request.form.get("photo_path"),
            _float_or_none(request.form.get("distance")),
            _float_or_none(request.form.get("duration")),
            _float_or_none(request.form.get("pace")),
            request.form.get("run_at"),
            request.form.get("note") or None,
            _int_or_none(request.form.get("calories")),
            _float_or_none(request.form.get("incline")),
            int(request.form.get("exif_date_missing", 0)),
        ),
    )
    db.commit()
    return redirect(url_for("runs.index"))


def _float_or_none(val):
    try:
        return float(val) if val else None
    except (ValueError, TypeError):
        return None


def _int_or_none(val):
    try:
        return int(val) if val else None
    except (ValueError, TypeError):
        return None
