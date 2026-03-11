from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from django.shortcuts import get_object_or_404
from ..models import Word, WordCategory, WordOfTheDay
from ..serializers import (
    WordSerializer, 
    WordCategorySerializer, 
    WordOfTheDaySerializer,
    MeaningSerializer, 
    PronunciationSerializer, 
    ThesaurusSerializer
)

class WordListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        queryset = Word.objects.all().order_by('-created_at')
        
        is_sophisticated = request.query_params.get('is_sophisticated')
        if is_sophisticated is not None:
            queryset = queryset.filter(is_sophisticated=is_sophisticated.lower() == 'true')
            
        category_id = request.query_params.get('category_id')
        if category_id:
            queryset = queryset.filter(categories__id=category_id)

        words = queryset[:100] 
        return Response(WordSerializer(words, many=True).data, status=status.HTTP_200_OK)

class WordManagerView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        data = request.data.copy()
        data['source_api'] = 'MANUAL'
        serializer = WordSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        word = get_object_or_404(Word, pk=pk)
        serializer = WordSerializer(word, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class WordSubEntityMixinView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, word_id, entity_type):
        word = get_object_or_404(Word, pk=word_id)
        
        if entity_type == 'meaning':
            serializer = MeaningSerializer(data=request.data)
        elif entity_type == 'pronunciation':
            serializer = PronunciationSerializer(data=request.data)
        elif entity_type == 'thesaurus':
            serializer = ThesaurusSerializer(data=request.data)
        else:
            return Response({"error": "Invalid entity type"}, status=status.HTTP_400_BAD_REQUEST)

        if serializer.is_valid():
            serializer.save(word=word)
            return Response(WordSerializer(word).data, status=status.HTTP_201_CREATED)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CategoryListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        categories = WordCategory.objects.all()
        return Response(WordCategorySerializer(categories, many=True).data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = WordCategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AssignWordToCategoryView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, word_id, category_id):
        word = get_object_or_404(Word, pk=word_id)
        category = get_object_or_404(WordCategory, pk=category_id)
        word.categories.add(category)
        return Response(WordSerializer(word).data, status=status.HTTP_200_OK)

class ManualWordOfTheDayView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        date_str = request.data.get('date')
        word_id = request.data.get('word_id')

        if not date_str or not word_id:
            return Response({"error": "date and word_id are required."}, status=status.HTTP_400_BAD_REQUEST)

        word = get_object_or_404(Word, pk=word_id)
        
        wotd, created = WordOfTheDay.objects.update_or_create(
            date=date_str,
            defaults={'word': word}
        )

        return Response(WordOfTheDaySerializer(wotd).data, status=status.HTTP_200_OK)