
# qubitgyan-backend/library/api/v2/lexicon/interfaces/api/manager_views.py

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ...models import (
    DailyPracticeSet,
    Meaning,
    Pronunciation,
    Thesaurus,
    Word,
    WordCategory,
    WordOfTheDay,
    WordUsage,
)
from ...serializers import (
    DailyPracticeSetReadSerializer,
    DailyPracticeSetWriteSerializer,
    MeaningSerializer,
    MeaningWriteSerializer,
    PronunciationSerializer,
    PronunciationWriteSerializer,
    ThesaurusSerializer,
    ThesaurusWriteSerializer,
    WordCategorySerializer,
    WordOfTheDayReadSerializer,
    WordOfTheDayWriteSerializer,
    WordReadSerializer,
    WordWriteSerializer,
)


def _prefetch_word(word):
    return Word.objects.prefetch_related(
        "categories",
        "pronunciations",
        "meanings",
        "thesaurus_entries",
    ).get(pk=word.pk)


def _schedule_word_embedding_refresh(word_ids):
    if not word_ids:
        return

    from ...tasks import refresh_word_embedding

    ids = [str(word_id) for word_id in word_ids]
    transaction.on_commit(lambda ids=ids: [refresh_word_embedding.delay(word_id) for word_id in ids])


def _schedule_single_word_embedding_refresh(word):
    _schedule_word_embedding_refresh([word.pk])


def _parse_limit(value, default=100, maximum=500):
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(limit, maximum))


class WordListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        queryset = Word.objects.prefetch_related(
            "categories",
            "pronunciations",
            "meanings",
            "thesaurus_entries",
        ).order_by("-created_at")

        is_sophisticated = request.query_params.get("is_sophisticated")
        if is_sophisticated is not None:
            queryset = queryset.filter(is_sophisticated=str(is_sophisticated).lower() == "true")

        category_id = request.query_params.get("category_id")
        if category_id:
            queryset = queryset.filter(categories__id=category_id)

        search = (request.query_params.get("search") or "").strip().lower()
        if search:
            queryset = queryset.filter(text__icontains=search)

        language = (request.query_params.get("language") or "").strip().lower()
        if language:
            queryset = queryset.filter(language=language)

        limit = _parse_limit(request.query_params.get("limit"), default=100, maximum=500)
        words = queryset.distinct()[:limit]
        return Response(WordReadSerializer(words, many=True).data, status=status.HTTP_200_OK)


