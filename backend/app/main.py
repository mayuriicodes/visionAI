import asyncio
import base64
import hashlib
import hmac
import io
import json
import logging
import os
import re
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Iterator

import jwt
from fastapi import Cookie, FastAPI, File, HTTPException, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from PIL import Image
from pydantic import BaseModel, Field, field_validator

from app.migrations import apply_pending_migrations
from app.services.image_classification import (
    DEFAULT_TOP_K,
    MODEL_NAME,
    InvalidClassificationImage,
    image_classification_service,
)
from app.services.object_detection import InvalidImageError, object_detection_service

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR.parent / "data"
DETECTION_IMAGE_DIR = DATA_DIR / "detections"
CLASSIFICATION_IMAGE_DIR = DATA_DIR / "classifications"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
CLASSIFICATION_MAX_UPLOAD_BYTES = 10 * 1024 * 1024
DATABASE_PATH = Path(
    os.environ.get("VISIONAI_DATABASE_PATH", DATA_DIR / "visionai.sqlite3")
)
TOKEN_COOKIE = "visionai_access_token"
TOKEN_LIFETIME = timedelta(minutes=30)
COOKIE_SECURE = os.environ.get("VISIONAI_COOKIE_SECURE", "").lower() == "true"
logger = logging.getLogger(__name__)


def get_jwt_secret() -> str:
    configured_secret = os.environ.get("VISIONAI_JWT_SECRET")
    if configured_secret:
        if len(configured_secret) < 32:
            raise RuntimeError("VISIONAI_JWT_SECRET must contain at least 32 characters.")
        return configured_secret

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    secret_path = DATA_DIR / ".jwt_secret"
    try:
        with secret_path.open("x", encoding="utf-8") as secret_file:
            secret_file.write(secrets.token_urlsafe(48))
    except FileExistsError:
        pass
    return secret_path.read_text(encoding="utf-8").strip()


JWT_SECRET = get_jwt_secret()

app = FastAPI(title="VisionAI API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS activities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                action TEXT NOT NULL,
                details TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_activities_user_created
                ON activities(user_id, created_at DESC);
            CREATE TABLE IF NOT EXISTS detection_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                original_filename TEXT NOT NULL,
                content_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                image_width INTEGER NOT NULL,
                image_height INTEGER NOT NULL,
                detections_json TEXT NOT NULL,
                annotated_filename TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_detection_runs_user_created
                ON detection_runs(user_id, created_at DESC);
            CREATE TABLE IF NOT EXISTS detections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                label TEXT NOT NULL,
                confidence REAL NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS classifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                result TEXT NOT NULL,
                confidence REAL NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        detection_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(detections)")
        }
        if "run_id" not in detection_columns:
            connection.execute(
                "ALTER TABLE detections ADD COLUMN run_id INTEGER "
                "REFERENCES detection_runs(id) ON DELETE CASCADE"
            )


@app.on_event("startup")
def startup() -> None:
    initialize_database()
    with get_connection() as connection:
        apply_pending_migrations(connection)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    password_hash = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return "$".join(
        (
            "scrypt",
            "16384",
            "8",
            "1",
            base64.urlsafe_b64encode(salt).decode("ascii"),
            base64.urlsafe_b64encode(password_hash).decode("ascii"),
        )
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, n, r, p, salt_value, hash_value = stored_hash.split("$")
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_value.encode("ascii"))
        expected_hash = base64.urlsafe_b64decode(hash_value.encode("ascii"))
        actual_hash = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual_hash, expected_hash)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_access_token(user_id: int) -> str:
    expires_at = datetime.now(timezone.utc) + TOKEN_LIFETIME
    return jwt.encode(
        {"sub": str(user_id), "exp": expires_at},
        JWT_SECRET,
        algorithm="HS256",
    )


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("Please enter your full name.")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
            raise ValueError("Enter a valid email address.")
        return normalized


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


def user_response(user: sqlite3.Row) -> dict[str, int | str]:
    return {"id": user["id"], "name": user["name"], "email": user["email"]}


