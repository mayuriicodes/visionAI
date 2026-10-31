import sqlite3


def upgrade(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE classification_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            original_filename TEXT NOT NULL,
            content_type TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            image_width INTEGER NOT NULL,
            image_height INTEGER NOT NULL,
            predictions_json TEXT NOT NULL,
            preview_filename TEXT NOT NULL UNIQUE,
            model_name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX idx_classification_runs_user_created
        ON classification_runs(user_id, created_at DESC)
        """
    )
