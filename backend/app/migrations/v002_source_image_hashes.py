import sqlite3


def upgrade(connection: sqlite3.Connection) -> None:
    connection.execute(
        "ALTER TABLE detection_runs ADD COLUMN source_sha256 TEXT"
    )
    connection.execute(
        "ALTER TABLE classification_runs ADD COLUMN source_sha256 TEXT"
    )
    connection.execute(
        """
        CREATE INDEX idx_detection_runs_user_source
        ON detection_runs(user_id, source_sha256)
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_classification_runs_user_source
        ON classification_runs(user_id, source_sha256)
        """
    )
