# Copyright (c) 2025 Efstratios Goudelis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Lemonade Server embedder for local model inference on AMD Ryzen AI NPU.

Uses Lemonade Server's OpenAI-compatible API, which routes inference to
FLM (FastFlowLM) for NPU-accelerated vision-language tasks (Qwen3-VL)
and text embeddings (nomic-embed-text / Qwen3-Embedding).
"""

import base64
import cv2
import httpx
from dataclasses import dataclass
from typing import List, Optional

from .base_embedder import BaseEmbedder
from common.common import logger


@dataclass
class FLMConfig:
    """Configuration for Lemonade Server connection and models.

    Lemonade Server manages FLM as the NPU backend. Default port is 8000
    (Lemonade router), not 8080 (direct FLM).
    """

    base_url: str = "http://localhost:8000"
    embedding_model: str = "nomic-embed-text-v2-moe-GGUF"
    vision_model: str = "qwen3vl-it-4b-FLM"
    dimensions: int = 768
    timeout: float = 30.0

    @classmethod
    def from_env(cls) -> "FLMConfig":
        """Load configuration from environment variables."""
        import os
        return cls(
            base_url=os.environ.get("FLM_BASE_URL", "http://localhost:8000"),
            embedding_model=os.environ.get("FLM_EMBEDDING_MODEL", "nomic-embed-text-v2-moe-GGUF"),
            vision_model=os.environ.get("FLM_VISION_MODEL", "qwen3vl-it-4b-FLM"),
            dimensions=int(os.environ.get("FLM_DIMENSIONS", 768)),
            timeout=float(os.environ.get("FLM_TIMEOUT", 30.0)),
        )


class FLMEmbedder(BaseEmbedder):
    """Local embedder using Lemonade Server with FLM NPU backend.

    Lemonade Server routes inference to FLM on the AMD Ryzen AI NPU.
    Uses Qwen3-VL for vision-language tasks (frame description) and
    nomic-embed-text for text embeddings. Video chunks are embedded by
    extracting the middle frame, describing it with Qwen3-VL, and
    embedding the resulting text description.
    """

    def __init__(self, config: Optional[FLMConfig] = None):
        self.config = config or FLMConfig.from_env()
        self._client = httpx.Client(base_url=self.config.base_url, timeout=self.config.timeout)
        self._verify_connection()

    def _verify_connection(self):
        """Verify Lemonade Server is accessible and models are available."""
        try:
            resp = self._client.get("/v1/models")
            resp.raise_for_status()
            models = resp.json().get("data", [])
            model_ids = [m["id"] for m in models]
            logger.info(f"Lemonade Server connected. Available models: {model_ids}")
            if self.config.embedding_model not in model_ids:
                logger.warning(f"Embedding model '{self.config.embedding_model}' not found on Lemonade Server")
            if self.config.vision_model not in model_ids:
                logger.warning(f"Vision model '{self.config.vision_model}' not found on Lemonade Server")
        except Exception as e:
            logger.error(f"Lemonade Server connection failed: {e}")
            raise

    def embed_video_chunk(self, chunk_path: str, verbose: bool = False) -> List[float]:
        """Embed a video chunk by extracting key frames and getting embeddings.

        Args:
            chunk_path: Path to the video chunk file (MP4).
            verbose: If True, log additional processing details.

        Returns:
            List of floats representing the embedding vector.

        Raises:
            ValueError: If frame extraction fails.
        """
        # Extract middle frame
        cap = cv2.VideoCapture(chunk_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 2)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            raise ValueError(f"Could not extract frame from {chunk_path}")

        if verbose:
            logger.info(f"Extracted middle frame from {chunk_path} ({total_frames} frames total)")

        # Convert to text description via Qwen3-VL, then embed the text
        # This is the pragmatic approach since FLM's /v1/embeddings is text-only
        description = self._describe_frame(frame)
        if verbose:
            logger.info(f"Frame description: {description}")

        return self.embed_query(description, verbose)

    def _describe_frame(self, frame) -> str:
        """Use Qwen3-VL to describe a video frame.

        Args:
            frame: OpenCV frame (BGR numpy array).

        Returns:
            Text description of the frame.
        """
        # Encode frame as JPEG base64
        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        b64 = base64.b64encode(buffer).decode('utf-8')

        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": "Describe this image concisely in one sentence. Focus on sky, clouds, aircraft, or contrails."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
            ]
        }]

        resp = self._client.post("/v1/chat/completions", json={
            "model": self.config.vision_model,
            "messages": messages,
            "max_tokens": 100,
        })
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def embed_query(self, query_text: str, verbose: bool = False) -> List[float]:
        """Get embedding for text query using nomic-embed-text via Lemonade Server.

        Args:
            query_text: Text to embed.
            verbose: If True, log additional processing details.

        Returns:
            List of floats representing the embedding vector (768 dimensions).
        """
        resp = self._client.post("/v1/embeddings", json={
            "model": self.config.embedding_model,
            "input": query_text,
        })
        resp.raise_for_status()
        data = resp.json()
        embedding = data["data"][0]["embedding"]
        result = embedding[:self.config.dimensions]

        if verbose:
            logger.info(f"Query embedding: dims={len(result)}, model={self.config.embedding_model}")

        return result

    def dimensions(self) -> int:
        """Return the embedding dimension."""
        return self.config.dimensions

    def get_model_info(self) -> dict:
        """Get information about available models on FLM server.

        Returns:
            Dictionary with embedding_model, vision_model, and available_models.
        """
        try:
            resp = self._client.get("/v1/models")
            resp.raise_for_status()
            models = resp.json().get("data", [])
            model_ids = [m["id"] for m in models]
            return {
                "embedding_model": self.config.embedding_model,
                "vision_model": self.config.vision_model,
                "available_models": model_ids,
                "server_connected": True,
            }
        except Exception as e:
            return {
                "embedding_model": self.config.embedding_model,
                "vision_model": self.config.vision_model,
                "available_models": [],
                "server_connected": False,
                "error": str(e),
            }

    def close(self):
        """Close the HTTP client connection."""
        self._client.close()
