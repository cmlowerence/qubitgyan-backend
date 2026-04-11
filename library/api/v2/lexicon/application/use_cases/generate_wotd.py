# qubitgyan-backend/library/api/v2/lexicon/application/use_cases/generate_wotd.py

import logging
import random
import uuid
from datetime import timedelta

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from ...application.constants import SEED_WORDS, WOTD_BLACKLIST_DAYS, WOTD_IMPORTANCE_THRESHOLD
from ...application.utils import is_sophisticated_word, normalize_text
from ...models import Word, WordOfTheDay, WordUsage
from .search_word import fetch_and_store_word

logger = logging.getLogger(__name__)

_LOCK_TIMEOUT_SECONDS = 60
_PRIORITY_SOURCES = {"FDA", "MW", "MIXED"}


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
    if not word_ids:
        return

    from ...tasks import refresh_word_embedding

    ids = [str(word_id) for word_id in word_ids]
    transaction.on_commit(lambda ids=ids: [refresh_word_embedding.delay(word_id) for word_id in ids])


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


def _usage_ids_for_date(usage_type: str, target_date, *, days_back: int):
    cutoff = target_date - timedelta(days=days_back)
    return set(
        WordUsage.objects.filter(
            usage_type=usage_type,
            used_on__gte=cutoff,
        ).values_list("word_id", flat=True)
    )


def _candidate_priority(word, recent_ids):
    is_important = (
        word.is_sophisticated
        or word.difficulty_score >= WOTD_IMPORTANCE_THRESHOLD
        or len(word.text) >= 8
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


def _top_up_with_sophisticated_seeds(blacklist_ids, rng):
    existing_texts = {
        normalize_text(text)
        for text in Word.objects.filter(language="en", is_active=True).values_list("text", flat=True)
    }
    seeds = [normalize_text(word) for word in SEED_WORDS if len(normalize_text(word)) >= 8]
    rng.shuffle(seeds)

    for seed in seeds:
        if seed in existing_texts:
            continue

        new_word, _ = fetch_and_store_word(seed, "en", increment_search_count=False)
        if (
            new_word
            and new_word.pk not in blacklist_ids
            and is_sophisticated_word(new_word.text, new_word.difficulty_score)
        ):
            return new_word

    return None


@transaction.atomic
def generate_word_of_the_day(date=None, allow_remote_fetch: bool = True):
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

        yesterday_ids = _usage_ids_for_date("WOTD", target_date, days_back=1)
        recent_ids = _usage_ids_for_date("WOTD", target_date, days_back=WOTD_BLACKLIST_DAYS)

        candidates = list(
            Word.objects.filter(language="en", is_active=True)
            .exclude(pk__in=yesterday_ids)
            .only("id", "text", "difficulty_score", "embedding", "is_sophisticated", "search_count", "source_api")
            .order_by("-difficulty_score", "-created_at")[:200]
        )

        important_candidates = [word for word in candidates if _candidate_priority(word, recent_ids)[0] == 1]
        ordered_candidates = important_candidates if important_candidates else candidates

        ordered_candidates = sorted(
            ordered_candidates,
            key=lambda word: _candidate_priority(word, recent_ids),
            reverse=True,
        )

        word = ordered_candidates[0] if ordered_candidates else None

        if not word and allow_remote_fetch:
            blacklist_ids = set(recent_ids) | set(yesterday_ids)
            word = _top_up_with_sophisticated_seeds(blacklist_ids, rng)

        if not word and allow_remote_fetch:
            fallback = list(
                Word.objects.filter(language="en", is_active=True)
                .exclude(pk__in=yesterday_ids)
                .only("id", "text", "difficulty_score", "embedding", "is_sophisticated", "search_count", "source_api")
                .order_by("-difficulty_score", "-created_at")[:200]
            )
            fallback = sorted(
                fallback,
                key=lambda item: _candidate_priority(item, recent_ids),
                reverse=True,
            )
            word = fallback[0] if fallback else None

        if not word:
            raise ValueError("Unable to generate a word of the day.")

        try:
            wotd, _ = WordOfTheDay.objects.update_or_create(date=target_date, defaults={"word": word})
        except IntegrityError:
            wotd = WordOfTheDay.objects.get(date=target_date)
            if wotd.word_id != word.pk:
                wotd.word = word
                wotd.save(update_fields=["word"])

        WordUsage.objects.get_or_create(
            word=word,
            usage_type="WOTD",
            used_on=target_date,
        )

        if getattr(word, "embedding", None) in (None, [], {}):
            _queue_embedding_refresh([word.pk])

        return _prefetched_wotd_queryset().get(pk=wotd.pk)

    finally:
        _release_lock(lock_key, lock_token)
