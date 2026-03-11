from rest_framework import serializers
from .models import WordCategory, Word, Pronunciation, Meaning, Thesaurus, WordOfTheDay, DailyPracticeSet

class WordCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = WordCategory
        fields = ['id', 'name', 'description']

class PronunciationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pronunciation
        fields = ['id', 'audio_url', 'region']

class MeaningSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meaning
        fields = ['id', 'part_of_speech', 'definition', 'example']

class ThesaurusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Thesaurus
        fields = ['id', 'related_word', 'relation_type']

class WordSerializer(serializers.ModelSerializer):
    categories = WordCategorySerializer(many=True, read_only=True)
    pronunciations = PronunciationSerializer(many=True, read_only=True)
    meanings = MeaningSerializer(many=True, read_only=True)
    thesaurus_entries = ThesaurusSerializer(many=True, read_only=True)

    class Meta:
        model = Word
        fields = [
            'id', 'text', 'language', 'phonetic_text', 'is_sophisticated',
            'source_api', 'word_type', 'search_count', 'categories', 
            'pronunciations', 'meanings', 'thesaurus_entries', 
            'created_at', 'updated_at'
        ]

class WordOfTheDaySerializer(serializers.ModelSerializer):
    word = WordSerializer(read_only=True)

    class Meta:
        model = WordOfTheDay
        fields = ['id', 'date', 'word']

class DailyPracticeSetSerializer(serializers.ModelSerializer):
    words = WordSerializer(many=True, read_only=True)

    class Meta:
        model = DailyPracticeSet
        fields = ['id', 'date', 'words']

        