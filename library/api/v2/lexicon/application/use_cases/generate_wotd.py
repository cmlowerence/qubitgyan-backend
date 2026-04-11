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
    WOTD_BLACKLIST_DAYS,
    WOTD_MIN_DIFFICULTY_SCORE,
)
from ...application.utils import normalize_text
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
    existing_texts = {
        normalize_text(text)
        for text in Word.objects.filter(language="en", is_active=True).values_list("text", flat=True)
    }
    seeds = [normalize_text(word) for word in [
        "aberration", "benevolent", "capricious", "dichotomy", "ephemeral",
        "fastidious", "garrulous", "harangue", "iconoclast", "juxtapose",
        "laconic", "maverick", "nebulous", "obfuscate", "paradigm",
        "quixotic", "resilient", "sycophant", "trepidation", "ubiquitous",
        "vacillate", "xenophobia", "zealous", "alacrity", "bellicose",
        "conundrum", "deleterious", "enervate", "fortuitous", "gratuitous",
        "hegemony", "impetuous", "judicious", "kaleidoscope", "loquacious",
        "meticulous", "nonchalant", "obstinate", "perfunctory", "reticent",
        "scrupulous", "tangible", "unfettered", "vindicate", "winsome",
        "yearning", "zephyr", "ascetic", "catharsis", "deference",
        "equanimity", "fervent", "gregarious", "halcyon", "inscrutable",
        "juxtaposition", "knavish", "legitimate", "melancholy", "nostalgic",
    ] if len(normalize_text(word)) >= 8]
    rng.shuffle(seeds)

    for seed in seeds:
        if seed in existing_texts:
            continue

        new_word, _ = fetch_and_store_word(
            seed,
            "en",
            increment_search_count=False,
            import_related=True,
            related_depth=1,
            related_limit=NIGHTLY_IMPORT_RELATED_LIMIT,
            force_enrich=True,
        )
        if (
            new_word
            and new_word.pk not in blacklist_ids
            and new_word.is_sophisticated
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
        previously_used_ids = _previously_used_ids("WOTD")

        candidates = list(_candidate_queryset()[:150])
        fresh_candidates = [word for word in candidates if word.pk not in previously_used_ids and word.pk not in blacklist_ids]
        stale_candidates = [word for word in candidates if word.pk in previously_used_ids and word.pk not in blacklist_ids]
        fallback_candidates = [word for word in candidates if word.pk in blacklist_ids]

        word = None
        for pool in (fresh_candidates, stale_candidates, fallback_candidates):
            if pool:
                word = rng.choice(pool)
                break

        if not word:
            word = _top_up_with_sophisticated_seeds(blacklist_ids, rng)

        if not word:
            fallback = list(
                Word.objects.filter(language="en", is_active=True)
                .annotate(
                    meaning_count=Count("meanings", distinct=True),
                    pronunciation_count=Count("pronunciations", distinct=True),
                    thesaurus_count=Count("thesaurus_entries", distinct=True),
                )
                .filter(meaning_count__gte=MIN_MEANINGS_FOR_SELECTION)
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
