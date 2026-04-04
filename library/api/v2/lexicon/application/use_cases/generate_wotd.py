
# qubitgyan-backend/library/api/v2/lexicon/application/use_cases/generate_wotd.py

import logging
import random
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from ...application.constants import SEED_WORDS, WOTD_BLACKLIST_DAYS
from ...application.utils import is_sophisticated_word, normalize_text
from ...models import Word, WordOfTheDay, WordUsage
from .search_word import fetch_and_store_word

logger = logging.getLogger(__name__)


def _recent_blacklist_ids(today, days: int):
    cutoff = today - timedelta(days=days)
    return WordUsage.objects.filter(used_on__gte=cutoff).values_list("word_id", flat=True).distinct()


def _top_up_with_sophisticated_seeds(blacklist_ids):
    existing_texts = set(Word.objects.values_list("text", flat=True))
    seeds = [normalize_text(word) for word in SEED_WORDS if len(normalize_text(word)) >= 8]
    random.shuffle(seeds)

    for seed in seeds:
        if seed in existing_texts:
            continue
        new_word, _ = fetch_and_store_word(seed, "en", increment_search_count=False)
        if new_word and new_word.pk not in blacklist_ids and is_sophisticated_word(new_word.text, new_word.difficulty_score):
            return new_word

    return None


def _prefetched_wotd(pk):
    return (
        WordOfTheDay.objects.select_related("word")
        .prefetch_related("word__categories", "word__pronunciations", "word__meanings", "word__thesaurus_entries")
        .get(pk=pk)
    )


@transaction.atomic
def generate_word_of_the_day(date=None):
    today = date or timezone.localdate()

    existing = (
        WordOfTheDay.objects.select_related("word")
        .prefetch_related("word__categories", "word__pronunciations", "word__meanings", "word__thesaurus_entries")
        .filter(date=today)
        .first()
    )
    if existing:
        return existing

    blacklist_ids = set(_recent_blacklist_ids(today, WOTD_BLACKLIST_DAYS))

    candidates = list(
        Word.objects.filter(language="en", is_active=True, is_sophisticated=True)
        .exclude(id__in=blacklist_ids)
        .order_by("-difficulty_score", "-created_at")[:100]
    )

    word = random.choice(candidates) if candidates else None
    if not word:
        word = _top_up_with_sophisticated_seeds(blacklist_ids)

    if not word:
        fallback = list(
            Word.objects.filter(language="en", is_active=True)
            .exclude(id__in=blacklist_ids)
            .order_by("-difficulty_score", "-created_at")[:100]
        )
        word = random.choice(fallback) if fallback else None

    if not word:
        raise ValueError("Unable to generate a word of the day.")

    try:
        wotd, _ = WordOfTheDay.objects.update_or_create(date=today, defaults={"word": word})
    except IntegrityError:
        wotd = WordOfTheDay.objects.get(date=today)
        if wotd.word_id != word.pk:
            wotd.word = word
            wotd.save(update_fields=["word"])

    WordUsage.objects.get_or_create(word=word, usage_type="WOTD", used_on=today)

    return _prefetched_wotd(wotd.pk)
