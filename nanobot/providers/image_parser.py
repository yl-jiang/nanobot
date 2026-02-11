"""Image parsing provider using vLLM (OpenAI-compatible API)."""

import base64
import mimetypes
from pathlib import Path

import re

from loguru import logger

try:
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class VLLMImageProvider:
    """Parse images using a vLLM OpenAI-compatible chat completions endpoint."""

    def __init__(
        self,
        api_base: str | None,
        model: str,
        api_key: str | None = None,
        prompt: str = "使用markdown语法，将图片中识别到的文字转换为markdown格式输出。",
        system_prompt: str = "You are a helpful assistant.",
        max_tokens: int = 4096,
        timeout_seconds: int = 60,
    ) -> None:
        self.api_base = api_base
        self.model = model
        self.prompt = prompt
        self.system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.timeout_seconds = timeout_seconds

        if not OPENAI_AVAILABLE:
            logger.error("openai package not installed. Run: pip install openai")
            self._client = None
        else:
            base_url = api_base.rstrip("/") if api_base else ""
            if not base_url.endswith("/v1"):
                base_url = f"{base_url}/v1"
            self._client = AsyncOpenAI(
                api_key=api_key or "EMPTY",
                base_url=base_url,
                timeout=timeout_seconds,
            )

    async def parse(self, image_path: str | Path, instruction: str | None = None) -> str:
        """Parse an image and return text description."""
        if not self._client or not self.api_base or not self.model:
            logger.warning("VLLM image parser not configured")
            return ""

        path = Path(image_path)
        if not path.exists():
            logger.error(f"Image file not found: {image_path}")
            return ""

        mime, _ = mimetypes.guess_type(str(path))
        if not mime or not mime.startswith("image/"):
            mime = "image/png"

        try:
            b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
            image_url = f"data:{mime};base64,{b64}"
            prompt = instruction.strip() if instruction and instruction.strip() else self.prompt

            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": image_url}},
                        ],
                    },
                ],
                max_tokens=self.max_tokens,
            )
            content = response.choices[0].message.content if response.choices else ""
            # Clean up model-specific special tokens (e.g. GLM <|begin_of_box|>)
            content = re.sub(r"<\|[a-z_]+\|>", "", content or "")
            return content.strip()
        except Exception as e:
            logger.error(f"VLLM image parse error: {e}")
            return ""
