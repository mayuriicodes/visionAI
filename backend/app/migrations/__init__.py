import sqlite3
from datetime import datetime, timezone

from .v001_classification_runs import upgrade as upgrade_classification_runs
from .v002_source_image_hashes import upgrade as upgrade_source_image_hashes

MIGRATIONS = {
    1: upgrade_classification_runs,
    2: upgrade_source_image_hashes,
}


def apply_pending_migrations(connection: sqlite3.Connection) -> None:
    connection.execute("BEGIN IMMEDIATE")
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        applied_versions = {
            row["version"]
            for row in connection.execute("SELECT version FROM schema_migrations")
        }
        for version, upgrade in sorted(MIGRATIONS.items()):
            if version in applied_versions:
                continue
            upgrade(connection)
            connection.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (version, datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )
    except Exception:
        connection.rollback()
        raise
