# qubitgyan-backend/library/api/v2/lexicon/application/use_cases/generate_wotd.py

import logging
import random
import uuid
from datetime import timedelta

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from ...application.constants import SEED_WORDS, WOTD_BLACKLIST_DAYS
from ...application.utils import is_sophisticated_word, normalize_text
from ...models import Word, WordOfTheDay, WordUsage
from .search_word import fetch_and_store_word

logger = logging.getLogger(__name__)

_LOCK_TIMEOUT_SECONDS = 60


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


def _recent_blacklist_ids(date_value, days: int):
    cutoff = date_value - timedelta(days=days)
    return (
        WordUsage.objects.filter(used_on__gte=cutoff)
        .values_list("word_id", flat=True)
        .distinct()
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

        candidates = list(
            Word.objects.filter(language="en", is_active=True, is_sophisticated=True)
            .exclude(id__in=blacklist_ids)
            .only("id", "text", "difficulty_score", "embedding")
            .order_by("-difficulty_score", "-created_at")[:100]
        )

        word = rng.choice(candidates) if candidates else None

        if not word:
            word = _top_up_with_sophisticated_seeds(blacklist_ids, rng)

        if not word:
            fallback = list(
                Word.objects.filter(language="en", is_active=True)
                .exclude(id__in=blacklist_ids)
                .only("id", "text", "difficulty_score", "embedding")
                .order_by("-difficulty_score", "-created_at")[:100]
            )
            word = rng.choice(fallback) if fallback else None

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

        