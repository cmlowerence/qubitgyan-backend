# qubitgyan-backend/library/api/v2/lexicon/tasks.py

import logging

from celery import shared_task
from django.utils import timezone

from .application.constants import DEFAULT_PRACTICE_COUNT
from .application.utils.embeddings import build_word_embedding_text, encode_text_to_vector
from .models import Word

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=3)
def refresh_word_embedding(self, word_id: str):
    try:
        word = (
            Word.objects.prefetch_related(
                "categories",
                "pronunciations",
                "meanings",
                "thesaurus_entries",
            )
            .get(pk=word_id)
        )
    except Word.DoesNotExist:
        return None

    embedding_text = build_word_embedding_text(word)
    vector = encode_text_to_vector(embedding_text)

    if not vector:
        Word.objects.filter(pk=word.pk).update(embedding=None)
        return str(word.pk)

    Word.objects.filter(pk=word.pk).update(embedding=vector)
    return str(word.pk)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=3)
def enrich_word_record(self, word_id: str, language: str = "en"):
    from .application.use_cases.search_word import enrich_existing_word_from_remote

    try:
        word = Word.objects.get(pk=word_id)
    except Word.DoesNotExist:
        return None

    enriched = enrich_existing_word_from_remote(word, language)
    refresh_word_embedding.delay(str(word.pk))
    return str(word.pk) if enriched else str(word.pk)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=3)
def generate_daily_practice_set_job(self, seed_top_up: bool = True, count: int | None = None):
    """Background job that prepares the daily practice set before the day starts."""
    from .application.constants import DEFAULT_PRACTICE_COUNT
    from .application.use_cases.generate_daily_set import generate_daily_practice_set

    practice_count = count or DEFAULT_PRACTICE_COUNT
    practice_set = generate_daily_practice_set(
        date=timezone.localdate(),
        count=practice_count,
        seed_top_up=seed_top_up,
        allow_remote_fetch=True,
    )
    return str(practice_set.pk) if practice_set else None


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=3)
def generate_word_of_the_day_job(self):
    """Background job that prepares the next word of the day."""
    from .application.use_cases.generate_wotd import generate_word_of_the_day

    wotd = generate_word_of_the_day(date=timezone.localdate(), allow_remote_fetch=True)
    return str(wotd.pk) if wotd else None


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=3)
def generate_lexicon_daily_content_job(self, seed_top_up: bool = True, count: int | None = None):
    """Single midnight job that warms both WOTD and practice content sequentially."""
    from .application.constants import DEFAULT_PRACTICE_COUNT
    from .application.use_cases.generate_daily_set import generate_daily_practice_set
    from .application.use_cases.generate_wotd import generate_word_of_the_day

    target_count = count or DEFAULT_PRACTICE_COUNT
    today = timezone.localdate()

    wotd = generate_word_of_the_day(date=today, allow_remote_fetch=True)
    practice_set = generate_daily_practice_set(
        date=today,
        count=target_count,
        seed_top_up=seed_top_up,
        allow_remote_fetch=True,
    )

    return {
        "date": today.isoformat(),
        "wotd_id": str(wotd.pk) if wotd else None,
        "practice_set_id": str(practice_set.pk) if practice_set else None,
        "practice_count": target_count,
    }
