import io
import threading
import warnings
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

MAX_IMAGE_PIXELS = 40_000_000
ALLOWED_FORMATS = {"JPEG", "PNG"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
DEFAULT_TOP_K = 3
MAX_TOP_K = 5
MODEL_NAME = "efficientnet_b0_imagenet1k_v1"


class InvalidClassificationImage(ValueError):
    pass


class ImageClassificationService:
    def __init__(self) -> None:
        self._model: Any | None = None
        self._transform: Any | None = None
        self._labels: list[str] | None = None
        self._lock = threading.Lock()

    def decode_image(self, image_bytes: bytes, filename: str) -> Image.Image:
        extension = Path(filename).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise InvalidClassificationImage("Upload a JPG, JPEG, or PNG image.")

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(image_bytes)) as source:
                    image_format = source.format
                    width, height = source.size
                    if image_format not in ALLOWED_FORMATS:
                        raise InvalidClassificationImage(
                            "The uploaded file is not a JPG or PNG image."
                        )
                    if width < 1 or height < 1 or width * height > MAX_IMAGE_PIXELS:
                        raise InvalidClassificationImage(
                            f"Image dimensions must not exceed {MAX_IMAGE_PIXELS:,} pixels."
                        )
                    expected_format = "PNG" if extension == ".png" else "JPEG"
                    if image_format != expected_format:
                        raise InvalidClassificationImage(
                            "The file extension does not match the image contents."
                        )
                    source.verify()

                with Image.open(io.BytesIO(image_bytes)) as source:
                    return source.convert("RGB")
        except InvalidClassificationImage:
            raise
        except (
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
            UnidentifiedImageError,
            OSError,
            ValueError,
        ) as error:
            raise InvalidClassificationImage(
                "The uploaded file is not a valid image."
            ) from error

    def _get_model(self) -> Any:
        if self._model is None:
            from torchvision.models import EfficientNet_B0_Weights, efficientnet_b0

            weights = EfficientNet_B0_Weights.IMAGENET1K_V1
            model = efficientnet_b0(weights=weights).to("cpu").eval()
            self._transform = weights.transforms()
            self._labels = weights.meta["categories"]
            self._model = model
        return self._model

    def predict(
        self, image: Image.Image, top_k: int = DEFAULT_TOP_K
    ) -> list[dict[str, float | str]]:
        if not 1 <= top_k <= MAX_TOP_K:
            raise ValueError(f"top_k must be between 1 and {MAX_TOP_K}.")

        with self._lock:
            model = self._get_model()
            import torch

            if self._transform is None or self._labels is None:
                raise RuntimeError("The EfficientNet-B0 model metadata was not initialized.")
            input_tensor = self._transform(image).unsqueeze(0)
            with torch.inference_mode():
                probabilities = torch.softmax(model(input_tensor)[0], dim=0)
            scores, indices = torch.topk(probabilities, k=min(top_k, len(self._labels)))

        return [
            {"label": self._labels[index], "confidence": float(score)}
            for score, index in zip(scores.tolist(), indices.tolist())
        ]


image_classification_service = ImageClassificationService()
