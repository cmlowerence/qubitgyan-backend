# qubitgyan-backend/library/api/v2/lexicon/interfaces/api/public_views.py

from copy import deepcopy

from django.core.cache import cache
from django.db.models import F
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ...application.constants import TRENDING_CACHE_SECONDS, WORD_CACHE_SECONDS
from ...application.use_cases.generate_daily_set import generate_daily_practice_set
from ...application.use_cases.generate_wotd import generate_word_of_the_day
from ...application.use_cases.search_word import fetch_and_store_word
from ...models import Word
from ...serializers import DailyPracticeSetReadSerializer, WordOfTheDayReadSerializer, WordReadSerializer


def _prefetched_word_queryset():
    return Word.objects.prefetch_related(
        "categories",
        "pronunciations",
        "meanings",
        "thesaurus_entries",
    )


class WordSearchView(APIView):
    def get(self, request):
        raw_word = request.query_params.get("word") or ""
        word_query = raw_word.strip().strip('"').strip("'").lower()
        language = (request.query_params.get("lang") or "en").strip().lower()

        if not word_query:
            return Response({"error": "Word parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        cache_key = f"lexicon:search:{language}:{word_query}"
        cached = cache.get(cache_key)

        if cached is not None:
            Word.objects.filter(text=word_query, language=language).update(search_count=F("search_count") + 1)

            response_data = deepcopy(cached)
            response_data["search_count"] = response_data.get("search_count", 0) + 1

            return Response(response_data, status=status.HTTP_200_OK)

        word_obj, suggestions = fetch_and_store_word(word_query, language, increment_search_count=True)

        if word_obj:
            serialized = WordReadSerializer(word_obj).data
            cache.set(cache_key, serialized, WORD_CACHE_SECONDS)
            return Response(serialized, status=status.HTTP_200_OK)

        if suggestions:
            return Response(
                {"error": "Word not found. Did you mean?", "suggestions": suggestions},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response({"error": "Word not found in any dictionary."}, status=status.HTTP_404_NOT_FOUND)


class DailyPracticeSetView(APIView):
    def get(self, request):
        try:
            practice_set = generate_daily_practice_set()
            return Response(DailyPracticeSetReadSerializer(practice_set).data, status=status.HTTP_200_OK)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)


class WordOfTheDayView(APIView):
    def get(self, request):
        try:
            wotd = generate_word_of_the_day()
            return Response(WordOfTheDayReadSerializer(wotd).data, status=status.HTTP_200_OK)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_404_NOT_FOUND)


class TrendingWordsView(APIView):
    def get(self, request):
        cache_key = "lexicon:trending:top20"
        cached = cache.get(cache_key)

        if cached is not None:
            return Response(cached, status=status.HTTP_200_OK)

        words = (
            _prefetched_word_queryset()
            .filter(search_count__gt=0, is_active=True)
            .order_by("-search_count", "-updated_at")[:20]
        )

        data = WordReadSerializer(words, many=True).data
        cache.set(cache_key, data, TRENDING_CACHE_SECONDS)

        return Response(data, status=status.HTTP_200_OK)
    
    