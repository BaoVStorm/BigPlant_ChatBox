from __future__ import annotations

import json
import re
from threading import Lock
from typing import Any

from app.config import Settings, get_settings


class LocalLLM:
    _shared_models: dict[str, Any] = {}
    _shared_lock = Lock()

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._load_error: str | None = None

    @property
    def is_available(self) -> bool:
        return self.settings.resolved_llm_model_path.exists()

    @property
    def load_error(self) -> str | None:
        return self._load_error

    def _load(self) -> Any:
        model_key = str(self.settings.resolved_llm_model_path)
        if model_key in self._shared_models:
            return self._shared_models[model_key]
        if not self.is_available:
            raise RuntimeError(f"Local LLM model file not found: {self.settings.resolved_llm_model_path}")

        with self._shared_lock:
            if model_key in self._shared_models:
                return self._shared_models[model_key]
            try:
                from llama_cpp import Llama

                model = Llama(
                    model_path=model_key,
                    n_ctx=self.settings.llm_context_size,
                    n_gpu_layers=self.settings.llm_gpu_layers,
                    verbose=False,
                )
                self._shared_models[model_key] = model
                return model
            except Exception as exc:  # pragma: no cover - depends on native llama.cpp runtime
                self._load_error = str(exc)
                raise RuntimeError(f"Failed to load local LLM: {exc}") from exc

    def generate(self, prompt: str, max_tokens: int | None = None, temperature: float | None = None) -> str:
        model = self._load()
        output = model(
            format_qwen_prompt(prompt),
            max_tokens=max_tokens or self.settings.llm_max_tokens,
            temperature=self.settings.llm_temperature if temperature is None else temperature,
            stop=["</s>", "<|im_end|>", "<|im_start|>", "\nUser:", "\nNgười dùng:", "\nAssistant:"],
        )
        return str(output["choices"][0]["text"]).strip()

    def generate_json(self, prompt: str) -> dict[str, Any]:
        text = self.generate(prompt, max_tokens=256, temperature=0.0)
        return parse_json_object(text)


def parse_json_object(text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


def format_qwen_prompt(prompt: str) -> str:
    return (
        "<|im_start|>system\n"
        "Bạn là trợ lý AI của BigPlant. Trả lời đúng yêu cầu, không tự tạo lượt hội thoại mới."
        "<|im_end|>\n"
        "<|im_start|>user\n"
        f"{prompt.strip()}"
        "<|im_end|>\n"
        "<|im_start|>assistant\n"
    )
