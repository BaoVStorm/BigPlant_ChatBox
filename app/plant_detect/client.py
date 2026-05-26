from __future__ import annotations

import base64
import json
import mimetypes
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any

from app.config import Settings, get_settings
from app.plant_detect.mock import build_mock_detection_result, normalize_label
from app.plant_detect.schemas import ChatImageInput, PlantDetectionResult


@dataclass
class PreparedImagePayload:
    content: bytes
    filename: str
    content_type: str


class BigPlantPlantDetectClient:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def detect(self, image: ChatImageInput) -> PlantDetectionResult:
        if self.settings.plant_detect_use_mock or image.mock_label:
            return build_mock_detection_result(image.mock_label)

        prepared = prepare_image_payload(image)
        url = build_detect_url(self.settings)
        body, content_type = build_multipart_body(prepared)

        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": content_type, "Accept": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.settings.plant_detect_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return parse_detection_payload(payload, source="remote")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
                result = parse_detection_payload(payload, source="remote")
                result.success = False
                result.error = payload.get("msg") or f"HTTP {exc.code}"
                return result
            except json.JSONDecodeError:
                return PlantDetectionResult(success=False, source="remote", error=f"HTTP {exc.code}: {raw}")
        except Exception as exc:
            return PlantDetectionResult(success=False, source="remote", error=str(exc))


def build_detect_url(settings: Settings) -> str:
    query = urllib.parse.urlencode(
        {
            "topk": settings.plant_detect_topk,
            "two_pass": str(settings.plant_detect_two_pass).lower(),
        }
    )
    return f"{settings.plant_detect_api_url}?{query}"


def prepare_image_payload(image: ChatImageInput) -> PreparedImagePayload:
    if image.data_url:
        content_type, content = decode_data_url(image.data_url)
        filename = image.filename or guess_filename(content_type)
        return PreparedImagePayload(content=content, filename=filename, content_type=image.content_type or content_type)

    if image.base64:
        content = decode_base64_content(image.base64)
        content_type = image.content_type or "image/jpeg"
        filename = image.filename or guess_filename(content_type)
        return PreparedImagePayload(content=content, filename=filename, content_type=content_type)

    if image.url:
        with urllib.request.urlopen(image.url, timeout=20) as response:
            content = response.read()
            content_type = image.content_type or response.headers.get_content_type() or "application/octet-stream"
            filename = image.filename or guess_filename(content_type)
            return PreparedImagePayload(content=content, filename=filename, content_type=content_type)

    raise RuntimeError("Image input must provide data_url, base64, url, or mock_label.")


def build_multipart_body(image: PreparedImagePayload) -> tuple[bytes, str]:
    boundary = f"----BigPlantBoundary{uuid.uuid4().hex}"
    lines = [
        f"--{boundary}".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{image.filename}"'.encode(),
        f"Content-Type: {image.content_type}".encode(),
        b"",
        image.content,
        f"--{boundary}--".encode(),
        b"",
    ]
    body = b"\r\n".join(lines)
    return body, f"multipart/form-data; boundary={boundary}"


def decode_data_url(data_url: str) -> tuple[str, bytes]:
    header, encoded = data_url.split(",", 1)
    content_type = "image/jpeg"
    if header.startswith("data:"):
        meta = header[5:]
        if ";" in meta:
            content_type = meta.split(";", 1)[0] or content_type
    return content_type, base64.b64decode(encoded)


def decode_base64_content(value: str) -> bytes:
    return base64.b64decode(value)


def guess_filename(content_type: str) -> str:
    extension = mimetypes.guess_extension(content_type) or ".jpg"
    return f"upload{extension}"


def parse_detection_payload(payload: dict[str, Any], source: str) -> PlantDetectionResult:
    detect_result = payload.get("detect_result") or {}
    label = payload.get("label")
    scientific_name_search = payload.get("scientific_name_search") or normalize_label(label or "") or None
    return PlantDetectionResult(
        success=bool(payload.get("success", True)),
        source=source,
        label=label,
        scientific_name_search=scientific_name_search,
        plant=payload.get("plant"),
        detect_result=detect_result,
        confidence=extract_confidence(detect_result),
        error=payload.get("msg"),
    )


def extract_confidence(detect_result: dict[str, Any]) -> float | None:
    pred = detect_result.get("pred") if isinstance(detect_result, dict) else None
    if isinstance(pred, dict):
        for key in ["confidence", "score", "prob", "probability"]:
            value = pred.get(key)
            if value is not None:
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
    return None
