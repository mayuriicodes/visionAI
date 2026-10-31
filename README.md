# VisionAI

VisionAI is an AI-powered image classification and object detection web application built with React + Vite and FastAPI. It provides SQLite-backed accounts, secure password hashing, signed JWT sessions in HTTP-only cookies, protected workspace pages, YOLO object detection, and general-purpose ImageNet image classification.

## Prerequisites

- Python 3.10 or newer
- Node.js LTS and npm

## Set up the backend

From the project root, create and activate a virtual environment and install the backend dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
```

Start the API:

```powershell
python -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

The local JWT signing secret is generated once and stored under `backend\data`; this directory also holds the SQLite database and is ignored by Git. For deployments, set a private signing key of at least 32 characters in `VISIONAI_JWT_SECRET` and set `VISIONAI_COOKIE_SECURE=true` when serving over HTTPS. `VISIONAI_DATABASE_PATH` can be set to use a different SQLite file.

## Set up the frontend

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. Vite proxies `/api` requests to FastAPI on port 8000.

## Phase 2 API

- `POST /api/auth/register` creates an account and signs it in.
- `POST /api/auth/login` verifies the account password and signs in.
- `POST /api/auth/logout` clears the session cookie.
- `GET /api/auth/me` returns the authenticated user.
- `GET /api/dashboard` returns authenticated run totals, unique tracked source-image totals, and recent owner-scoped classification/detection results; it requires an active session.
- `POST /api/classifications` classifies an uploaded JPG, JPEG, or PNG image and returns its top three ImageNet-1K labels and scores.
- `GET /api/classifications` lists up to 50 saved classifications; `GET /api/classifications/{id}` returns one result, and `GET /api/classifications/{id}/image` serves its owner-scoped preview.

Passwords are hashed with scrypt. Session JWTs are signed with HS256, expire after 30 minutes, and are kept in an HTTP-only, SameSite=Lax cookie. Dashboard statistics are derived from the signed-in user's SQLite records; no sample or simulated predictions are shown. New run records store a SHA-256 fingerprint of the uploaded image so repeats across the two analysis tools count once. Older saved runs predate that fingerprint and their original uploads are not retained, so matching filename, file size, and image dimensions are used as a fallback identity; distinct images with identical metadata may therefore be counted together.

## Object detection

The authenticated `POST /api/detections` endpoint accepts a JPG, JPEG, or PNG image up to 10 MB. It runs the pretrained lightweight YOLO11n model, returns detected labels, confidence scores, pixel-coordinate boxes, source image metadata, and an owner-scoped processed-image URL. Detection records and image metadata are stored in SQLite; annotated JPEGs are stored under `backend\data\detections`. The model is loaded once per backend process. Its initial weights are downloaded on the first inference and cached under `backend\data\models`. Set `VISIONAI_YOLO_MODEL` to a local `.pt` model path to select different weights.

`GET /api/detections` lists the signed-in user's recent runs, `GET /api/detections/{id}` returns one of that user's results, and `GET /api/detections/{id}/image` serves its annotated image. Requests for another user's run return 404.

## General-purpose image classification

The authenticated `POST /api/classifications` endpoint accepts a JPG, JPEG, or PNG image up to 10 MB. It uses TorchVision's pretrained EfficientNet-B0 `IMAGENET1K_V1` weights and the weights' documented preprocessing and 1,000-category label mapping to return the top three labels and confidence scores. The model loads lazily on the first classification request; if weights are not cached, TorchVision downloads them from its configured weights source. Classification uses a separate service and model from YOLO object detection.

Classification runs are stored separately in `classification_runs`; additive versioned migrations create this table, its user/date index, and the optional source-image fingerprint columns without changing or deleting existing records. A compressed JPEG preview is stored under `backend\data\classifications`; the original upload is not retained. The classification history appears separately on the History page, and result/image endpoints are scoped to the signed-in owner. Model outputs are estimates, not guarantees or clinically validated results. EfficientNet-B0 uses ImageNet's fixed label set; user-defined or medical classification is not supported by this phase.

## History

The signed-in History workspace displays up to 50 completed detection runs and up to 50 image classification runs, with separate results and View Results panels. Detection history continues to display its processed image; classification history displays its saved compressed preview.

Interactive API documentation is available at <http://127.0.0.1:8000/docs>.

Run the backend regression tests from the project root with:

```powershell
python -m pip install -r backend\requirements-test.txt
$env:PYTHONPATH = "backend"
python -m unittest discover -s backend\tests -v
```
