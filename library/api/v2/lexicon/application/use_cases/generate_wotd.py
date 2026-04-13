import logging
import random
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.utils import timezone

from ...application.constants import (
    MIN_MEANINGS_FOR_SELECTION,
    WOTD_BLACKLIST_DAYS,
    WOTD_MIN_DIFFICULTY_SCORE,
)
from ...models import Word, WordOfTheDay, WordUsage

logger = logging.getLogger(__name__)

_LOCK_TIMEOUT_SECONDS = 60


def _acquire_lock(lock_key: str) -> str | None:
    token = uuid.uuid4().hex
    if cache.add(lock_key, token, timeout=_LOCK_TIMEOUT_SECONDS):
        return token
    return None


def _release_lock(lock_key: str, token: str | None) -> None:
    if token and cache.get(lock_key) == token:
        cache.delete(lock_key)


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


def _queue_embedding_refresh(word_id):
    if not settings.ENABLE_ASYNC_TASKS:
        try:
            from ...application.utils.embeddings import build_word_embedding_text, encode_text_to_vector

            word = Word.objects.prefetch_related(
                "categories",
                "pronunciations",
                "meanings",
                "thesaurus_entries",
            ).get(pk=word_id)
        except Word.DoesNotExist:
            return

        vector = encode_text_to_vector(build_word_embedding_text(word))
        Word.objects.filter(pk=word.pk).update(embedding=vector if any(vector) else None)
        return

    from ...tasks import refresh_word_embedding

    transaction.on_commit(lambda: refresh_word_embedding.delay(str(word_id)))


def _select_word(target_date):
    rng = random.Random(str(target_date))
    blacklist_ids = set(_recent_blacklist_ids(target_date, WOTD_BLACKLIST_DAYS))
    candidates = list(_candidate_queryset().exclude(id__in=blacklist_ids)[:200])
    if not candidates:
        return None
    return rng.choice(candidates)


def generate_word_of_the_day(date=None, *, allow_prime: bool = False, prime_batch_size: int = 1):
    target_date = date or timezone.localdate()
    lock_key = f"lock:wotd:{target_date.isoformat()}"
    lock_token = _acquire_lock(lock_key)

    if lock_token is None:
        return _existing_wotd(target_date)

    try:
        existing = _existing_wotd(target_date)
        if existing:
            return existing

        word = _select_word(target_date)

        if word is None and allow_prime:
            from .search_word import prime_remote_dictionary_inventory

            prime_remote_dictionary_inventory(
                language="en",
                limit=max(1, prime_batch_size),
                related_depth=0,
                related_limit=0,
                import_related=False,
                force_enrich=False,
            )
            word = _select_word(target_date)

        if word is None:
            return None

        try:
            wotd, _ = WordOfTheDay.objects.update_or_create(date=target_date, defaults={"word": word})
        except IntegrityError:
            wotd = WordOfTheDay.objects.get(date=target_date)
            if wotd.word_id != word.pk:
                wotd.word = word
                wotd.save(update_fields=["word"])

        WordUsage.objects.filter(usage_type="WOTD", used_on=target_date).delete()
        WordUsage.objects.create(word=word, usage_type="WOTD", used_on=target_date)

        if not getattr(word, "embedding", None):
            _queue_embedding_refresh(word.pk)

        return _prefetched_wotd_queryset().get(pk=wotd.pk)

    finally:
        _release_lock(lock_key, lock_token)