# qubitgyan-backend\library\api\v2\lexicon\application\utils\embeddings.py

import hashlib
import logging
import math
import os
import re
from functools import lru_cache

from django.db.models import QuerySet

from ...application.utils import normalize_text
from ...models import Word

logger = logging.getLogger(__name__)

EMBEDDING_DIM = int(os.environ.get("LEXICON_EMBEDDING_DIM", "384"))
_TOKEN_RE = re.compile(r"[a-z0-9']+", re.IGNORECASE)

try:
    from pgvector.django import CosineDistance  # type: ignore
except Exception:  # pragma: no cover
    CosineDistance = None


def _prefetched_word_queryset():
    return Word.objects.prefetch_related(
        "categories",
        "pronunciations",
        "meanings",
        "thesaurus_entries",
    )


def _normalize_parts(parts):
    return " ".join(str(part).strip() for part in parts if str(part or "").strip()).strip()


def build_word_embedding_text(word: Word) -> str:
    parts = [
        word.text,
        word.language,
        word.word_type,
        word.phonetic_text or "",
        word.source_api or "",
        word.source_reference or "",
    ]

    parts.extend(category.name for category in word.categories.all())

    for meaning in word.meanings.all():
        parts.append(meaning.part_of_speech or "")
        parts.append(meaning.definition or "")
        if meaning.example:
            parts.append(meaning.example)

    for pronunciation in word.pronunciations.all():
        parts.append(pronunciation.region or "")

    for entry in word.thesaurus_entries.all():
        parts.append(entry.related_word_text or "")
        parts.append(entry.relation_type or "")

    return _normalize_parts(parts)


@lru_cache(maxsize=1)
def _sentence_transformer_model():
    model_name = os.environ.get("LEXICON_EMBEDDING_MODEL", "").strip()
    if not model_name:
        return None

    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except Exception as exc:  # pragma: no cover
        logger.warning("SentenceTransformers unavailable: %s", exc)
        return None

    try:
        return SentenceTransformer(model_name)
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to load embedding model %s: %s", model_name, exc)
        return None


def _hash_embedding(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIM
    tokens = _TOKEN_RE.findall(normalize_text(text))

    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        weight = 1.0 + min(len(token), 12) / 12.0

        for offset in range(0, 32, 4):
            idx = int.from_bytes(digest[offset : offset + 4], "big") % EMBEDDING_DIM
            sign = 1.0 if digest[offset] % 2 == 0 else -1.0
            vector[idx] += sign * weight

    norm = math.sqrt(sum(value * value for value in vector))
    if norm:
        vector = [value / norm for value in vector]

    return [round(value, 6) for value in vector]


def _ensure_dimension(vector) -> list[float]:
    if vector is None:
        return [0.0] * EMBEDDING_DIM

    values = list(vector)
    if len(values) > EMBEDDING_DIM:
        values = values[:EMBEDDING_DIM]
    elif len(values) < EMBEDDING_DIM:
        values.extend([0.0] * (EMBEDDING_DIM - len(values)))

    return [float(value) for value in values]


def encode_text_to_vector(text: str) -> list[float]:
    text = normalize_text(text)
    if not text:
        return [0.0] * EMBEDDING_DIM

    model = _sentence_transformer_model()
    if model is not None:
        try:
            vector = model.encode(text, normalize_embeddings=True)
            if hasattr(vector, "tolist"):
                vector = vector.tolist()
            elif isinstance(vector, (list, tuple)) and vector and hasattr(vector[0], "tolist"):
                vector = vector[0].tolist()
            return _ensure_dimension(vector)
        except Exception as exc:  # pragma: no cover
            logger.warning("Embedding model failed, falling back to hashed vector: %s", exc)

    return _hash_embedding(text)


def search_words_by_similarity(query: str, language: str = "en", limit: int = 20):
    query = normalize_text(query)
    language = normalize_text(language) or "en"

    if not query or limit <= 0:
        return []

    lexical_fallback = list(
        _prefetched_word_queryset()
        .filter(language=language, is_active=True, text__icontains=query)
        .order_by("-search_count", "-updated_at")[:limit]
    )

    field = Word._meta.get_field("embedding")
    vector_backend_enabled = CosineDistance is not None and "pgvector" in field.__class__.__module__

    if not vector_backend_enabled:
        return lexical_fallback

    query_vector = encode_text_to_vector(query)
    if not any(query_vector):
        return lexical_fallback

    try:
        results = list(
            _prefetched_word_queryset()
            .filter(language=language, is_active=True, embedding__isnull=False)
            .annotate(distance=CosineDistance("embedding", query_vector))
            .order_by("distance", "-search_count", "-updated_at")[:limit]
        )
        return results or lexical_fallback
    except Exception as exc:  # pragma: no cover
        logger.warning("Vector search failed, using lexical fallback: %s", exc)
        return lexical_fallback