class WordManagerView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @transaction.atomic
    def get(self, request, pk):
        word = get_object_or_404(
            Word.objects.prefetch_related(
                "categories",
                "pronunciations",
                "meanings",
                "thesaurus_entries",
            ),
            pk=pk,
        )
        return Response(WordReadSerializer(word).data, status=status.HTTP_200_OK)

    @transaction.atomic
    def post(self, request):
        serializer = WordWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        word = serializer.save(source_api="MANUAL")
        word = _prefetch_word(word)
        _schedule_single_word_embedding_refresh(word)
        return Response(WordReadSerializer(word).data, status=status.HTTP_201_CREATED)

    @transaction.atomic
    def patch(self, request, pk):
        word = get_object_or_404(Word, pk=pk)
        serializer = WordWriteSerializer(word, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        word = serializer.save()
        word = _prefetch_word(word)
        _schedule_single_word_embedding_refresh(word)
        return Response(WordReadSerializer(word).data, status=status.HTTP_200_OK)

    def delete(self, request, pk):
        word = get_object_or_404(Word, pk=pk)
        word.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CategoryListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        categories = WordCategory.objects.all().order_by("name")
        return Response(WordCategorySerializer(categories, many=True).data, status=status.HTTP_200_OK)

    @transaction.atomic
    def post(self, request):
        serializer = WordCategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        return Response(WordCategorySerializer(category).data, status=status.HTTP_201_CREATED)


class CategoryDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @transaction.atomic
    def patch(self, request, pk):
        category = get_object_or_404(WordCategory, pk=pk)
        related_word_ids = list(category.words.values_list("id", flat=True))

        serializer = WordCategorySerializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        category = serializer.save()

        _schedule_word_embedding_refresh(related_word_ids)
        return Response(WordCategorySerializer(category).data, status=status.HTTP_200_OK)

    @transaction.atomic
    def delete(self, request, pk):
        category = get_object_or_404(WordCategory, pk=pk)
        related_word_ids = list(category.words.values_list("id", flat=True))
        category.delete()
        _schedule_word_embedding_refresh(related_word_ids)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AssignWordToCategoryView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @transaction.atomic
    def post(self, request, word_id, category_id):
        word = get_object_or_404(Word, pk=word_id)
        category = get_object_or_404(WordCategory, pk=category_id)
        word.categories.add(category)
        word = _prefetch_word(word)
        _schedule_single_word_embedding_refresh(word)
        return Response(WordReadSerializer(word).data, status=status.HTTP_200_OK)

    @transaction.atomic
    def delete(self, request, word_id, category_id):
        word = get_object_or_404(Word, pk=word_id)
        category = get_object_or_404(WordCategory, pk=category_id)
        word.categories.remove(category)
        word = _prefetch_word(word)
        _schedule_single_word_embedding_refresh(word)
        return Response(WordReadSerializer(word).data, status=status.HTTP_200_OK)


class WordSubEntityMixinView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def _model_and_serializer(self, entity_type):
        entity_type = str(entity_type).lower()
        if entity_type == "meaning":
            return Meaning, MeaningWriteSerializer, MeaningSerializer
        if entity_type == "pronunciation":
            return Pronunciation, PronunciationWriteSerializer, PronunciationSerializer
        if entity_type == "thesaurus":
            return Thesaurus, ThesaurusWriteSerializer, ThesaurusSerializer
        return None, None, None

    @transaction.atomic
    def post(self, request, word_id, entity_type):
        word = get_object_or_404(Word, pk=word_id)
        model_cls, write_serializer_cls, _ = self._model_and_serializer(entity_type)
        if not model_cls:
            return Response({"error": "Invalid entity type."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = write_serializer_cls(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if model_cls is Meaning:
            model_cls.objects.create(word=word, **data)
        elif model_cls is Pronunciation:
            model_cls.objects.create(word=word, **data)
        elif model_cls is Thesaurus:
            related_word = data.pop("related_word", None)
            related_word_text = data.pop("related_word_text", "")
            if related_word and not related_word_text:
                related_word_text = related_word.text
            model_cls.objects.create(
                word=word,
                related_word=related_word,
                related_word_text=related_word_text,
                **data,
            )

        word = _prefetch_word(word)
        _schedule_single_word_embedding_refresh(word)
        return Response(WordReadSerializer(word).data, status=status.HTTP_201_CREATED)

    @transaction.atomic
    def delete(self, request, word_id, entity_type, entity_id):
        word = get_object_or_404(Word, pk=word_id)
        model_cls, _, _ = self._model_and_serializer(entity_type)
        if not model_cls:
            return Response({"error": "Invalid entity type."}, status=status.HTTP_400_BAD_REQUEST)

        obj = get_object_or_404(model_cls, pk=entity_id, word=word)
        obj.delete()

        word = _prefetch_word(word)
        _schedule_single_word_embedding_refresh(word)
        return Response(WordReadSerializer(word).data, status=status.HTTP_200_OK)


class ManualWordOfTheDayView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @transaction.atomic
    def post(self, request):
        serializer = WordOfTheDayWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        wotd, _ = WordOfTheDay.objects.update_or_create(
            date=serializer.validated_data["date"],
            defaults={"word": serializer.validated_data["word"]},
        )

        WordUsage.objects.get_or_create(
            word=serializer.validated_data["word"],
            usage_type="WOTD",
            used_on=serializer.validated_data["date"],
        )

        wotd = WordOfTheDay.objects.select_related("word").prefetch_related(
            "word__categories",
            "word__pronunciations",
            "word__meanings",
            "word__thesaurus_entries",
        ).get(pk=wotd.pk)

        return Response(WordOfTheDayReadSerializer(wotd).data, status=status.HTTP_200_OK)


class ManualDailyPracticeSetView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    @transaction.atomic
    def post(self, request):
        serializer = DailyPracticeSetWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        practice_set, _ = DailyPracticeSet.objects.get_or_create(date=serializer.validated_data["date"])
        practice_set.words.set(serializer.validated_data["words"])

        WordUsage.objects.bulk_create(
            [
                WordUsage(
                    word=word,
                    usage_type="PRACTICE",
                    used_on=serializer.validated_data["date"],
                )
                for word in serializer.validated_data["words"]
            ],
            ignore_conflicts=True,
        )

        practice_set = DailyPracticeSet.objects.prefetch_related(
            "words__categories",
            "words__pronunciations",
            "words__meanings",
            "words__thesaurus_entries",
        ).get(pk=practice_set.pk)

        return Response(DailyPracticeSetReadSerializer(practice_set).data, status=status.HTTP_200_OK)
    
    