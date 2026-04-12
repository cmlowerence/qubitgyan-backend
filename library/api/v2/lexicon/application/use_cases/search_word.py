# qubitgyan-backend/library/api/v2/lexicon/application/use_cases/search_word.py

import logging
from typing import Iterable

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from ...application.utils import calculate_difficulty_score, is_sophisticated_word, normalize_text, unique_list
from ...infrastructure.external_apis.fda_client import FDAClient
from ...infrastructure.external_apis.mw_client import MWClient
from ...models import Meaning, Pronunciation, Thesaurus, Word

logger = logging.getLogger(__name__)

ENRICHMENT_COOLDOWN_HOURS = 24
DEFAULT_RELATED_IMPORT_LIMIT = 4
DEFAULT_RELATED_IMPORT_DEPTH = 1


def _has_items(value) -> bool:
    if value is None:
        return False

    if isinstance(value, str):
        return bool(value.strip())

    size = getattr(value, "size", None)
    if isinstance(size, int):
        return size > 0

    try:
        return len(value) > 0
    except TypeError:
        return bool(value)
    except ValueError:
        size = getattr(value, "size", None)
        if isinstance(size, int):
            return size > 0
        return True


def _as_list(value):
    if value is None:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, tuple):
        return list(value)

    if isinstance(value, set):
        return list(value)

    if isinstance(value, str):
        return [value]

    try:
        return list(value)
    except TypeError:
        return [value]


def _payload_has_content(payload) -> bool:
    if payload is None:
        return False

    if isinstance(payload, dict):
        return any(
            _has_items(payload.get(key))
            for key in ("phonetic_text", "pronunciations", "meanings", "thesaurus")
        )

    return _has_items(payload)


def _prefetched_word(word: Word) -> Word:
    return (
        Word.objects.prefetch_related(
            "categories",
            "pronunciations",
            "meanings",
            "thesaurus_entries",
        )
        .get(pk=word.pk)
    )


def _queue_enrichment(word_id, language: str):
    if not settings.ENABLE_ASYNC_TASKS:
        logger.warning("Skipping enrich_word_record task dispatch because async tasks are disabled.")
        return

    from ...tasks import enrich_word_record

    def _dispatch():
        try:
            enrich_word_record.delay(str(word_id), language)
        except Exception as exc:
            logger.warning(
                "Failed to dispatch enrich_word_record task for word_id=%s language=%s: %s",
                word_id,
                language,
                exc,
            )

    transaction.on_commit(_dispatch)


def _queue_embedding_refresh(word_id):
    if not settings.ENABLE_ASYNC_TASKS:
        logger.warning("Skipping refresh_word_embedding task dispatch because async tasks are disabled.")
        return

    from ...tasks import refresh_word_embedding

    def _dispatch():
        try:
            refresh_word_embedding.delay(str(word_id))
        except Exception as exc:
            logger.warning(
                "Failed to dispatch refresh_word_embedding task for word_id=%s: %s",
                word_id,
                exc,
            )

    transaction.on_commit(_dispatch)


def _should_enrich(word: Word) -> bool:
    if not word.updated_at:
        return True

    delta = timezone.now() - word.updated_at
    return delta.total_seconds() > ENRICHMENT_COOLDOWN_HOURS * 3600


def _merge_payloads(*payloads):
    merged = {
        "phonetic_text": "",
        "pronunciations": [],
        "meanings": [],
        "thesaurus": [],
    }

    for payload in payloads:
        if not _payload_has_content(payload):
            continue

        if not merged["phonetic_text"] and payload.get("phonetic_text"):
            merged["phonetic_text"] = payload["phonetic_text"]

        merged["pronunciations"].extend(_as_list(payload.get("pronunciations")))
        merged["meanings"].extend(_as_list(payload.get("meanings")))
        merged["thesaurus"].extend(_as_list(payload.get("thesaurus")))

    pronunciation_pairs = unique_list(
        [
            (item.get("audio_url", ""), item.get("region", "GEN"))
            for item in merged["pronunciations"]
            if isinstance(item, dict) and item.get("audio_url")
        ]
    )
    merged["pronunciations"] = [{"audio_url": url, "region": region} for url, region in pronunciation_pairs]

    meaning_triples = unique_list(
        [
            (
                item.get("part_of_speech", ""),
                item.get("definition", ""),
                item.get("example", "") or "",
            )
            for item in merged["meanings"]
            if isinstance(item, dict) and item.get("definition")
        ]
    )
    merged["meanings"] = [
        {"part_of_speech": pos, "definition": definition, "example": example}
        for pos, definition, example in meaning_triples
    ]

    thesaurus_pairs = unique_list(
        [
            (
                normalize_text(item.get("related_word_text", "")),
                (item.get("relation_type") or "SYN").upper(),
            )
            for item in merged["thesaurus"]
            if isinstance(item, dict) and item.get("related_word_text")
        ]
    )
    merged["thesaurus"] = [
        {"related_word_text": text, "relation_type": rel}
        for text, rel in thesaurus_pairs
    ]

    return merged


