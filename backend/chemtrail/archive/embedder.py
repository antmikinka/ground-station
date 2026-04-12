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

"""Embedder factory — selects and caches the active backend.

Provides backward-compatible top-level functions (embed_video_chunk,
embed_query) that delegate to whichever backend is currently active.
Re-exports error classes from gemini_embedder for existing import sites.
"""

from .base_embedder import BaseEmbedder
from .gemini_embedder import GeminiAPIKeyError, GeminiQuotaError  # noqa: F401

_current_embedder: BaseEmbedder | None = None


def get_embedder(backend: str = "gemini", **kwargs) -> BaseEmbedder:
    """Factory to get or create the active embedder."""
    global _current_embedder
    if _current_embedder is None:
        if backend == "gemini":
            from .gemini_embedder import GeminiEmbedder
            _current_embedder = GeminiEmbedder()
        elif backend == "flm":
            from .flm_embedder import FLMEmbedder
            _current_embedder = FLMEmbedder()
        elif backend == "local":
            raise NotImplementedError(
                "Local embedding (Qwen3-VL) requires optional dependencies: "
                "torch, torchvision, transformers, accelerate, qwen-vl-utils, torchcodec. "
                "Install with: pip install torch transformers accelerate qwen-vl-utils torchcodec"
            )
        else:
            raise ValueError(f"Unknown backend: {backend}")
    return _current_embedder


def reset_embedder():
    """Reset the cached embedder (for switching backends)."""
    global _current_embedder
    _current_embedder = None


# Convenience functions — backward compatible with existing callers
def embed_video_chunk(chunk_path: str, verbose: bool = False) -> list[float]:
    return get_embedder().embed_video_chunk(chunk_path, verbose=verbose)


def embed_query(query_text: str, verbose: bool = False) -> list[float]:
    return get_embedder().embed_query(query_text, verbose=verbose)
