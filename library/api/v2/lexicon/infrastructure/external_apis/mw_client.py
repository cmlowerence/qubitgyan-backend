
# qubitgyan-backend/library/api/v2/lexicon/infrastructure/external_apis/mw_client.py

import logging
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def _unique_normalized(values):
    seen = set()
    items = []
    for value in values:
        text = (value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(text)
    return items


class MWClient:
    DICTIONARY_URL = "https://www.dictionaryapi.com/api/v3/references/collegiate/json/{word}"
    THESAURUS_URL = "https://www.dictionaryapi.com/api/v3/references/thesaurus/json/{word}"

    @classmethod
    def _key(cls, setting_name: str):
        return getattr(settings, setting_name, None)

    @classmethod
    def _request(cls, url: str, api_key: str):
        return requests.get(
            url,
            params={"key": api_key},
            timeout=6,
            headers={"Accept": "application/json"},
        )

    @classmethod
    def _parse_dictionary_entry(cls, entry: dict[str, Any]):
        payload = {
            "phonetic_text": "",
            "pronunciations": [],
            "meanings": [],
            "thesaurus": [],
        }

        hw = (entry.get("hwi", {}) or {}).get("hw", "")
        if hw:
            payload["phonetic_text"] = hw.replace("*", "").strip()

        prs = (entry.get("hwi", {}) or {}).get("prs", []) or []
        for pronunciation in prs[:2]:
            sound = pronunciation.get("sound", {}) or {}
            audio_base = (sound.get("audio") or "").strip()
            if not audio_base:
                continue

            subdir = audio_base[0] if audio_base[0].isalpha() else "number"
            if audio_base.startswith("bix"):
                subdir = "bix"
            elif audio_base.startswith("gg"):
                subdir = "gg"

            payload["pronunciations"].append(
                {
                    "audio_url": f"https://media.merriam-webster.com/audio/prons/en/us/mp3/{subdir}/{audio_base}.mp3",
                    "region": "US",
                }
            )

        pos = (entry.get("fl", "") or "").strip()
        for definition in entry.get("shortdef", []) or []:
            definition = (definition or "").strip()
            if definition:
                payload["meanings"].append(
                    {
                        "part_of_speech": pos,
                        "definition": definition,
                        "example": "",
                    }
                )

        return payload

    @classmethod
    def _parse_thesaurus_entry(cls, entry: dict[str, Any]):
        payload = {
            "phonetic_text": "",
            "pronunciations": [],
            "meanings": [],
            "thesaurus": [],
        }

        meta = entry.get("meta", {}) or {}
        for syn_list in meta.get("syns", []) or []:
            for syn in syn_list or []:
                payload["thesaurus"].append({"related_word_text": syn, "relation_type": "SYN"})

        for ant_list in meta.get("ants", []) or []:
            for ant in ant_list or []:
                payload["thesaurus"].append({"related_word_text": ant, "relation_type": "ANT"})

        return payload

    @classmethod
    def fetch_dictionary(cls, word: str):
        word = (word or "").strip().lower()
        api_key = cls._key("MW_DICTIONARY_KEY")
        if not api_key:
            return None, []

        try:
            response = cls._request(cls.DICTIONARY_URL.format(word=word), api_key)
            if response.status_code == 404:
                data = response.json()
                suggestions = data if isinstance(data, list) else []
                return None, _unique_normalized(suggestions[:10])

            if response.status_code != 200:
                return None, []

            data = response.json()
            if not data:
                return None, []

            if isinstance(data[0], str):
                return None, _unique_normalized(data[:10])

            entry = data[0]
            return cls._parse_dictionary_entry(entry), []
        except (requests.RequestException, ValueError, TypeError, KeyError, IndexError) as exc:
            logger.warning("MW dictionary fetch failed for %s: %s", word, exc)
            return None, []

    @classmethod
    def fetch_thesaurus(cls, word: str):
        word = (word or "").strip().lower()
        api_key = cls._key("MW_THESAURUS_KEY")
        if not api_key:
            return None, []

        try:
            response = cls._request(cls.THESAURUS_URL.format(word=word), api_key)
            if response.status_code == 404:
                data = response.json()
                suggestions = data if isinstance(data, list) else []
                return None, _unique_normalized(suggestions[:10])

            if response.status_code != 200:
                return None, []

            data = response.json()
            if not data:
                return None, []

            if isinstance(data[0], str):
                return None, _unique_normalized(data[:10])

            entry = data[0]
            return cls._parse_thesaurus_entry(entry), []
        except (requests.RequestException, ValueError, TypeError, KeyError, IndexError) as exc:
            logger.warning("MW thesaurus fetch failed for %s: %s", word, exc)
            return None, []

