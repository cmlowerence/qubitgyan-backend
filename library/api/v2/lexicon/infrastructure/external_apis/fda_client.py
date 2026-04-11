
# qubitgyan-backend/library/api/v2/lexicon/infrastructure/external_apis/fda_client.py

import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


def _unique_normalized_strings(values):
    seen = set()
    output = []
    for value in values:
        text = (value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        output.append(text)
    return output


def _unique_pronunciations(items):
    seen = set()
    output = []
    for item in items:
        audio = (item.get("audio_url") or "").strip()
        region = (item.get("region") or "GEN").strip().upper()
        if not audio:
            continue
        key = (audio, region)
        if key in seen:
            continue
        seen.add(key)
        output.append({"audio_url": audio, "region": region})
    return output


def _unique_meanings(items):
    seen = set()
    output = []
    for item in items:
        pos = (item.get("part_of_speech") or "").strip()
        definition = (item.get("definition") or "").strip()
        example = (item.get("example") or "").strip()

        if not definition:
            continue

        key = (pos, definition, example)
        if key in seen:
            continue

        seen.add(key)
        output.append(
            {
                "part_of_speech": pos,
                "definition": definition,
                "example": example,
            }
        )
    return output


def _unique_thesaurus(items):
    seen = set()
    output = []
    for item in items:
        text = (item.get("related_word_text") or "").strip().lower()
        relation = (item.get("relation_type") or "SYN").strip().upper()

        if not text:
            continue

        key = (text, relation)
        if key in seen:
            continue

        seen.add(key)
        output.append(
            {
                "related_word_text": text,
                "relation_type": relation,
            }
        )
    return output


class FDAClient:
    BASE_URL = "https://api.dictionaryapi.dev/api/v2/entries"

    @classmethod
    def _request(cls, language: str, word: str):
        return requests.get(
            f"{cls.BASE_URL}/{language}/{word}",
            timeout=6,
            headers={"Accept": "application/json"},
        )

    @classmethod
    def _parse_payload(cls, entry: dict[str, Any]):
        payload = {
            "phonetic_text": "",
            "pronunciations": [],
            "meanings": [],
            "thesaurus": [],
        }

        phonetic = (entry.get("phonetic") or "").strip()
        if phonetic:
            payload["phonetic_text"] = phonetic

        for phon in entry.get("phonetics", []) or []:
            audio_url = (phon.get("audio") or "").strip()
            if not audio_url:
                continue

            region = "GEN"
            lowered = audio_url.lower()
            if "-uk" in lowered:
                region = "UK"
            elif "-us" in lowered:
                region = "US"
            elif "-in" in lowered:
                region = "IN"
            elif "-sco" in lowered:
                region = "SCO"

            payload["pronunciations"].append(
                {
                    "audio_url": audio_url,
                    "region": region,
                }
            )

            inline_phonetic = (phon.get("text") or "").strip()
            if inline_phonetic and not payload["phonetic_text"]:
                payload["phonetic_text"] = inline_phonetic

        for meaning in entry.get("meanings", []) or []:
            pos = (meaning.get("partOfSpeech") or "").strip()

            for def_data in meaning.get("definitions", []) or []:
                definition = (def_data.get("definition") or "").strip()
                if not definition:
                    continue

                payload["meanings"].append(
                    {
                        "part_of_speech": pos,
                        "definition": definition,
                        "example": (def_data.get("example") or "").strip(),
                    }
                )

                for syn in def_data.get("synonyms", []) or []:
                    payload["thesaurus"].append(
                        {"related_word_text": syn, "relation_type": "SYN"}
                    )

                for ant in def_data.get("antonyms", []) or []:
                    payload["thesaurus"].append(
                        {"related_word_text": ant, "relation_type": "ANT"}
                    )

        return payload

    @classmethod
    def fetch(cls, word: str, language: str = "en"):
        word = (word or "").strip().lower()
        language = (language or "en").strip().lower() or "en"

        try:
            response = cls._request(language, word)

            if response.status_code == 404:
                data = response.json()
                suggestions = data if isinstance(data, list) else []
                return None, _unique_normalized_strings(suggestions[:10])

            if response.status_code != 200:
                return None, []

            data = response.json()
            if not isinstance(data, list) or not data:
                return None, []

            payloads = [
                cls._parse_payload(entry)
                for entry in data
                if isinstance(entry, dict)
            ]

            if not payloads:
                return None, []

            merged = {
                "phonetic_text": "",
                "pronunciations": [],
                "meanings": [],
                "thesaurus": [],
            }

            for item in payloads:
                if not merged["phonetic_text"] and item.get("phonetic_text"):
                    merged["phonetic_text"] = item["phonetic_text"]

                merged["pronunciations"].extend(item.get("pronunciations", []))
                merged["meanings"].extend(item.get("meanings", []))
                merged["thesaurus"].extend(item.get("thesaurus", []))

            merged["pronunciations"] = _unique_pronunciations(merged["pronunciations"])
            merged["meanings"] = _unique_meanings(merged["meanings"])
            merged["thesaurus"] = _unique_thesaurus(merged["thesaurus"])

            return merged, []

        except (requests.RequestException, ValueError, TypeError) as exc:
            logger.warning("FDA fetch failed for %s: %s", word, exc)
            return None, []