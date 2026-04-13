import logging

from celery import shared_task

from .application.constants import NIGHTLY_IMPORT_RELATED_LIMIT
from .application.use_cases.generate_daily_set import generate_daily_practice_set
from .application.use_cases.generate_wotd import generate_word_of_the_day
from .application.use_cases.search_word import bootstrap_daily_lexicon, prime_remote_dictionary_inventory
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

    enriched = enrich_existing_word_from_remote(
        word,
        language,
        import_related=False,
        related_depth=0,
        related_limit=NIGHTLY_IMPORT_RELATED_LIMIT,
    )
    refresh_word_embedding.delay(str(word.pk))
    return str(word.pk) if enriched else str(word.pk)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=3)
def prime_lexicon_inventory_job(self):
    imported = prime_remote_dictionary_inventory(
        language="en",
        limit=1,
        related_depth=0,
        related_limit=0,
        import_related=False,
        force_enrich=False,
    )
    return [str(word.pk) for word in imported]


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=3)
def generate_daily_practice_set_job(self):
    practice_set = generate_daily_practice_set(allow_prime=False)
    return str(practice_set.pk) if practice_set else None


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=3)
def generate_word_of_the_day_job(self):
    wotd = generate_word_of_the_day(allow_prime=False)
    return str(wotd.pk) if wotd else None


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_jitter=True, max_retries=3)
def run_midnight_lexicon_pipeline(self):
    from django.utils import timezone

    target_date = timezone.localdate()
    result = bootstrap_daily_lexicon(date=target_date, practice_count=18)
    return {
        "status": result.get("status"),
        "imported": [str(word.pk) for word in result.get("imported", [])],
        "wotd": str(result["wotd"].pk) if result.get("wotd") else None,
        "practice_set": str(result["practice_set"].pk) if result.get("practice_set") else None,
    }
    
    