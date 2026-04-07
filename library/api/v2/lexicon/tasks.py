# qubitgyan-backend\library\api\v2\lexicon\tasks.py

import logging

from celery import shared_task

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
def generate_daily_practice_set_job(self, seed_top_up: bool = True):
    """Background daily job to pre-generate today's practice set before traffic peaks."""
    from .application.use_cases.generate_daily_set import generate_daily_practice_set

    practice_set = generate_daily_practice_set(seed_top_up=seed_top_up)
    return str(practice_set.pk) if practice_set else None