def _payload_sources(fda_payload, mw_dict_payload, mw_thes_payload):
    sources = set()
    if _payload_has_content(fda_payload):
        sources.add("FDA")
    if _payload_has_content(mw_dict_payload) or _payload_has_content(mw_thes_payload):
        sources.add("MW")
    return sources


def _merge_source_api(current_source: str, payload_sources: Iterable[str]) -> str:
    current_source = (current_source or "MANUAL").upper()
    payload_sources = {s.upper() for s in payload_sources if s}

    if not payload_sources:
        return current_source

    if current_source in {"MANUAL", "IMPORT"}:
        return "MIXED" if len(payload_sources) > 1 else next(iter(payload_sources))

    if current_source in payload_sources:
        return "MIXED" if len(payload_sources) > 1 else current_source

    return "MIXED"


def _sync_thesaurus_links(word: Word) -> None:
    unresolved = list(
        word.thesaurus_entries.filter(related_word__isnull=True).values(
            "id",
            "related_word_text",
            "relation_type",
        )
    )

    if not unresolved:
        return

    linked = 0
    for entry in unresolved:
        related_text = normalize_text(entry["related_word_text"])
        if not related_text:
            continue

        related_word = (
            Word.objects.filter(text=related_text, language=word.language, is_active=True)
            .only("id")
            .first()
        )
        if not related_word:
            continue

        Thesaurus.objects.filter(pk=entry["id"]).update(related_word=related_word)
        linked += 1

    if linked:
        logger.info("Linked %s thesaurus relations for word=%s", linked, word.text)


def _backfill_related_word_links(word: Word) -> int:
    matches = (
        Thesaurus.objects.filter(
            related_word__isnull=True,
            related_word_text=word.text,
            word__language=word.language,
        )
        .exclude(word=word)
    )
    updated = matches.update(related_word=word)
    if updated:
        logger.info("Backfilled %s thesaurus relations for related word=%s", updated, word.text)
    return updated


def _upsert_related_data(word: Word, payload: dict, payload_sources: Iterable[str]):
    if payload.get("phonetic_text") and not word.phonetic_text:
        word.phonetic_text = payload["phonetic_text"]

    existing_meanings = {
        (pos, definition, example or "")
        for pos, definition, example in word.meanings.values_list("part_of_speech", "definition", "example")
    }

    new_meanings = []
    for item in payload.get("meanings", []):
        if not isinstance(item, dict):
            continue

        key = (item["part_of_speech"], item["definition"], item.get("example") or "")
        if key not in existing_meanings:
            new_meanings.append(Meaning(word=word, **item))
            existing_meanings.add(key)

    if new_meanings:
        Meaning.objects.bulk_create(new_meanings)

    existing_pronunciations = {
        (audio_url, region)
        for audio_url, region in word.pronunciations.values_list("audio_url", "region")
    }

    new_pronunciations = []
    for item in payload.get("pronunciations", []):
        if not isinstance(item, dict):
            continue

        key = (item["audio_url"], item["region"])
        if key not in existing_pronunciations:
            new_pronunciations.append(Pronunciation(word=word, **item))
            existing_pronunciations.add(key)

    if new_pronunciations:
        Pronunciation.objects.bulk_create(new_pronunciations)

    existing_thesaurus = {
        (text, rel)
        for text, rel in word.thesaurus_entries.values_list("related_word_text", "relation_type")
    }

    new_thesaurus = []
    for item in payload.get("thesaurus", []):
        if not isinstance(item, dict):
            continue

        text = normalize_text(item["related_word_text"])
        rel = (item.get("relation_type") or "SYN").upper()
        key = (text, rel)

        if key not in existing_thesaurus:
            new_thesaurus.append(
                Thesaurus(word=word, related_word_text=text, relation_type=rel)
            )
            existing_thesaurus.add(key)

    if new_thesaurus:
        Thesaurus.objects.bulk_create(new_thesaurus)

    word.difficulty_score = calculate_difficulty_score(
        word.text,
        meanings_count=len(existing_meanings),
        pronunciation_count=len(existing_pronunciations),
        thesaurus_count=len(existing_thesaurus),
    )

    word.is_sophisticated = is_sophisticated_word(word.text, word.difficulty_score)

    new_source = _merge_source_api(word.source_api, payload_sources)
    if new_source != word.source_api:
        word.source_api = new_source

    word.save(update_fields=["difficulty_score", "is_sophisticated", "source_api", "updated_at"])
    _backfill_related_word_links(word)
    _sync_thesaurus_links(word)


