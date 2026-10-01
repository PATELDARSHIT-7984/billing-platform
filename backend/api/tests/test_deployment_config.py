"""Deployment settings and the real entrypoint, without connecting to a database."""
import os
from pathlib import Path
import runpy
import subprocess
import sys

import dotenv
import pytest


BACKEND = Path(__file__).resolve().parents[2]
SETTINGS = BACKEND / "api/config/settings.py"


def test_environment_overrides_local_file(monkeypatch, tmp_path):
    local = tmp_path / ".env"
    local.write_text("DATABASE_URL=postgresql://local:fake@localhost/local\nFRONTEND_ORIGIN=http://localhost:5173\n")
    loader = dotenv.load_dotenv
    monkeypatch.setattr(dotenv, "load_dotenv", lambda path, override: loader(local, override=override))
    monkeypatch.setenv("DATABASE_URL", "postgres://demo:fake%25@db.example/demo")
    monkeypatch.setenv("FRONTEND_ORIGIN", "https://demo.example/")
    settings = runpy.run_path(str(SETTINGS))
    assert settings["DATABASE_URL"] == "postgresql://demo:fake%25@db.example/demo"
    assert settings["FRONTEND_ORIGINS"] == ["https://demo.example"]


def test_local_file_is_resolved_independently_of_working_directory(monkeypatch, tmp_path):
    local = tmp_path / ".env"
    local.write_text("DATABASE_URL=postgresql://local:fake@localhost/local\n")
    loader = dotenv.load_dotenv

    def load_local(path, override):
        assert path == BACKEND / ".env"
        return loader(local, override=override)

    monkeypatch.setattr(dotenv, "load_dotenv", load_local)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("FRONTEND_ORIGIN", raising=False)
    monkeypatch.chdir(tmp_path)
    settings = runpy.run_path(str(SETTINGS))
    assert settings["DATABASE_URL"] == "postgresql://local:fake@localhost/local"
    assert settings["FRONTEND_ORIGINS"] == ["http://localhost:5173"]


def test_missing_database_url_fails_clearly(monkeypatch):
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        runpy.run_path(str(SETTINGS))


@pytest.mark.parametrize("origin", ["*", "https://*.example", "https://demo.example/path", "demo.example"])
def test_invalid_cors_origin_is_rejected(monkeypatch, origin):
    monkeypatch.setenv("DATABASE_URL", "postgresql://demo:fake@db.example/demo")
    monkeypatch.setenv("FRONTEND_ORIGIN", origin)
    with pytest.raises(RuntimeError, match="FRONTEND_ORIGIN"):
        runpy.run_path(str(SETTINGS))


def test_real_entrypoint_health_and_cors_without_database():
    env = dict(os.environ, DATABASE_URL="postgresql://demo:fake@invalid.example/demo",
               FRONTEND_ORIGIN="https://demo.example", PYTHONDONTWRITEBYTECODE="1")
    script = '''
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
def forbidden_connection(*args, **kwargs):
    raise AssertionError("Health/startup must not connect to the database")
Engine.connect = forbidden_connection
from api.main import app
with TestClient(app) as client:
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
    for origin, expected in [('https://demo.example', 200), ('https://other.example', 400)]:
        response = client.options('/health', headers={'Origin': origin, 'Access-Control-Request-Method': 'GET'})
        assert response.status_code == expected
        assert response.headers.get('access-control-allow-origin') == (origin if expected == 200 else None)
'''
    result = subprocess.run([sys.executable, "-B", "-c", script], cwd=BACKEND,
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
