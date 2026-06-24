import os
import tempfile
import pytest
from app import create_app


@pytest.fixture()
def app(tmp_path):
    db_path = str(tmp_path / "test.db")
    uploads_path = str(tmp_path / "uploads")
    os.makedirs(uploads_path)

    application = create_app(
        test_config={
            "TESTING": True,
            "DATABASE": db_path,
            "UPLOAD_FOLDER": uploads_path,
            "MODEL": "claude-sonnet-4-6",
        }
    )
    yield application


@pytest.fixture()
def client(app):
    return app.test_client()