def get_current_user(token: str | None) -> dict[str, int | str]:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please sign in to continue.",
        )
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session has expired. Please sign in again.",
        ) from None
    with get_connection() as connection:
        user = connection.execute(
            "SELECT id, name, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your account could not be found.",
        )
    return user_response(user)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "VisionAI API is running"}


@app.get("/api/health")
def read_health() -> dict[str, str]:
    return {"status": "ok", "service": "VisionAI API"}


@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response) -> dict[str, int | str]:
    password_hash = hash_password(payload.password)
    created_at = utc_now()
    try:
        with get_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO users (name, email, password_hash, created_at) "
                "VALUES (?, ?, ?, ?)",
                (payload.name, payload.email, password_hash, created_at),
            )
            user_id = cursor.lastrowid
            connection.execute(
                "INSERT INTO activities (user_id, action, details, created_at) "
                "VALUES (?, ?, ?, ?)",
                (user_id, "account_created", "Your VisionAI account was created.", created_at),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from None

    response.set_cookie(
        TOKEN_COOKIE,
        create_access_token(user_id),
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=int(TOKEN_LIFETIME.total_seconds()),
        path="/",
    )
    return {"id": user_id, "name": payload.name, "email": payload.email}


@app.post("/api/auth/login")
def login(payload: LoginRequest, response: Response) -> dict[str, int | str]:
    with get_connection() as connection:
        user = connection.execute(
            "SELECT id, name, email, password_hash FROM users WHERE email = ?",
            (payload.email,),
        ).fetchone()
        if user is None or not verify_password(payload.password, user["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email or password is incorrect.",
            )
        connection.execute(
            "INSERT INTO activities (user_id, action, details, created_at) "
            "VALUES (?, ?, ?, ?)",
            (user["id"], "signed_in", "You signed in to VisionAI.", utc_now()),
        )

    response.set_cookie(
        TOKEN_COOKIE,
        create_access_token(user["id"]),
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        max_age=int(TOKEN_LIFETIME.total_seconds()),
        path="/",
    )
    return user_response(user)


@app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(
        TOKEN_COOKIE,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


@app.get("/api/auth/me")
def read_current_user(
    token: Annotated[str | None, Cookie(alias=TOKEN_COOKIE)] = None,
) -> dict[str, int | str]:
    return get_current_user(token)


@app.get("/api/dashboard")
def read_dashboard(
    token: Annotated[str | None, Cookie(alias=TOKEN_COOKIE)] = None,
) -> dict[str, object]:
    current_user = get_current_user(token)
    user_id = current_user["id"]
    with get_connection() as connection:
        detections = connection.execute(
            "SELECT COUNT(*) AS count FROM detections WHERE user_id = ?", (user_id,)
        ).fetchone()["count"]
        legacy_classifications = connection.execute(
            "SELECT COUNT(*) AS count FROM classifications WHERE user_id = ?", (user_id,)
        ).fetchone()["count"]
        classification_runs = connection.execute(
            "SELECT COUNT(*) AS count FROM classification_runs WHERE user_id = ?",
            (user_id,),
        ).fetchone()["count"]
        detection_runs = connection.execute(
            "SELECT COUNT(*) AS count FROM detection_runs WHERE user_id = ?",
            (user_id,),
        ).fetchone()["count"]
        source_hashes = connection.execute(
            """
            SELECT source_sha256 FROM detection_runs
            WHERE user_id = ? AND source_sha256 IS NOT NULL
            UNION
            SELECT source_sha256 FROM classification_runs
            WHERE user_id = ? AND source_sha256 IS NOT NULL
            """,
            (user_id, user_id),
        ).fetchall()
        legacy_image_signatures = connection.execute(
            """
            SELECT LOWER(original_filename) AS filename,
                   file_size, image_width, image_height
            FROM detection_runs
            WHERE user_id = ? AND source_sha256 IS NULL
            UNION
            SELECT LOWER(original_filename) AS filename,
                   file_size, image_width, image_height
            FROM classification_runs
            WHERE user_id = ? AND source_sha256 IS NULL
            """,
            (user_id, user_id),
        ).fetchall()
        activities = connection.execute(
            "SELECT id, action, details, created_at FROM activities "
            "WHERE user_id = ? ORDER BY created_at DESC, id DESC LIMIT 8",
            (user_id,),
        ).fetchall()
        recent_results = connection.execute(
            """
            SELECT 'detection' AS activity_type, id AS result_id,
                   original_filename, created_at, detections_json AS result_json
            FROM detection_runs
            WHERE user_id = ?
            UNION ALL
            SELECT 'classification' AS activity_type, id AS result_id,
                   original_filename, created_at, predictions_json AS result_json
            FROM classification_runs
            WHERE user_id = ?
            ORDER BY created_at DESC, result_id DESC, activity_type
            LIMIT 8
            """,
            (user_id, user_id),
        ).fetchall()

    recent_activity = []
    for result in recent_results:
        details = json.loads(result["result_json"])
        if result["activity_type"] == "detection":
            object_count = len(details)
            summary = (
                f"{object_count} "
                f"{'object' if object_count == 1 else 'objects'} detected"
                if object_count
                else "No objects detected"
            )
        else:
            summary = details[0]["label"] if details else "No prediction returned"
        recent_activity.append(
            {
                "type": result["activity_type"],
                "result_id": result["result_id"],
                "original_filename": result["original_filename"],
                "created_at": result["created_at"],
                "summary": summary,
            }
        )

    return {
        "total_detections": detections,
        "total_classifications": legacy_classifications + classification_runs,
        "activities": [dict(activity) for activity in activities],
        "total_object_detection_runs": detection_runs,
        "total_image_classifications": legacy_classifications + classification_runs,
        "total_images_processed": len(source_hashes) + len(legacy_image_signatures),
        "recent_activity_count": len(recent_activity),
        "recent_results": recent_activity,
    }


def detection_run_response(run: sqlite3.Row) -> dict[str, object]:
    return {
        "id": run["id"],
        "original_filename": run["original_filename"],
        "content_type": run["content_type"],
        "file_size": run["file_size"],
        "width": run["image_width"],
        "height": run["image_height"],
        "detections": json.loads(run["detections_json"]),
        "created_at": run["created_at"],
        "image_url": f"/api/detections/{run['id']}/image",
    }


@app.post("/api/detections", status_code=status.HTTP_201_CREATED)
async def create_detection(
    image: Annotated[UploadFile, File(...)],
    token: Annotated[str | None, Cookie(alias=TOKEN_COOKIE)] = None,
) -> dict[str, object]:
    current_user = get_current_user(token)
    if not image.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Choose a JPG, JPEG, or PNG image.",
        )

    image_bytes = await image.read(MAX_UPLOAD_BYTES + 1)
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image files must be 10 MB or smaller.",
        )
    try:
        decoded_image = object_detection_service.decode_image(
            image_bytes, Path(image.filename).name
        )
    except InvalidImageError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    finally:
        await image.close()

    try:
        inference = await asyncio.to_thread(object_detection_service.predict, decoded_image)
    except Exception as error:
        logger.exception("YOLO inference failed for user %s", current_user["id"])
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Object detection is unavailable. Check that the YOLO model can be loaded.",
        ) from error

    DETECTION_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    annotated_filename = f"{uuid.uuid4().hex}.jpg"
    annotated_path = DETECTION_IMAGE_DIR / annotated_filename
    try:
        annotated_path.write_bytes(inference["annotated_image"])
        created_at = utc_now()
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO detection_runs (
                    user_id, original_filename, content_type, file_size,
                    image_width, image_height, detections_json,
                    annotated_filename, created_at, source_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    current_user["id"],
                    Path(image.filename).name,
                    image.content_type or "application/octet-stream",
                    len(image_bytes),
                    inference["width"],
                    inference["height"],
                    json.dumps(inference["objects"], separators=(",", ":")),
                    annotated_filename,
                    created_at,
                    hashlib.sha256(image_bytes).hexdigest(),
                ),
            )
            run_id = cursor.lastrowid
            connection.executemany(
                "INSERT INTO detections (user_id, label, confidence, created_at, run_id) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    (
                        current_user["id"],
                        detection["name"],
                        detection["confidence"],
                        created_at,
                        run_id,
                    )
                    for detection in inference["objects"]
                ],
            )
            connection.execute(
                "INSERT INTO activities (user_id, action, details, created_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    current_user["id"],
                    "detection_completed",
                    f"Detected {len(inference['objects'])} objects in {Path(image.filename).name}.",
                    created_at,
                ),
            )
            run = connection.execute(
                "SELECT * FROM detection_runs WHERE id = ? AND user_id = ?",
                (run_id, current_user["id"]),
            ).fetchone()
    except OSError as error:
        annotated_path.unlink(missing_ok=True)
        logger.exception("Could not save annotated image for user %s", current_user["id"])
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The processed image could not be saved.",
        ) from error
    except sqlite3.Error as error:
        annotated_path.unlink(missing_ok=True)
        logger.exception("Could not save detection results for user %s", current_user["id"])
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Detection results could not be saved.",
        ) from error
    return detection_run_response(run)