def _fetch_remote_payload(word_query: str, language: str):
    fda_payload, fda_suggestions = FDAClient.fetch(word_query, language)

    if language == "en":
        mw_dict_payload, mw_dict_suggestions = MWClient.fetch_dictionary(word_query)
        mw_thes_payload, mw_thes_suggestions = MWClient.fetch_thesaurus(word_query)
    else:
        mw_dict_payload, mw_dict_suggestions = None, []
        mw_thes_payload, mw_thes_suggestions = None, []

    merged = _merge_payloads(fda_payload, mw_dict_payload, mw_thes_payload)

    suggestions = unique_list(
        _as_list(fda_suggestions) + _as_list(mw_dict_suggestions) + _as_list(mw_thes_suggestions)
    )

    sources = _payload_sources(fda_payload, mw_dict_payload, mw_thes_payload)

    return merged, suggestions, sources, fda_payload, mw_dict_payload, mw_thes_payload


def _related_word_texts(word: Word, limit: int):
    texts = []
    seen = set()
    for text in word.thesaurus_entries.values_list("related_word_text", flat=True):
        normalized = normalize_text(text)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        texts.append(normalized)
        if len(texts) >= limit:
            break
    return texts


def _import_related_words(
    word: Word,
    language: str,
    *,
    depth: int = DEFAULT_RELATED_IMPORT_DEPTH,
    limit: int = DEFAULT_RELATED_IMPORT_LIMIT,
    visited: set[str] | None = None,
):
    if depth <= 0:
        return []

    visited = visited or set()
    imported_words = []

    for related_text in _related_word_texts(word, limit):
        visit_key = f"{language}:{related_text}"
        if visit_key in visited:
            continue
        visited.add(visit_key)

        related_word, _ = fetch_and_store_word(
            related_text,
            language=language,
            increment_search_count=False,
            import_related=depth - 1 > 0,
            related_depth=depth - 1,
            related_limit=limit,
            force_enrich=True,
            visited=visited,
        )
        if related_word:
            imported_words.append(related_word)

    return imported_words


def enrich_existing_word_from_remote(
    word: Word,
    language: str = "en",
    *,
    import_related: bool = True,
    related_depth: int = DEFAULT_RELATED_IMPORT_DEPTH,
    related_limit: int = DEFAULT_RELATED_IMPORT_LIMIT,
    visited: set[str] | None = None,
) -> bool:
    merged, _, sources, _, _, _ = _fetch_remote_payload(word.text, language)

    if not _payload_has_content(merged):
        return False

    _upsert_related_data(word, merged, sources)
    _backfill_related_word_links(word)

    if import_related:
        _import_related_words(
            word,
            language,
            depth=related_depth,
            limit=related_limit,
            visited=visited,
        )

    return True


