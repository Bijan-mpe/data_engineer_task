"""Unit checks for Docker and Docker Compose configuration files."""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def compose_config():
    """Return normalized Docker Compose config from the Docker CLI."""
    try:
        result = subprocess.run(
            ["docker", "compose", "config", "--format", "json"],
            cwd=ROOT,
            capture_output=True,
            check=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        pytest.skip(f"docker compose config is unavailable: {exc}")
    return json.loads(result.stdout)


def test_dockerfile_exists_and_runs_entrypoint():
    """Dockerfile must install runtime dependencies and run the app entrypoint."""
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "FROM python:3.12-slim" in dockerfile
    assert "pip install --no-cache-dir -r requirements.txt" in dockerfile
    assert "build-essential" not in dockerfile
    assert "USER app" in dockerfile
    assert 'CMD ["/app/docker/entrypoint.sh"]' in dockerfile


def test_dockerignore_excludes_local_only_artifacts():
    """Docker build context must exclude local and test-only artifacts."""
    dockerignore = (ROOT / ".dockerignore").read_text().splitlines()
    for path in [".claude", ".codex", ".agents", "tests", "docs", "data", "reports"]:
        assert path in dockerignore


def test_compose_defines_postgres_and_api_services(compose_config):
    """Compose must define the required postgres and api services."""
    services = compose_config["services"]
    assert services["postgres"]["image"] == "postgres:16"
    assert "build" in services["api"]


def test_compose_wires_service_health_checks(compose_config):
    """Postgres and API services must expose health checks for startup ordering."""
    services = compose_config["services"]
    assert "pg_isready" in " ".join(services["postgres"]["healthcheck"]["test"])
    assert "http://localhost:8000/health" in " ".join(services["api"]["healthcheck"]["test"])
    assert services["api"]["depends_on"]["postgres"]["condition"] == "service_healthy"


def test_compose_mounts_data_directory_read_only(compose_config):
    """API container must see the source Excel files without mutating them."""
    api = compose_config["services"]["api"]
    data_mount = next(volume for volume in api["volumes"] if volume["target"] == "/app/data")
    report_mount = next(
        volume for volume in api["volumes"] if volume["target"] == "/app/reports"
    )
    assert data_mount["read_only"] is True
    assert api["environment"]["DATA_DIR"] == "/app/data"
    assert report_mount.get("read_only", False) is False
    assert api["environment"]["QUALITY_REPORT_DIR"] == "/app/reports"


def test_entrypoint_runs_migrations_pipeline_then_api():
    """Entrypoint must initialize schema, optionally seed data, then start Uvicorn."""
    entrypoint = (ROOT / "docker" / "entrypoint.sh").read_text()
    assert "alembic upgrade head" in entrypoint
    assert "RUN_PIPELINE_ON_STARTUP" in entrypoint
    assert "python -m src.pipeline.pipeline" in entrypoint
    assert "exec uvicorn src.api.main:app --host 0.0.0.0 --port 8000" in entrypoint


def test_env_example_contains_required_runtime_settings():
    """Example env file must document DB, API, and SQLAlchemy pool settings."""
    env_example = (ROOT / ".env.example").read_text()
    for key in [
        "POSTGRES_PASSWORD=",
        "DATA_DIR=",
        "QUALITY_REPORT_DIR=",
        "API_PORT=",
        "RUN_PIPELINE_ON_STARTUP=",
        "SQLALCHEMY_POOL_SIZE=",
        "SQLALCHEMY_MAX_OVERFLOW=",
        "SQLALCHEMY_POOL_TIMEOUT=",
        "SQLALCHEMY_POOL_RECYCLE=",
    ]:
        assert key in env_example
