import os
from flask import Flask
from .db import close_db, init_db


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, "fitness.db"),
        UPLOAD_FOLDER=os.path.join(app.instance_path, "uploads"),
        MODEL=os.environ.get("MODEL", "claude-sonnet-4-6"),
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev"),
    )

    if test_config is not None:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    init_db(app)

    from .routes import bp
    app.register_blueprint(bp)

    app.teardown_appcontext(close_db)

    return app
