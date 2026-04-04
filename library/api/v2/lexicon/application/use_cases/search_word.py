# qubitgyan-backend/library/api/v2/lexicon/application/use_cases/search_word.py

import logging
from typing import Iterable

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from ...application.utils import calculate_difficulty_score, is_sophisticated_word, normalize_text, unique_list
from ...infrastructure.external_apis.fda_client import FDAClient
from ...infrastructure.external_apis.mw_client import MWClient
from ...models import Meaning, Pronunciation, Thesaurus, Word

logger = logging.getLogger(__name__)

ENRICHMENT_COOLDOWN_HOURS = 24


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
    from ...tasks import enrich_word_record

    transaction.on_commit(lambda: enrich_word_record.delay(str(word_id), language))


def _queue_embedding_refresh(word_id):
    from ...tasks import refresh_word_embedding

    transaction.on_commit(lambda: refresh_word_embedding.delay(str(word_id)))


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
        if not payload:
            continue

        if not merged["phonetic_text"] and payload.get("phonetic_text"):
            merged["phonetic_text"] = payload["phonetic_text"]

        merged["pronunciations"].extend(payload.get("pronunciations", []))
        merged["meanings"].extend(payload.get("meanings", []))
        merged["thesaurus"].extend(payload.get("thesaurus", []))

    pronunciation_pairs = unique_list(
        [
            (item.get("audio_url", ""), item.get("region", "GEN"))
            for item in merged["pronunciations"]
            if item.get("audio_url")
        ]
    )

    merged["pronunciations"] = [
        {"audio_url": url, "region": region}
        for url, region in pronunciation_pairs
    ]

    meaning_triples = unique_list(
        [
            (
                item.get("part_of_speech", ""),
                item.get("definition", ""),
                item.get("example", "") or "",
            )
            for item in merged["meanings"]
            if item.get("definition")
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
            if item.get("related_word_text")
        ]
    )

    merged["thesaurus"] = [
        {"related_word_text": text, "relation_type": rel}
        for text, rel in thesaurus_pairs
    ]

    return merged


def _payload_sources(fda_payload, mw_dict_payload, mw_thes_payload):
    sources = set()
    if fda_payload:
        sources.add("FDA")
    if mw_dict_payload or mw_thes_payload:
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


def _upsert_related_data(word: Word, payload: dict, payload_sources: Iterable[str]):
    if payload.get("phonetic_text") and not word.phonetic_text:
        word.phonetic_text = payload["phonetic_text"]

    existing_meanings = {
        (pos, definition, example or "")
        for pos, definition, example in word.meanings.values_list("part_of_speech", "definition", "example")
    }

    new_meanings = []
    for item in payload.get("meanings", []):
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
        [
            *(fda_suggestions or []),
            *(mw_dict_suggestions or []),
            *(mw_thes_suggestions or []),
        ]
    )

    sources = _payload_sources(fda_payload, mw_dict_payload, mw_thes_payload)

    return merged, suggestions, sources, fda_payload, mw_dict_payload, mw_thes_payload


def enrich_existing_word_from_remote(word: Word, language: str = "en") -> bool:
    merged, _, sources, _, _, _ = _fetch_remote_payload(word.text, language)

    if not (merged["phonetic_text"] or merged["pronunciations"] or merged["meanings"] or merged["thesaurus"]):
        return False

    _upsert_related_data(word, merged, sources)
    return True


@transaction.atomic
def fetch_and_store_word(word_query: str, language: str = "en", increment_search_count: bool = False):
    word_query = normalize_text(word_query)
    language = normalize_text(language) or "en"

    if not word_query:
        return None, []

    existing = (
        Word.objects.prefetch_related("categories", "pronunciations", "meanings", "thesaurus_entries")
        .filter(text=word_query, language=language)
        .first()
    )

    if existing:
        if increment_search_count:
            Word.objects.filter(pk=existing.pk).update(search_count=F("search_count") + 1)
            existing.refresh_from_db(fields=["search_count"])

        if _should_enrich(existing):
            _queue_enrichment(existing.pk, language)
        elif getattr(existing, "embedding", None) in (None, [], {}):
            _queue_embedding_refresh(existing.pk)

        return _prefetched_word(existing), []

    merged, suggestions, sources, fda, mw_dict, mw_thes = _fetch_remote_payload(word_query, language)

    if not fda and not mw_dict and not mw_thes:
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
    _queue_embedding_refresh(word.pk)

    return _prefetched_word(word), []

