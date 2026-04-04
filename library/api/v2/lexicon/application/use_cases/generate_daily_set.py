
# qubitgyan-backend/library/api/v2/lexicon/application/use_cases/generate_daily_set.py

import logging
import random
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from ...application.constants import DEFAULT_PRACTICE_COUNT, PRACTICE_BLACKLIST_DAYS, SEED_WORDS
from ...application.utils import normalize_text, sample_items
from ...models import DailyPracticeSet, Word, WordUsage
from .search_word import fetch_and_store_word

logger = logging.getLogger(__name__)


def _recent_blacklist_ids(today, days: int):
    cutoff = today - timedelta(days=days)
    return WordUsage.objects.filter(used_on__gte=cutoff).values_list("word_id", flat=True).distinct()


def _unique_words(words):
    unique = {}
    for word in words:
        unique[word.pk] = word
    return list(unique.values())


def _top_up_with_seed_words(available_words, blacklist_ids, target_count):
    existing_texts = set(Word.objects.filter(language="en").values_list("text", flat=True)[:5000])
    candidate_seeds = [
        normalize_text(word)
        for word in SEED_WORDS
        if normalize_text(word) not in existing_texts
    ]
    random.shuffle(candidate_seeds)

    selected = {word.pk: word for word in available_words}
    for seed in candidate_seeds:
        if len(selected) >= target_count:
            break
        new_word, _ = fetch_and_store_word(seed, "en", increment_search_count=False)
        if new_word and new_word.pk not in blacklist_ids:
            selected[new_word.pk] = new_word

    return list(selected.values())


def _prefetched_practice_set(pk):
    return (
        DailyPracticeSet.objects.prefetch_related(
            "words__categories",
            "words__pronunciations",
            "words__meanings",
            "words__thesaurus_entries",
        )
        .get(pk=pk)
    )


@transaction.atomic
def generate_daily_practice_set(date=None, count: int = DEFAULT_PRACTICE_COUNT):
    today = date or timezone.localdate()

    existing = (
        DailyPracticeSet.objects.prefetch_related(
            "words__categories",
            "words__pronunciations",
            "words__meanings",
            "words__thesaurus_entries",
        )
        .filter(date=today)
        .first()
    )
    if existing:
        return existing

    blacklist_ids = set(_recent_blacklist_ids(today, PRACTICE_BLACKLIST_DAYS))
    available_words = list(Word.objects.filter(language="en", is_active=True).exclude(id__in=blacklist_ids))

    if len(available_words) < count:
        available_words = _top_up_with_seed_words(available_words, blacklist_ids, count)

    if len(available_words) < count:
        fallback_pool = list(Word.objects.filter(language="en", is_active=True).exclude(id__in=blacklist_ids))
        available_words = _unique_words([*available_words, *fallback_pool])

    if len(available_words) < count:
        raise ValueError("Not enough words available to generate a practice set.")

    selected = sample_items(available_words, count)

    try:
        practice_set, _ = DailyPracticeSet.objects.get_or_create(date=today)
    except IntegrityError:
        practice_set = DailyPracticeSet.objects.get(date=today)

    practice_set.words.set(selected)

    WordUsage.objects.bulk_create(
        [WordUsage(word=word, usage_type="PRACTICE", used_on=today) for word in selected],
        ignore_conflicts=True,
    )

    return _prefetched_practice_set(practice_set.pk)
