"""
Tests for vision / image understanding pipeline.
"""

from app.core.domain import Chunk
from app.infrastructure.vision_llm import VisionLLM


def test_vision_llm_defaults():
    v = VisionLLM()
    assert v.model == "nvidia/nemotron-3.5-super-vl:free"
    assert v.base_url == "https://openrouter.ai/api/v1"
    assert v.language == "fa"


def test_chunk_image_fields():
    c = Chunk(
        text="توضیح مثلث",
        chunk_type="image",
        image_ref="doc_page_1_img_0",
    )
    assert c.chunk_type == "image"
    assert c.image_ref == "doc_page_1_img_0"
    assert c.text == "توضیح مثلث"


def test_chunk_defaults_unchanged():
    c = Chunk(text="متن عادی")
    assert c.chunk_type == "text"
    assert c.image_ref is None
