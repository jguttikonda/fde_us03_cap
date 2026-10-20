"""Throwaway PostgreSQL in Docker, loaded with the FX123 mock data."""

import subprocess
import time
from pathlib import Path

import psycopg

DB_DIR = Path(__file__).resolve().parent.parent / "db"


class DockerPostgres:
    name = "aog-demo-pg"
    port = 55432
    uri = f"postgresql://postgres:aog@localhost:{port}/postgres"

    def start(self) -> str:
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)
        subprocess.run(
            ["docker", "run", "-d", "--rm", "--name", self.name, "-e", "POSTGRES_PASSWORD=aog",
             "-p", f"{self.port}:5432", "postgres:16"],
            check=True, capture_output=True)
        # The image's temporary init server has no TCP listener, so a TCP connect means the real server is up.
        for _ in range(90):
            try:
                psycopg.connect(self.uri, connect_timeout=2).close()
                return self.uri
            except psycopg.OperationalError:
                time.sleep(1)
        raise RuntimeError("PostgreSQL container did not become ready")

    def cleanup(self) -> None:
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True)


def load_mock_data(uri: str, verbose: bool = True) -> None:
    with psycopg.connect(uri, autocommit=True) as conn:
        for name in ("schema.sql", "seed.sql"):
            conn.execute((DB_DIR / name).read_text(encoding="utf-8"))
            if verbose:
                print(f"  loaded {name}")
