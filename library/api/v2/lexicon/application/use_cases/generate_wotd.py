# qubitgyan-backend/library/api/v2/lexicon/application/use_cases/generate_wotd.py

import logging
import random
import uuid
from datetime import timedelta

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone

from ...application.constants import (
    MIN_MEANINGS_FOR_SELECTION,
    NIGHTLY_IMPORT_RELATED_LIMIT,
    NIGHTLY_IMPORT_SEED_LIMIT,
    WOTD_BLACKLIST_DAYS,
    WOTD_MIN_DIFFICULTY_SCORE,
)
from ...application.utils import normalize_text
from ...models import Word, WordOfTheDay, WordUsage
from .search_word import fetch_and_store_word, prime_remote_dictionary_inventory

logger = logging.getLogger(__name__)

_LOCK_TIMEOUT_SECONDS = 60


def _has_items(value) -> bool:
    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    size = getattr(value, "size", None)
    if isinstance(size, int):
        return size > 0

    try:
        return len(value) > 0
    except TypeError:
        return bool(value)
    except ValueError:
        size = getattr(value, "size", None)
        if isinstance(size, int):
            return size > 0
        return True


def _is_missing_embedding(value) -> bool:
    if value is None:
        return True

    if isinstance(value, str):
        return not value.strip()

    size = getattr(value, "size", None)
    if isinstance(size, int):
        return size == 0

    try:
        return len(value) == 0
    except TypeError:
        return False
    except ValueError:
        size = getattr(value, "size", None)
        if isinstance(size, int):
            return size == 0
        return False


def _normalize_id_list(word_ids):
    if word_ids is None:
        return []

    if isinstance(word_ids, (str, bytes)):
        return [word_ids]

    try:
        return list(word_ids)
    except TypeError:
        return [word_ids]


def _acquire_lock(lock_key: str) -> str | None:
    token = uuid.uuid4().hex
    if cache.add(lock_key, token, timeout=_LOCK_TIMEOUT_SECONDS):
        return token
    return None


def _release_lock(lock_key: str, token: str | None) -> None:
    if not token:
        return
    if cache.get(lock_key) == token:
        cache.delete(lock_key)


def _queue_embedding_refresh(word_ids):
    ids = _normalize_id_list(word_ids)
    if not ids:
        return

    from django.conf import settings

    if not settings.ENABLE_ASYNC_TASKS:
        from ...application.utils.embeddings import build_word_embedding_text, encode_text_to_vector

        for word_id in ids:
            try:
                word = Word.objects.prefetch_related(
                    "categories",
                    "pronunciations",
                    "meanings",
                    "thesaurus_entries",
                ).get(pk=word_id)
            except Word.DoesNotExist:
                continue

            vector = encode_text_to_vector(build_word_embedding_text(word))
            Word.objects.filter(pk=word.pk).update(embedding=vector if any(vector) else None)
        return

    from ...tasks import refresh_word_embedding

    transaction.on_commit(
        lambda ids=ids: [
            refresh_word_embedding.delay(str(word_id))
            for word_id in ids
        ]
    )


def _prefetched_wotd_queryset():
    return (
        WordOfTheDay.objects.select_related("word")
        .prefetch_related(
            "word__categories",
            "word__pronunciations",
            "word__meanings",
            "word__thesaurus_entries",
        )
    )


def _existing_wotd(date_value):
    return _prefetched_wotd_queryset().filter(date=date_value).first()


def _recent_blacklist_ids(date_value, days: int):
    cutoff = date_value - timedelta(days=days)
    return (
        WordUsage.objects.filter(used_on__gte=cutoff)
        .values_list("word_id", flat=True)
        .distinct()
    )


def _previously_used_ids(usage_type: str):
    return set(
        WordUsage.objects.filter(usage_type=usage_type)
        .values_list("word_id", flat=True)
        .distinct()
    )


def _candidate_queryset():
    return (
        Word.objects.filter(language="en", is_active=True, is_sophisticated=True)
        .annotate(
            meaning_count=Count("meanings", distinct=True),
            pronunciation_count=Count("pronunciations", distinct=True),
            thesaurus_count=Count("thesaurus_entries", distinct=True),
        )
        .filter(
            meaning_count__gte=MIN_MEANINGS_FOR_SELECTION,
            difficulty_score__gte=WOTD_MIN_DIFFICULTY_SCORE,
        )
        .order_by("-difficulty_score", "-meaning_count", "-thesaurus_count", "-created_at")
    )


def _top_up_with_sophisticated_seeds(blacklist_ids, rng):
    prime_remote_dictionary_inventory(
        language="en",
        limit=max(NIGHTLY_IMPORT_SEED_LIMIT, 20),
        related_depth=2,
        related_limit=NIGHTLY_IMPORT_RELATED_LIMIT,
    )

    candidates = list(
        _candidate_queryset()
        .exclude(id__in=blacklist_ids)
        .only("id", "text", "difficulty_score", "embedding")[:200]
    )
    if not candidates:
        return None

    return rng.choice(candidates)


@transaction.atomic
def generate_word_of_the_day(date=None):
    target_date = date or timezone.localdate()
    rng = random.Random(str(target_date))
    lock_key = f"lock:wotd:{target_date.isoformat()}"
    lock_token = _acquire_lock(lock_key)

    if lock_token is None:
        return _existing_wotd(target_date)

    try:
        existing = _existing_wotd(target_date)
        if existing:
            return existing

        blacklist_ids = set(_recent_blacklist_ids(target_date, WOTD_BLACKLIST_DAYS))

        candidates = list(_candidate_queryset().exclude(id__in=blacklist_ids)[:200])
        if not candidates:
            prime_remote_dictionary_inventory(
                language="en",
                limit=max(NIGHTLY_IMPORT_SEED_LIMIT, 20),
                related_depth=2,
                related_limit=NIGHTLY_IMPORT_RELATED_LIMIT,
            )
            candidates = list(_candidate_queryset().exclude(id__in=blacklist_ids)[:200])

        word = rng.choice(candidates) if candidates else None

        if not word:
            word = _top_up_with_sophisticated_seeds(blacklist_ids, rng)

        if not word:
            raise ValueError("Unable to generate a word of the day without repeating the last 15 days.")

        try:
            wotd, _ = WordOfTheDay.objects.update_or_create(date=target_date, defaults={"word": word})
        except IntegrityError:
            wotd = WordOfTheDay.objects.get(date=target_date)
            if wotd.word_id != word.pk:
                wotd.word = word
                wotd.save(update_fields=["word"])

        WordUsage.objects.filter(usage_type="WOTD", used_on=target_date).delete()
        WordUsage.objects.create(
            word=word,
            usage_type="WOTD",
            used_on=target_date,
        )

        if _is_missing_embedding(getattr(word, "embedding", None)):
            _queue_embedding_refresh([word.pk])

        return _prefetched_wotd_queryset().get(pk=wotd.pk)

    finally:
        _release_lock(lock_key, lock_token)
        
        