@app.get("/api/detections")
def list_detections(
    token: Annotated[str | None, Cookie(alias=TOKEN_COOKIE)] = None,
) -> list[dict[str, object]]:
    current_user = get_current_user(token)
    with get_connection() as connection:
        runs = connection.execute(
            "SELECT * FROM detection_runs WHERE user_id = ? "
            "ORDER BY created_at DESC, id DESC LIMIT 50",
            (current_user["id"],),
        ).fetchall()
    return [detection_run_response(run) for run in runs]


@app.get("/api/detections/{run_id}/image")
def get_detection_image(
    run_id: int,
    token: Annotated[str | None, Cookie(alias=TOKEN_COOKIE)] = None,
) -> FileResponse:
    current_user = get_current_user(token)
    with get_connection() as connection:
        run = connection.execute(
            "SELECT annotated_filename FROM detection_runs WHERE id = ? AND user_id = ?",
            (run_id, current_user["id"]),
        ).fetchone()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detection result not found.",
        )
    annotated_path = DETECTION_IMAGE_DIR / run["annotated_filename"]
    if not annotated_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The processed image is no longer available.",
        )
    return FileResponse(
        annotated_path,
        media_type="image/jpeg",
        filename=f"visionai-detection-{run_id}.jpg",
    )


@app.get("/api/detections/{run_id}")
def get_detection(
    run_id: int,
    token: Annotated[str | None, Cookie(alias=TOKEN_COOKIE)] = None,
) -> dict[str, object]:
    current_user = get_current_user(token)
    with get_connection() as connection:
        run = connection.execute(
            "SELECT * FROM detection_runs WHERE id = ? AND user_id = ?",
            (run_id, current_user["id"]),
        ).fetchone()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Detection result not found.",
        )
    return detection_run_response(run)


