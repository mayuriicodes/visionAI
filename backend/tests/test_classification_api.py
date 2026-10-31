import io
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

from app import main

PREDICTIONS = [
    {"label": "tabby, tabby cat", "confidence": 0.72},
    {"label": "tiger cat", "confidence": 0.16},
    {"label": "Egyptian cat", "confidence": 0.05},
]


def image_bytes(
    image_format: str = "JPEG",
    color: tuple[int, int, int] = (200, 80, 40),
) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (32, 24), color=color).save(output, format=image_format)
    return output.getvalue()


class ClassificationApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        data_path = Path(self.temporary_directory.name)
        self.original_database_path = main.DATABASE_PATH
        self.original_classification_image_dir = main.CLASSIFICATION_IMAGE_DIR
        self.original_detection_image_dir = main.DETECTION_IMAGE_DIR
        main.DATABASE_PATH = data_path / "test.sqlite3"
        main.CLASSIFICATION_IMAGE_DIR = data_path / "classifications"
        main.DETECTION_IMAGE_DIR = data_path / "detections"
        self.client = TestClient(main.app)
        self.client.__enter__()
        response = self.client.post(
            "/api/auth/register",
            json={
                "name": "VisionAI Test",
                "email": "visionai-test@example.com",
                "password": "test-password-123",
            },
        )
        self.assertEqual(response.status_code, 201)

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        main.DATABASE_PATH = self.original_database_path
        main.CLASSIFICATION_IMAGE_DIR = self.original_classification_image_dir
        main.DETECTION_IMAGE_DIR = self.original_detection_image_dir
        self.temporary_directory.cleanup()

    def upload_classification(self, filename: str = "sample.jpg", data: bytes | None = None):
        return self.client.post(
            "/api/classifications",
            files={
                "image": (
                    filename,
                    image_bytes() if data is None else data,
                    "image/jpeg" if filename.lower().endswith((".jpg", ".jpeg")) else "image/png",
                )
            },
        )

    def test_classification_results_persist_and_owner_can_view_preview(self) -> None:
        with patch.object(
            main.image_classification_service, "predict", return_value=PREDICTIONS
        ):
            response = self.upload_classification()

        self.assertEqual(response.status_code, 201, response.text)
        result = response.json()
        self.assertEqual(len(result["predictions"]), 3)
        self.assertEqual(result["predictions"], PREDICTIONS)
        self.assertEqual(result["model"], main.MODEL_NAME)

        history = self.client.get("/api/classifications")
        self.assertEqual(history.status_code, 200)
        self.assertEqual([item["id"] for item in history.json()], [result["id"]])

        detail = self.client.get(f"/api/classifications/{result['id']}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json(), result)

        preview = self.client.get(result["image_url"])
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.headers["content-type"], "image/jpeg")
        with Image.open(io.BytesIO(preview.content)) as decoded:
            self.assertEqual(decoded.size, (32, 24))

        dashboard = self.client.get("/api/dashboard")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.json()["total_classifications"], 1)
        self.assertEqual(
            dashboard.json()["activities"][0]["action"],
            "classification_completed",
        )

    def test_png_upload_is_supported(self) -> None:
        with patch.object(
            main.image_classification_service, "predict", return_value=PREDICTIONS
        ):
            response = self.client.post(
                "/api/classifications",
                files={
                    "image": (
                        "sample.png",
                        image_bytes("PNG"),
                        "image/png",
                    )
                },
            )

        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["content_type"], "image/png")
        self.assertEqual(self.client.get(response.json()["image_url"]).status_code, 200)

    def test_classification_results_are_owner_scoped(self) -> None:
        with patch.object(
            main.image_classification_service, "predict", return_value=PREDICTIONS
        ):
            created = self.upload_classification()
        self.assertEqual(created.status_code, 201, created.text)

        registration = self.client.post(
            "/api/auth/register",
            json={
                "name": "Second Test",
                "email": "second-test@example.com",
                "password": "test-password-456",
            },
        )
        self.assertEqual(registration.status_code, 201)
        self.assertEqual(self.client.get("/api/classifications").json(), [])
        self.assertEqual(
            self.client.get(f"/api/classifications/{created.json()['id']}").status_code,
            404,
        )
        self.assertEqual(
            self.client.get(created.json()["image_url"]).status_code,
            404,
        )

    def test_classification_history_survives_a_new_session(self) -> None:
        with patch.object(
            main.image_classification_service, "predict", return_value=PREDICTIONS
        ):
            created = self.upload_classification()
        self.assertEqual(created.status_code, 201, created.text)

        self.client.__exit__(None, None, None)
        self.client = TestClient(main.app)
        self.client.__enter__()
        login = self.client.post(
            "/api/auth/login",
            json={"email": "visionai-test@example.com", "password": "test-password-123"},
        )
        self.assertEqual(login.status_code, 200)
        history = self.client.get("/api/classifications")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()[0]["id"], created.json()["id"])

    def test_classification_endpoints_require_authentication(self) -> None:
        self.client.cookies.clear()
        self.assertEqual(self.client.get("/api/classifications").status_code, 401)
        self.assertEqual(
            self.client.post(
                "/api/classifications",
                files={"image": ("sample.jpg", image_bytes(), "image/jpeg")},
            ).status_code,
            401,
        )

    def test_invalid_mismatched_and_oversized_uploads_are_rejected(self) -> None:
        invalid = self.upload_classification(data=b"not an image")
        self.assertEqual(invalid.status_code, 422)

        mismatch = self.client.post(
            "/api/classifications",
            files={"image": ("wrong.png", image_bytes("JPEG"), "image/png")},
        )
        self.assertEqual(mismatch.status_code, 422)

        with patch("app.services.image_classification.MAX_IMAGE_PIXELS", 500):
            excessive_dimensions = self.upload_classification()
        self.assertEqual(excessive_dimensions.status_code, 422)

        unsupported = self.client.post(
            "/api/classifications",
            files={"image": ("sample.gif", b"not a supported image", "image/gif")},
        )
        self.assertEqual(unsupported.status_code, 422)

        with patch.object(
            main.image_classification_service, "predict", return_value=PREDICTIONS
        ):
            unknown_mime = self.client.post(
                "/api/classifications",
                files={"image": ("sample.jpg", image_bytes(), "application/octet-stream")},
            )
        self.assertEqual(unknown_mime.status_code, 201)

        oversized = self.client.post(
            "/api/classifications",
            files={
                "image": (
                    "large.jpg",
                    b"x" * (main.CLASSIFICATION_MAX_UPLOAD_BYTES + 1),
                    "image/jpeg",
                )
            },
        )
        self.assertEqual(oversized.status_code, 413)

    def test_model_failure_returns_service_unavailable_without_saving_history(self) -> None:
        with patch.object(
            main.image_classification_service,
            "predict",
            side_effect=RuntimeError("model weights unavailable"),
        ):
            response = self.upload_classification()

        self.assertEqual(response.status_code, 503)
        self.assertIn("classification is unavailable", response.json()["detail"].lower())

        with patch.object(main.image_classification_service, "predict", return_value=[]):
            empty_result = self.upload_classification()
        self.assertEqual(empty_result.status_code, 503)
        self.assertEqual(self.client.get("/api/classifications").json(), [])
        self.assertEqual(list(main.CLASSIFICATION_IMAGE_DIR.glob("*")), [])

    def test_migration_is_versioned_additive_and_idempotent(self) -> None:
        with closing(sqlite3.connect(main.DATABASE_PATH)) as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            self.assertTrue(
                {
                    "users",
                    "activities",
                    "detections",
                    "detection_runs",
                    "classifications",
                    "classification_runs",
                    "schema_migrations",
                }.issubset(tables)
            )
            self.assertEqual(
                connection.execute(
                    "SELECT version FROM schema_migrations ORDER BY version"
                ).fetchall(),
                [(1,), (2,)],
            )
            for table in ("detection_runs", "classification_runs"):
                columns = {
                    row[1] for row in connection.execute(f"PRAGMA table_info({table})")
                }
                self.assertIn("source_sha256", columns)
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM classifications"
                ).fetchone()[0],
                0,
            )

        main.startup()
        with closing(sqlite3.connect(main.DATABASE_PATH)) as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0],
                2,
            )

    def test_dashboard_counts_runs_deduplicates_images_and_links_saved_results(self) -> None:
        original_image = image_bytes()
        other_image = image_bytes(color=(40, 100, 210))

        with patch.object(
            main.image_classification_service, "predict", return_value=PREDICTIONS
        ):
            first_classification = self.upload_classification(
                "first.jpg", original_image
            )
            duplicate_classification = self.upload_classification(
                "duplicate.jpg", original_image
            )
            distinct_classification = self.upload_classification(
                "different.jpg", other_image
            )

        self.assertEqual(first_classification.status_code, 201, first_classification.text)
        self.assertEqual(duplicate_classification.status_code, 201, duplicate_classification.text)
        self.assertEqual(distinct_classification.status_code, 201, distinct_classification.text)

        detection = {
            "name": "cat",
            "confidence": 0.91,
            "box": {"x1": 1.0, "y1": 2.0, "x2": 20.0, "y2": 21.0},
        }
        with (
            patch.object(
                main.object_detection_service,
                "decode_image",
                return_value=Image.new("RGB", (32, 24)),
            ),
            patch.object(
                main.object_detection_service,
                "predict",
                return_value={
                    "width": 32,
                    "height": 24,
                    "objects": [detection],
                    "annotated_image": image_bytes(),
                },
            ),
        ):
            detection_response = self.client.post(
                "/api/detections",
                files={"image": ("same-source.jpg", original_image, "image/jpeg")},
            )

        self.assertEqual(detection_response.status_code, 201, detection_response.text)
        dashboard = self.client.get("/api/dashboard")
        self.assertEqual(dashboard.status_code, 200, dashboard.text)
        data = dashboard.json()
        self.assertEqual(data["total_object_detection_runs"], 1)
        self.assertEqual(data["total_image_classifications"], 3)
        self.assertEqual(data["total_images_processed"], 2)
        self.assertEqual(data["recent_activity_count"], 4)
        self.assertEqual(len(data["recent_results"]), 4)
        self.assertEqual(
            {activity["type"] for activity in data["recent_results"]},
            {"detection", "classification"},
        )

        for activity in data["recent_results"]:
            endpoint = "detections" if activity["type"] == "detection" else "classifications"
            result = self.client.get(f"/api/{endpoint}/{activity['result_id']}")
            self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(
                self.client.get(result.json()["image_url"]).status_code,
                200,
            )

        self.client.post(
            "/api/auth/register",
            json={
                "name": "Second Test",
                "email": "second-dashboard@example.com",
                "password": "test-password-456",
            },
        )
        other_dashboard = self.client.get("/api/dashboard")
        self.assertEqual(other_dashboard.status_code, 200)
        self.assertEqual(other_dashboard.json()["total_object_detection_runs"], 0)
        self.assertEqual(other_dashboard.json()["total_image_classifications"], 0)
        self.assertEqual(other_dashboard.json()["total_images_processed"], 0)
        self.assertEqual(other_dashboard.json()["recent_activity_count"], 0)

    def test_dashboard_deduplicates_legacy_runs_by_saved_image_metadata(self) -> None:
        user_id = self.client.get("/api/auth/me").json()["id"]
        created_at = main.utc_now()
        with main.get_connection() as connection:
            connection.execute(
                """
                INSERT INTO detection_runs (
                    user_id, original_filename, content_type, file_size,
                    image_width, image_height, detections_json,
                    annotated_filename, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    "legacy.png",
                    "image/png",
                    1234,
                    32,
                    24,
                    "[]",
                    "legacy-detection.jpg",
                    created_at,
                ),
            )
            connection.execute(
                """
                INSERT INTO classification_runs (
                    user_id, original_filename, content_type, file_size,
                    image_width, image_height, predictions_json,
                    preview_filename, model_name, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    "legacy.png",
                    "image/png",
                    1234,
                    32,
                    24,
                    "[]",
                    "legacy-classification.jpg",
                    "test-model",
                    created_at,
                ),
            )

        dashboard = self.client.get("/api/dashboard")
        self.assertEqual(dashboard.status_code, 200, dashboard.text)
        self.assertEqual(dashboard.json()["total_object_detection_runs"], 1)
        self.assertEqual(dashboard.json()["total_image_classifications"], 1)
        self.assertEqual(dashboard.json()["total_images_processed"], 1)

    def test_existing_detection_api_contract_remains_available(self) -> None:
        annotated = image_bytes()
        detection = {
            "name": "cat",
            "confidence": 0.91,
            "box": {"x1": 1.0, "y1": 2.0, "x2": 20.0, "y2": 21.0},
        }
        with (
            patch.object(
                main.object_detection_service,
                "decode_image",
                return_value=Image.new("RGB", (32, 24)),
            ),
            patch.object(
                main.object_detection_service,
                "predict",
                return_value={
                    "width": 32,
                    "height": 24,
                    "objects": [detection],
                    "annotated_image": annotated,
                },
            ),
        ):
            response = self.client.post(
                "/api/detections",
                files={"image": ("detection.jpg", image_bytes(), "image/jpeg")},
            )

        self.assertEqual(response.status_code, 201, response.text)
        result = response.json()
        self.assertEqual(result["detections"], [detection])
        self.assertEqual(
            set(result),
            {
                "id",
                "original_filename",
                "content_type",
                "file_size",
                "width",
                "height",
                "detections",
                "created_at",
                "image_url",
            },
        )
        history = self.client.get("/api/detections")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()[0]["id"], result["id"])
        self.assertEqual(
            self.client.get(result["image_url"]).headers["content-type"],
            "image/jpeg",
        )


if __name__ == "__main__":
    unittest.main()
