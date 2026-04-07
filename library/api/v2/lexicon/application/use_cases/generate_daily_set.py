# qubitgyan-backend/library/api/v2/lexicon/application/use_cases/generate_daily_set.py

import logging
import random
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from ...application.constants import DEFAULT_PRACTICE_COUNT, PRACTICE_BLACKLIST_DAYS, SEED_WORDS
from ...models import DailyPracticeSet, Word, WordUsage

logger = logging.getLogger(__name__)

_LOCK_TIMEOUT_SECONDS = 60


def _acquire_lock(lock_key: str):
    token = uuid.uuid4().hex
    if cache.add(lock_key, token, timeout=_LOCK_TIMEOUT_SECONDS):
        return token
    return None


def _release_lock(lock_key: str, token: str | None):
    if not token:
        return
    if cache.get(lock_key) == token:
        cache.delete(lock_key)


def _queue_embedding_refresh(word_ids):
    if not word_ids:
        return

    if not settings.ENABLE_ASYNC_TASKS:
        logger.warning("Skipping embedding refresh task dispatch because async tasks are disabled.")
        return

    from ...tasks import refresh_word_embedding

    ids = [str(word_id) for word_id in word_ids]

    def _dispatch(ids_to_dispatch):
        for word_id in ids_to_dispatch:
            try:
                refresh_word_embedding.delay(word_id)
            except Exception as exc:
                logger.warning(
                    "Failed to dispatch refresh_word_embedding task for word_id=%s: %s",
                    word_id,
                    exc,
                )

    transaction.on_commit(lambda ids=ids: _dispatch(ids))


def _recent_blacklist_ids(today, days: int):
    cutoff = today - timedelta(days=days)
    return (
        WordUsage.objects.filter(used_on__gte=cutoff)
        .values_list("word_id", flat=True)
        .distinct()
    )


def _prefetched_practice_set_queryset():
    return DailyPracticeSet.objects.prefetch_related(
        "words__categories",
        "words__pronunciations",
        "words__meanings",
        "words__thesaurus_entries",
    )


def _existing_practice_set(today):
    return _prefetched_practice_set_queryset().filter(date=today).first()


def _active_word_count(language: str = "en") -> int:
    return Word.objects.filter(language=language, is_active=True).count()


def _top_up_seed_words(minimum_count: int, language: str = "en"):
    """
    Populate local lexicon inventory using configured seed words.

    This function is intended for background jobs only and may perform
    remote API lookups through fetch_and_store_word.
    """
    if _active_word_count(language=language) >= minimum_count:
        return

    from .search_word import fetch_and_store_word

    for seed in SEED_WORDS:
        if _active_word_count(language=language) >= minimum_count:
            break

        try:
            fetch_and_store_word(seed, language=language, increment_search_count=False)
        except Exception as exc:
            logger.warning("Seed top-up failed for word=%s language=%s: %s", seed, language, exc)


@transaction.atomic
def generate_daily_practice_set(
    date=None,
    count: int = DEFAULT_PRACTICE_COUNT,
    seed_top_up: bool = False,
):
    today = date or timezone.localdate()
    rng = random.Random(str(today))

    lock_key = f"lock:practice_set:{today.isoformat()}"
    lock_token = _acquire_lock(lock_key)

    if lock_token is None:
        return _existing_practice_set(today)

    try:
        existing = _existing_practice_set(today)
        if existing:
            return existing

        if seed_top_up:
            _top_up_seed_words(minimum_count=count)

        blacklist_ids = set(_recent_blacklist_ids(today, PRACTICE_BLACKLIST_DAYS))

        available_words = list(
            Word.objects.filter(language="en", is_active=True)
            .exclude(id__in=blacklist_ids)
            .only("id", "text", "difficulty_score", "embedding")
        )

        if len(available_words) < count:
            raise ValueError("Not enough words available to generate a practice set.")

        selected = rng.sample(available_words, count)

        try:
            practice_set, _ = DailyPracticeSet.objects.get_or_create(date=today)
        except IntegrityError:
            practice_set = DailyPracticeSet.objects.get(date=today)

        practice_set.words.set(selected)

        WordUsage.objects.bulk_create(
            [WordUsage(word=word, usage_type="PRACTICE", used_on=today) for word in selected],
            ignore_conflicts=True,
        )

        missing_embedding_ids = [
            word.pk for word in selected if getattr(word, "embedding", None) in (None, [], {})
        ]
        _queue_embedding_refresh(missing_embedding_ids)

        return _prefetched_practice_set_queryset().get(pk=practice_set.pk)

    finally:
        _release_lock(lock_key, lock_token)

        
