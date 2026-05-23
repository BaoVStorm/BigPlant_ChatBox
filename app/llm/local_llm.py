from __future__ import annotations

import json
import re
from typing import Any

from app.config import Settings, get_settings


class LocalLLM:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._model: Any | None = None
        self._load_error: str | None = None

    @property
    def is_available(self) -> bool:
        return self.settings.resolved_llm_model_path.exists()

    @property
    def load_error(self) -> str | None:
        return self._load_error

    def _load(self) -> Any:
        if self._model is not None:
            return self._model
        if not self.is_available:
            raise RuntimeError(f"Local LLM model file not found: {self.settings.resolved_llm_model_path}")
        try:
            from llama_cpp import Llama

            self._model = Llama(
                model_path=str(self.settings.resolved_llm_model_path),
                n_ctx=self.settings.llm_context_size,
                n_gpu_layers=self.settings.llm_gpu_layers,
                verbose=False,
            )
            return self._model
        except Exception as exc:  # pragma: no cover - depends on native llama.cpp runtime
            self._load_error = str(exc)
            raise RuntimeError(f"Failed to load local LLM: {exc}") from exc

    def generate(self, prompt: str, max_tokens: int | None = None, temperature: float | None = None) -> str:
        model = self._load()
        output = model(
            prompt,
            max_tokens=max_tokens or self.settings.llm_max_tokens,
            temperature=self.settings.llm_temperature if temperature is None else temperature,
            stop=["</s>", "<|im_end|>"],
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
