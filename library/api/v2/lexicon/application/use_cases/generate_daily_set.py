# qubitgyan-backend/library/api/v2/lexicon/application/use_cases/generate_daily_set.py

import logging
import random
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from ...application.constants import (
    DEFAULT_PRACTICE_COUNT,
    MAX_PRACTICE_COUNT,
    MIN_PRACTICE_COUNT,
    PRACTICE_BLACKLIST_DAYS,
    PRACTICE_IMPORTANCE_THRESHOLD,
    SEED_WORDS,
)
from ...application.utils import normalize_text
from ...models import DailyPracticeSet, Word, WordUsage

logger = logging.getLogger(__name__)

_LOCK_TIMEOUT_SECONDS = 60
_PRIORITY_SOURCES = {"FDA", "MW", "MIXED"}


def _normalize_count(count):
    try:
        parsed_count = int(count)
    except (TypeError, ValueError):
        parsed_count = DEFAULT_PRACTICE_COUNT
    return max(MIN_PRACTICE_COUNT, min(MAX_PRACTICE_COUNT, parsed_count))


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


def _prefetched_practice_set_queryset():
    return DailyPracticeSet.objects.prefetch_related(
        "words__categories",
        "words__pronunciations",
        "words__meanings",
        "words__thesaurus_entries",
    )


def _existing_practice_set(target_date):
    return _prefetched_practice_set_queryset().filter(date=target_date).first()


def _top_up_seed_words(minimum_count: int, language: str = "en"):
    """
    Grow the local lexicon inventory gradually, one seed at a time.
    This keeps the midnight job predictable on free-tier infrastructure.
    """
    from .search_word import fetch_and_store_word

    active_count = Word.objects.filter(language=language, is_active=True).count()
    if active_count >= minimum_count:
        return

    existing_texts = {
        normalize_text(text)
        for text in Word.objects.filter(language=language).values_list("text", flat=True)
    }

    seeds = [normalize_text(word) for word in SEED_WORDS if len(normalize_text(word)) >= 8]
    random.shuffle(seeds)

    for seed in seeds:
        if active_count >= minimum_count:
            break

        if seed in existing_texts:
            continue

        try:
            new_word, _ = fetch_and_store_word(seed, language=language, increment_search_count=False)
        except Exception as exc:
            logger.warning("Seed top-up failed for word=%s language=%s: %s", seed, language, exc)
            continue

        if new_word:
            existing_texts.add(new_word.text)
            active_count += 1


def _usage_ids_for_date(usage_type: str, target_date, *, days_back: int):
    cutoff = target_date - timedelta(days=days_back)
    return set(
        WordUsage.objects.filter(
            usage_type=usage_type,
            used_on__gte=cutoff,
        ).values_list("word_id", flat=True)
    )


def _word_importance_key(word, recent_ids, important_threshold: float):
    is_important = (
        word.is_sophisticated
        or word.difficulty_score >= important_threshold
        or len(word.text) >= 7
    )
    source_bonus = 1 if word.source_api in _PRIORITY_SOURCES else 0
    recent_penalty = -1 if word.pk in recent_ids else 0

    return (
        1 if is_important else 0,
        round(float(word.difficulty_score or 0.0), 3),
        source_bonus,
        min(len(word.text), 20),
        recent_penalty,
        -min(int(word.search_count or 0), 1000),
        word.text,
    )


def _select_words_for_practice(target_date, count: int, allow_remote_fetch: bool):
    yesterday_ids = _usage_ids_for_date("PRACTICE", target_date, days_back=1)
    recent_ids = _usage_ids_for_date("PRACTICE", target_date, days_back=PRACTICE_BLACKLIST_DAYS)

    base_words = list(
        Word.objects.filter(language="en", is_active=True)
        .exclude(pk__in=yesterday_ids)
        .only("id", "text", "difficulty_score", "embedding", "is_sophisticated", "search_count", "source_api")
    )

    important_words = [
        word for word in base_words if _word_importance_key(word, recent_ids, PRACTICE_IMPORTANCE_THRESHOLD)[0] == 1
    ]
    candidate_words = important_words if len(important_words) >= count else base_words

    ordered = sorted(
        candidate_words,
        key=lambda word: _word_importance_key(word, recent_ids, PRACTICE_IMPORTANCE_THRESHOLD),
        reverse=True,
    )

    if len(ordered) >= count:
        return ordered[:count]

    if allow_remote_fetch:
        _top_up_seed_words(minimum_count=count, language="en")
        base_words = list(
            Word.objects.filter(language="en", is_active=True)
            .exclude(pk__in=yesterday_ids)
            .only("id", "text", "difficulty_score", "embedding", "is_sophisticated", "search_count", "source_api")
        )
        important_words = [
            word for word in base_words if _word_importance_key(word, recent_ids, PRACTICE_IMPORTANCE_THRESHOLD)[0] == 1
        ]
        candidate_words = important_words if len(important_words) >= count else base_words
        ordered = sorted(
            candidate_words,
            key=lambda word: _word_importance_key(word, recent_ids, PRACTICE_IMPORTANCE_THRESHOLD),
            reverse=True,
        )

    return ordered[:count]


@transaction.atomic
def generate_daily_practice_set(
    date=None,
    count: int = DEFAULT_PRACTICE_COUNT,
    seed_top_up: bool = False,
    allow_remote_fetch: bool = False,
):
    target_date = date or timezone.localdate()
    count = _normalize_count(count)

    lock_key = f"lock:practice_set:{target_date.isoformat()}"
    lock_token = _acquire_lock(lock_key)

    if lock_token is None:
        return _existing_practice_set(target_date)

    try:
        existing = _existing_practice_set(target_date)
        if existing:
            return existing

        if seed_top_up and allow_remote_fetch:
            _top_up_seed_words(minimum_count=count, language="en")

        selected = _select_words_for_practice(
            target_date,
            count=count,
            allow_remote_fetch=allow_remote_fetch,
        )

        if len(selected) < count:
            raise ValueError("Unable to build a complete practice set from the available important words.")

        try:
            practice_set, _ = DailyPracticeSet.objects.get_or_create(date=target_date)
        except IntegrityError:
            practice_set = DailyPracticeSet.objects.get(date=target_date)

        practice_set.words.set(selected)

        WordUsage.objects.bulk_create(
            [WordUsage(word=word, usage_type="PRACTICE", used_on=target_date) for word in selected],
            ignore_conflicts=True,
        )

        missing_embedding_ids = [
            word.pk for word in selected if getattr(word, "embedding", None) in (None, [], {})
        ]
        _queue_embedding_refresh(missing_embedding_ids)

        return _prefetched_practice_set_queryset().get(pk=practice_set.pk)

    finally:
        _release_lock(lock_key, lock_token)
