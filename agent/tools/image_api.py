"""DALL-E 3 / Stable Diffusion API wrapper for image generation."""

import base64
import logging
from typing import Optional

import httpx

logger = logging.getLogger("social-agent")


class ImageAPIClient:
    """Wrapper around image generation APIs."""

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        sd_api_url: Optional[str] = None,
    ):
        self.openai_api_key = openai_api_key
        self.sd_api_url = sd_api_url

    async def generate(self, prompt: str, size: str = "1792x1024") -> bytes:
        """Generate an image from a text prompt. Returns raw PNG bytes."""
        if self.openai_api_key:
            return await self._generate_dalle(prompt, size)
        elif self.sd_api_url:
            return await self._generate_sd(prompt, size)
        else:
            raise ValueError(
                "No image API configured (set OPENAI_API_KEY or SD_API_URL)"
            )

    async def _generate_dalle(self, prompt: str, size: str) -> bytes:
        # DALL-E 3 only supports specific sizes; use closest match
        dalle_size = self._closest_dalle_size(size)
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                "https://api.openai.com/v1/images/generations",
                headers={"Authorization": f"Bearer {self.openai_api_key}"},
                json={
                    "model": "dall-e-3",
                    "prompt": prompt,
                    "n": 1,
                    "size": dalle_size,
                    "response_format": "b64_json",
                },
            )
            resp.raise_for_status()
            b64_data = resp.json()["data"][0]["b64_json"]
            return base64.b64decode(b64_data)

    async def _generate_sd(self, prompt: str, size: str) -> bytes:
        w, h = size.split("x")
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{self.sd_api_url}/sdapi/v1/txt2img",
                json={"prompt": prompt, "width": int(w), "height": int(h)},
            )
            resp.raise_for_status()
            b64_data = resp.json()["images"][0]
            return base64.b64decode(b64_data)

    @staticmethod
    def _closest_dalle_size(size: str) -> str:
        """Map requested size to nearest DALL-E 3 supported size."""
        supported = ["1024x1024", "1024x1792", "1792x1024"]
        w, h = map(int, size.split("x"))
        ratio = w / h
        if ratio > 1.3:
            return "1792x1024"  # landscape
        elif ratio < 0.77:
            return "1024x1792"  # portrait
        return "1024x1024"  # square-ish
