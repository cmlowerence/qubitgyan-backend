from copy import deepcopy

from django.core.cache import cache
from django.db.models import F
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ...application.constants import TRENDING_CACHE_SECONDS, WORD_CACHE_SECONDS
from ...application.use_cases.search_word import bootstrap_daily_lexicon, fetch_and_store_word
from ...application.utils.embeddings import search_words_by_similarity
from ...models import Word
from ...serializers import DailyPracticeSetReadSerializer, WordOfTheDayReadSerializer, WordReadSerializer


CACHE_VERSION = "v5"
SEMANTIC_CACHE_SECONDS = 900


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
        semantic_requested = str(request.query_params.get("semantic") or "").strip().lower() in {"1", "true", "yes"}

        if not word_query:
            return Response({"error": "Word parameter is required."}, status=status.HTTP_400_BAD_REQUEST)

        if semantic_requested:
            cache_key = f"lexicon:{CACHE_VERSION}:semantic:{language}:{word_query}"
            cached = cache.get(cache_key)
            if cached is not None:
                return Response(cached, status=status.HTTP_200_OK)

            results = search_words_by_similarity(word_query, language=language, limit=20)
            payload = {
                "query": word_query,
                "language": language,
                "mode": "semantic",
                "results": WordReadSerializer(results, many=True).data,
            }
            cache.set(cache_key, payload, SEMANTIC_CACHE_SECONDS)
            return Response(payload, status=status.HTTP_200_OK)

        cache_key = f"lexicon:{CACHE_VERSION}:search:{language}:{word_query}"
        cached = cache.get(cache_key)

        if cached is not None:
            Word.objects.filter(text=word_query, language=language).update(search_count=F("search_count") + 1)

            response_data = deepcopy(cached)
            response_data["search_count"] = response_data.get("search_count", 0) + 1

            return Response(response_data, status=status.HTTP_200_OK)

        word_obj, suggestions = fetch_and_store_word(
            word_query,
            language,
            increment_search_count=True,
        )

        if word_obj:
            serialized = WordReadSerializer(word_obj).data
            cache.set(cache_key, serialized, WORD_CACHE_SECONDS)
            return Response(serialized, status=status.HTTP_200_OK)

        if suggestions:
            return Response(
                {"error": "Word not found. Did you mean?", "suggestions": suggestions},
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {"error": "Word not found in any dictionary."},
            status=status.HTTP_404_NOT_FOUND,
        )


class DailyPracticeSetView(APIView):
    def get(self, request):
        result = bootstrap_daily_lexicon(
            date=timezone.localdate(),
            practice_count=18,
        )

        if result.get("status") != "ready" or not result.get("practice_set"):
            return Response(result, status=status.HTTP_202_ACCEPTED)

        return Response(
            DailyPracticeSetReadSerializer(result["practice_set"]).data,
            status=status.HTTP_200_OK,
        )


class WordOfTheDayView(APIView):
    def get(self, request):
        result = bootstrap_daily_lexicon(
            date=timezone.localdate(),
            practice_count=18,
        )

        if result.get("status") != "ready" or not result.get("wotd"):
            return Response(result, status=status.HTTP_202_ACCEPTED)

        return Response(
            WordOfTheDayReadSerializer(result["wotd"]).data,
            status=status.HTTP_200_OK,
        )


class TrendingWordsView(APIView):
    def get(self, request):
        cache_key = f"lexicon:{CACHE_VERSION}:trending:top20"
        cached = cache.get(cache_key)

        if cached is not None:
            return Response(cached, status=status.HTTP_200_OK)

        words = (
            _prefetched_word_queryset()
            .filter(search_count__gt=0, is_active=True)
            .only("id", "text", "search_count", "updated_at")
            .order_by("-search_count", "-updated_at")[:20]
        )

        data = WordReadSerializer(words, many=True).data
        cache.set(cache_key, data, TRENDING_CACHE_SECONDS)

        return Response(data, status=status.HTTP_200_OK)
        
        