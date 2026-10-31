import io
import os
import threading
import warnings
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

MAX_IMAGE_PIXELS = 40_000_000
ALLOWED_FORMATS = {"JPEG", "PNG"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


class InvalidImageError(ValueError):
    pass


class ObjectDetectionService:
    def __init__(self) -> None:
        self._model: Any | None = None
        self._lock = threading.Lock()

    def decode_image(self, image_bytes: bytes, filename: str) -> Image.Image:
        extension = Path(filename).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise InvalidImageError("Upload a JPG, JPEG, or PNG image.")

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(image_bytes)) as source:
                    image_format = source.format
                    width, height = source.size
                    if image_format not in ALLOWED_FORMATS:
                        raise InvalidImageError("The uploaded file is not a JPG or PNG image.")
                    if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
                        raise InvalidImageError(
                            f"Image dimensions must not exceed {MAX_IMAGE_PIXELS:,} pixels."
                        )
                    expected_format = "PNG" if extension == ".png" else "JPEG"
                    if image_format != expected_format:
                        raise InvalidImageError(
                            "The file extension does not match the image contents."
                        )
                    source.verify()

                with Image.open(io.BytesIO(image_bytes)) as source:
                    return source.convert("RGB")
        except InvalidImageError:
            raise
        except (
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
            UnidentifiedImageError,
            OSError,
            ValueError,
        ) as error:
            raise InvalidImageError("The uploaded file is not a valid image.") from error

    def _get_model(self) -> Any:
        if self._model is None:
            model_path = Path(__file__).resolve().parents[2] / "data" / "models"
            model_path.mkdir(parents=True, exist_ok=True)
            os.environ.setdefault("YOLO_CONFIG_DIR", str(model_path / "config"))
            from ultralytics import YOLO

            configured_model = os.environ.get("VISIONAI_YOLO_MODEL", "yolo11n.pt")
            weights = Path(configured_model)
            if not weights.is_absolute() and weights.parent == Path("."):
                weights = model_path / weights
            self._model = YOLO(str(weights))
        return self._model

    def predict(self, image: Image.Image) -> dict[str, Any]:
        with self._lock:
            model = self._get_model()
            results = model.predict(source=image, verbose=False)

        if not results:
            raise RuntimeError("The YOLO model returned no inference result.")

        result = results[0]
        detections: list[dict[str, Any]] = []
        if result.boxes is not None:
            boxes = result.boxes
            for coordinates, confidence, class_id in zip(
                boxes.xyxy.tolist(),
                boxes.conf.tolist(),
                boxes.cls.tolist(),
            ):
                x1, y1, x2, y2 = coordinates
                detections.append(
                    {
                        "name": str(result.names[int(class_id)]),
                        "confidence": round(float(confidence), 6),
                        "box": {
                            "x1": round(float(x1), 2),
                            "y1": round(float(y1), 2),
                            "x2": round(float(x2), 2),
                            "y2": round(float(y2), 2),
                        },
                    }
                )

        annotated = result.plot()
        annotated_image = Image.fromarray(annotated[:, :, ::-1].copy())
        output = io.BytesIO()
        annotated_image.save(output, format="JPEG", quality=90, optimize=True)
        return {
            "width": int(image.width),
            "height": int(image.height),
            "objects": detections,
            "annotated_image": output.getvalue(),
        }


object_detection_service = ObjectDetectionService()
