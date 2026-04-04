
# # qubitgyan-backend/library/api/v2/lexicon/application/utils.py

# import random
# import re
# from typing import Any, Iterable


# def normalize_text(value: Any) -> str:
#     return str(value or "").strip().lower()


# def approximate_syllables(word: str) -> int:
#     word = normalize_text(word)
#     if not word:
#         return 0

#     count = len(re.findall(r"[aeiouy]+", word))
#     if word.endswith(("e", "es", "ed")) and count > 1:
#         count -= 1
#     return max(1, count)


# def calculate_difficulty_score(
#     text: str,
#     meanings_count: int = 0,
#     pronunciation_count: int = 0,
#     thesaurus_count: int = 0,
# ) -> float:
#     text = normalize_text(text)
#     if not text:
#         return 0.0

#     length_score = min(len(text) / 16.0, 1.0)
#     syllable_score = min(approximate_syllables(text) / 5.0, 1.0)
#     rarity_bonus = 0.08 if len(text) >= 8 else 0.0
#     meaning_bonus = min(meanings_count * 0.04, 0.12)
#     pronunciation_bonus = 0.04 if pronunciation_count else 0.0
#     thesaurus_bonus = min(thesaurus_count * 0.02, 0.08)

#     score = (
#         (0.45 * length_score)
#         + (0.35 * syllable_score)
#         + rarity_bonus
#         + meaning_bonus
#         + pronunciation_bonus
#         + thesaurus_bonus
#     )
#     return round(min(score, 1.0), 3)


# def is_sophisticated_word(text: str, score: float | None = None) -> bool:
#     if score is None:
#         score = calculate_difficulty_score(text)
#     return score >= 0.55


# def unique_list(items: Iterable[Any]):
#     seen = set()
#     output = []
#     for item in items:
#         key = str(item)
#         if key in seen:
#             continue
#         seen.add(key)
#         output.append(item)
#     return output


# def sample_items(items, count: int):
#     items = list(items)
#     if count <= 0:
#         return []
#     if len(items) <= count:
#         return items
#     return random.sample(items, count)
