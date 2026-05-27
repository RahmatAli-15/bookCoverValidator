from __future__ import annotations

import re

_MIN_TOKEN_LEN = 2


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def cleanup_duplicate_chars(text: str) -> str:
    # Compress excessive character repeats from OCR artifacts.
    return re.sub(r"(.)\1{3,}", r"\1\1", text)


def cleanup_punctuation(text: str) -> str:
    text = re.sub(r"[|~`_^]{2,}", " ", text)
    text = re.sub(r"\s*([,.;:!?])\s*", r"\1 ", text)
    return normalize_whitespace(text)


def remove_unreadable_fragments(text: str) -> str:
    tokens = text.split(" ")
    kept: list[str] = []
    for token in tokens:
        alnum = sum(ch.isalnum() for ch in token)
        if len(token) < _MIN_TOKEN_LEN and alnum <= 1:
            continue
        if alnum == 0:
            continue
        kept.append(token)
    return " ".join(kept).strip()


def is_major_typography_block(text: str, box_height: float, img_height: int) -> bool:
    lowered = text.lower()
    keyword_hit = any(k in lowered for k in ["author", "subtitle", "edition", "novel", "poems", "stories"])
    visual_prominent = box_height >= max(18.0, img_height * 0.018)
    text_len_ok = len(text) >= 8
    return keyword_hit or (visual_prominent and text_len_ok)


def clean_ocr_text(text: str) -> str:
    value = normalize_whitespace(text)
    value = cleanup_duplicate_chars(value)
    value = cleanup_punctuation(value)
    value = remove_unreadable_fragments(value)
    return normalize_whitespace(value)