def classification_run_response(run: sqlite3.Row) -> dict[str, object]:
    return {
        "id": run["id"],
        "original_filename": run["original_filename"],
        "content_type": run["content_type"],
        "file_size": run["file_size"],
        "width": run["image_width"],
        "height": run["image_height"],
        "predictions": json.loads(run["predictions_json"]),
        "model": run["model_name"],
        "created_at": run["created_at"],
        "image_url": f"/api/classifications/{run['id']}/image",
    }


@app.post("/api/classifications", status_code=status.HTTP_201_CREATED)
async def create_classification(
    image: Annotated[UploadFile, File(...)],
    token: Annotated[str | None, Cookie(alias=TOKEN_COOKIE)] = None,
) -> dict[str, object]:
    current_user = get_current_user(token)
    if not image.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Choose a JPG, JPEG, or PNG image.",
        )
    try:
        image_bytes = await image.read(CLASSIFICATION_MAX_UPLOAD_BYTES + 1)
    finally:
        await image.close()
    if len(image_bytes) > CLASSIFICATION_MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image files must be 10 MB or smaller.",
        )
    try:
        decoded_image = image_classification_service.decode_image(
            image_bytes, Path(image.filename).name
        )
    except InvalidClassificationImage as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    image_width, image_height = decoded_image.size
    try:
        predictions = await asyncio.to_thread(
            image_classification_service.predict, decoded_image, DEFAULT_TOP_K
        )
        if not predictions:
            raise RuntimeError("The classifier returned no predictions.")
        preview = decoded_image.copy()
        try:
            preview.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
            preview_output = io.BytesIO()
            preview.save(preview_output, format="JPEG", quality=85, optimize=True)
        finally:
            preview.close()
    except Exception as error:
        logger.exception("Image classification failed for user %s", current_user["id"])
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Image classification is unavailable. Check that the EfficientNet-B0 weights can be loaded.",
        ) from error
    finally:
        decoded_image.close()

    CLASSIFICATION_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    preview_filename = f"{uuid.uuid4().hex}.jpg"
    preview_path = CLASSIFICATION_IMAGE_DIR / preview_filename
    try:
        preview_path.write_bytes(preview_output.getvalue())
        created_at = utc_now()
        content_type = "image/png" if Path(image.filename).suffix.lower() == ".png" else "image/jpeg"
        with get_connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO classification_runs (
                    user_id, original_filename, content_type, file_size,
                    image_width, image_height, predictions_json,
                    preview_filename, model_name, created_at, source_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    current_user["id"],
                    Path(image.filename).name,
                    content_type,
                    len(image_bytes),
                    image_width,
                    image_height,
                    json.dumps(predictions, separators=(",", ":")),
                    preview_filename,
                    MODEL_NAME,
                    created_at,
                    hashlib.sha256(image_bytes).hexdigest(),
                ),
            )
            connection.execute(
                "INSERT INTO activities (user_id, action, details, created_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    current_user["id"],
                    "classification_completed",
                    f"Classified {Path(image.filename).name} with top result "
                    f"{predictions[0]['label']}.",
                    created_at,
                ),
            )
            run = connection.execute(
                "SELECT * FROM classification_runs WHERE id = ? AND user_id = ?",
                (cursor.lastrowid, current_user["id"]),
            ).fetchone()
    except OSError as error:
        preview_path.unlink(missing_ok=True)
        logger.exception("Could not save classification preview for user %s", current_user["id"])
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The classification preview could not be saved.",
        ) from error
    except sqlite3.Error as error:
        preview_path.unlink(missing_ok=True)
        logger.exception("Could not save classification results for user %s", current_user["id"])
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Classification results could not be saved.",
        ) from error
    return classification_run_response(run)


