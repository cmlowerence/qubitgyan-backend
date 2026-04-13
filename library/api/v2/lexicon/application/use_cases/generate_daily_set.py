import logging
import random
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone

from ...application.constants import (
    DEFAULT_PRACTICE_COUNT,
    MIN_MEANINGS_FOR_SELECTION,
    PRACTICE_BLACKLIST_DAYS,
    PRACTICE_MAX_COUNT,
    PRACTICE_MIN_COUNT,
    PRACTICE_MIN_DIFFICULTY_SCORE,
)
from ...models import DailyPracticeSet, Word, WordUsage

logger = logging.getLogger(__name__)

_LOCK_TIMEOUT_SECONDS = 60


def _acquire_lock(lock_key: str):
    token = uuid.uuid4().hex
    if cache.add(lock_key, token, timeout=_LOCK_TIMEOUT_SECONDS):
        return token
    return None


def _release_lock(lock_key: str, token: str | None):
    if token and cache.get(lock_key) == token:
        cache.delete(lock_key)


def _prefetched_practice_set_queryset():
    return DailyPracticeSet.objects.prefetch_related(
        "words__categories",
        "words__pronunciations",
        "words__meanings",
        "words__thesaurus_entries",
    )


def _existing_practice_set(today):
    return _prefetched_practice_set_queryset().filter(date=today).first()


def _recent_blacklist_ids(today, days: int):
    cutoff = today - timedelta(days=days)
    return (
        WordUsage.objects.filter(used_on__gte=cutoff)
        .values_list("word_id", flat=True)
        .distinct()
    )


def _candidate_queryset(language: str = "en"):
    return (
        Word.objects.filter(language=language, is_active=True)
        .annotate(
            meaning_count=Count("meanings", distinct=True),
            pronunciation_count=Count("pronunciations", distinct=True),
            thesaurus_count=Count("thesaurus_entries", distinct=True),
        )
        .filter(
            meaning_count__gte=MIN_MEANINGS_FOR_SELECTION,
            difficulty_score__gte=PRACTICE_MIN_DIFFICULTY_SCORE,
        )
        .order_by("-difficulty_score", "-meaning_count", "-thesaurus_count", "-created_at")
    )


def _queue_embedding_refresh(word_ids):
    ids = [str(word_id) for word_id in (word_ids or [])]
    if not ids:
        return

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

    transaction.on_commit(lambda: [refresh_word_embedding.delay(word_id) for word_id in ids])


def _select_practice_words(today, count: int):
    blacklist_ids = set(_recent_blacklist_ids(today, PRACTICE_BLACKLIST_DAYS))
    candidates = list(_candidate_queryset(language="en").exclude(id__in=blacklist_ids)[:250])

    if len(candidates) < count:
        return []

    rng = random.Random(str(today))
    rng.shuffle(candidates)
    return candidates[:count]


def generate_daily_practice_set(
    date=None,
    count: int = DEFAULT_PRACTICE_COUNT,
    *,
    allow_prime: bool = False,
    prime_batch_size: int = 1,
):
    if count < PRACTICE_MIN_COUNT or count > PRACTICE_MAX_COUNT:
        raise ValueError(
            f"Practice count must be between {PRACTICE_MIN_COUNT} and {PRACTICE_MAX_COUNT}."
        )

    today = date or timezone.localdate()
    lock_key = f"lock:practice_set:{today.isoformat()}"
    lock_token = _acquire_lock(lock_key)

    if lock_token is None:
        return _existing_practice_set(today)

    try:
        existing = _existing_practice_set(today)
        if existing:
            return existing

        selected = _select_practice_words(today, count=count)

        if len(selected) < count and allow_prime:
            from .search_word import prime_remote_dictionary_inventory

            prime_remote_dictionary_inventory(
                language="en",
                limit=max(1, prime_batch_size),
                related_depth=0,
                related_limit=0,
                import_related=False,
                force_enrich=False,
            )
            selected = _select_practice_words(today, count=count)

        if len(selected) < count:
            return None

        try:
            practice_set, _ = DailyPracticeSet.objects.get_or_create(date=today)
        except IntegrityError:
            practice_set = DailyPracticeSet.objects.get(date=today)

        practice_set.words.set(selected)

        WordUsage.objects.filter(usage_type="PRACTICE", used_on=today).delete()
        WordUsage.objects.bulk_create(
            [WordUsage(word=word, usage_type="PRACTICE", used_on=today) for word in selected],
            ignore_conflicts=True,
        )

        missing_embedding_ids = [
            word.pk for word in selected if not getattr(word, "embedding", None)
        ]
        _queue_embedding_refresh(missing_embedding_ids)

        return _prefetched_practice_set_queryset().get(pk=practice_set.pk)

    finally:
        _release_lock(lock_key, lock_token)