@transaction.atomic
def fetch_and_store_word(
    word_query: str,
    language: str = "en",
    increment_search_count: bool = False,
    *,
    import_related: bool = False,
    related_depth: int = DEFAULT_RELATED_IMPORT_DEPTH,
    related_limit: int = DEFAULT_RELATED_IMPORT_LIMIT,
    force_enrich: bool = False,
    visited: set[str] | None = None,
):
    word_query = normalize_text(word_query)
    language = normalize_text(language) or "en"

    if not word_query:
        return None, []

    visited = visited or set()
    visit_key = f"{language}:{word_query}"
    if visit_key in visited:
        existing = (
            Word.objects.prefetch_related("categories", "pronunciations", "meanings", "thesaurus_entries")
            .filter(text=word_query, language=language)
            .first()
        )
        return (_prefetched_word(existing), []) if existing else (None, [])
    visited.add(visit_key)

    existing = (
        Word.objects.prefetch_related("categories", "pronunciations", "meanings", "thesaurus_entries")
        .filter(text=word_query, language=language)
        .first()
    )

    if existing:
        if increment_search_count:
            Word.objects.filter(pk=existing.pk).update(search_count=F("search_count") + 1)
            existing.refresh_from_db(fields=["search_count"])

        if force_enrich:
            enrich_existing_word_from_remote(
                existing,
                language,
                import_related=import_related,
                related_depth=related_depth,
                related_limit=related_limit,
                visited=visited,
            )
        elif _should_enrich(existing):
            _queue_enrichment(existing.pk, language)
        elif not _has_items(getattr(existing, "embedding", None)):
            _queue_embedding_refresh(existing.pk)

        return _prefetched_word(existing), []

    merged, suggestions, sources, fda, mw_dict, mw_thes = _fetch_remote_payload(word_query, language)

    if not (_payload_has_content(fda) or _payload_has_content(mw_dict) or _payload_has_content(mw_thes)):
        return None, suggestions

    difficulty = calculate_difficulty_score(
        word_query,
        meanings_count=len(merged["meanings"]),
        pronunciation_count=len(merged["pronunciations"]),
        thesaurus_count=len(merged["thesaurus"]),
    )

    source_api = "MIXED" if len(sources) > 1 else (next(iter(sources)) if sources else "MANUAL")

    defaults = {
        "phonetic_text": merged["phonetic_text"],
        "source_api": source_api,
        "word_type": "WORD",
        "search_count": 1 if increment_search_count else 0,
        "difficulty_score": difficulty,
        "is_sophisticated": is_sophisticated_word(word_query, difficulty),
    }

    try:
        word, created = Word.objects.get_or_create(
            text=word_query,
            language=language,
            defaults=defaults,
        )
    except IntegrityError:
        word = Word.objects.get(text=word_query, language=language)
        created = False

    if not created and increment_search_count:
        Word.objects.filter(pk=word.pk).update(search_count=F("search_count") + 1)
        word.refresh_from_db(fields=["search_count"])

    if merged["phonetic_text"] and not word.phonetic_text:
        word.phonetic_text = merged["phonetic_text"]

    word.source_api = _merge_source_api(word.source_api, sources)
    word.save(update_fields=["phonetic_text", "source_api", "updated_at"])

    _upsert_related_data(word, merged, sources)
    _backfill_related_word_links(word)

    if import_related:
        _import_related_words(
            word,
            language,
            depth=related_depth,
            limit=related_limit,
            visited=visited,
        )

    _queue_embedding_refresh(word.pk)

    return _prefetched_word(word), []


def prime_remote_dictionary_inventory(
    *,
    seed_words: Iterable[str] | None = None,
    language: str = "en",
    limit: int = 8,
    related_depth: int = DEFAULT_RELATED_IMPORT_DEPTH,
    related_limit: int = DEFAULT_RELATED_IMPORT_LIMIT,
):
    from ...application.constants import SEED_WORDS

    seeds = list(seed_words or SEED_WORDS)
    selected = []
    seen = set()

    for seed in seeds:
        normalized = normalize_text(seed)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        selected.append(normalized)
        if len(selected) >= limit:
            break

    imported = []
    visited = set()
    for seed in selected:
        word, _ = fetch_and_store_word(
            seed,
            language=language,
            increment_search_count=False,
            import_related=True,
            related_depth=related_depth,
            related_limit=related_limit,
            force_enrich=True,
            visited=visited,
        )
        if word:
            imported.append(word)

    return imported
    
    