@app.get("/api/classifications")
def list_classifications(
    token: Annotated[str | None, Cookie(alias=TOKEN_COOKIE)] = None,
) -> list[dict[str, object]]:
    current_user = get_current_user(token)
    with get_connection() as connection:
        runs = connection.execute(
            "SELECT * FROM classification_runs WHERE user_id = ? "
            "ORDER BY created_at DESC, id DESC LIMIT 50",
            (current_user["id"],),
        ).fetchall()
    return [classification_run_response(run) for run in runs]


@app.get("/api/classifications/{run_id}/image")
def get_classification_image(
    run_id: int,
    token: Annotated[str | None, Cookie(alias=TOKEN_COOKIE)] = None,
) -> FileResponse:
    current_user = get_current_user(token)
    with get_connection() as connection:
        run = connection.execute(
            "SELECT preview_filename FROM classification_runs "
            "WHERE id = ? AND user_id = ?",
            (run_id, current_user["id"]),
        ).fetchone()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classification result not found.",
        )
    preview_path = CLASSIFICATION_IMAGE_DIR / run["preview_filename"]
    if not preview_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The classification preview is no longer available.",
        )
    return FileResponse(preview_path, media_type="image/jpeg")


@app.get("/api/classifications/{run_id}")
def get_classification(
    run_id: int,
    token: Annotated[str | None, Cookie(alias=TOKEN_COOKIE)] = None,
) -> dict[str, object]:
    current_user = get_current_user(token)
    with get_connection() as connection:
        run = connection.execute(
            "SELECT * FROM classification_runs WHERE id = ? AND user_id = ?",
            (run_id, current_user["id"]),
        ).fetchone()
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Classification result not found.",
        )
    return classification_run_response(run)
