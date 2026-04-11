
# qubitgyan-backend/library/api/v2/lexicon/serializers.py

from rest_framework import serializers

from .models import (
    DailyPracticeSet,
    Meaning,
    Pronunciation,
    Thesaurus,
    Word,
    WordCategory,
    WordOfTheDay,
)


class WordCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = WordCategory
        fields = ["id", "name", "description", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("Category name cannot be empty.")
        return value


class PronunciationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pronunciation
        fields = ["id", "audio_url", "region"]
        read_only_fields = ["id"]


class MeaningSerializer(serializers.ModelSerializer):
    class Meta:
        model = Meaning
        fields = ["id", "part_of_speech", "definition", "example"]
        read_only_fields = ["id"]


class ThesaurusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Thesaurus
        fields = ["id", "related_word_text", "relation_type"]
        read_only_fields = ["id"]


class WordReadSerializer(serializers.ModelSerializer):
    categories = WordCategorySerializer(many=True, read_only=True)
    pronunciations = PronunciationSerializer(many=True, read_only=True)
    meanings = MeaningSerializer(many=True, read_only=True)
    thesaurus_entries = ThesaurusSerializer(many=True, read_only=True)

    class Meta:
        model = Word
        fields = [
            "id",
            "text",
            "language",
            "phonetic_text",
            "is_sophisticated",
            "difficulty_score",
            "source_api",
            "source_reference",
            "word_type",
            "search_count",
            "is_active",
            "categories",
            "pronunciations",
            "meanings",
            "thesaurus_entries",
            "created_at",
            "updated_at",
        ]


class PronunciationWriteSerializer(serializers.Serializer):
    audio_url = serializers.URLField(max_length=500)
    region = serializers.ChoiceField(
        choices=[("UK", "UK"), ("US", "US"), ("SCO", "SCO"), ("IN", "IN"), ("GEN", "GEN")]
    )


class MeaningWriteSerializer(serializers.Serializer):
    part_of_speech = serializers.CharField(max_length=50)
    definition = serializers.CharField()
    example = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class ThesaurusWriteSerializer(serializers.Serializer):
    related_word = serializers.PrimaryKeyRelatedField(queryset=Word.objects.all(), required=False, allow_null=True)
    related_word_text = serializers.CharField(max_length=100, required=False, allow_blank=True)
    relation_type = serializers.ChoiceField(choices=[("SYN", "SYN"), ("ANT", "ANT")])

    def validate(self, attrs):
        related_word = attrs.get("related_word")
        related_word_text = (attrs.get("related_word_text") or "").strip().lower()

        if related_word_text:
            attrs["related_word_text"] = related_word_text

        if not related_word and not related_word_text:
            raise serializers.ValidationError("Provide either related_word or related_word_text.")

        if related_word and not related_word_text:
            attrs["related_word_text"] = related_word.text

        return attrs


class WordWriteSerializer(serializers.ModelSerializer):
    categories = serializers.PrimaryKeyRelatedField(queryset=WordCategory.objects.all(), many=True, required=False)
    meanings = MeaningWriteSerializer(many=True, required=False)
    pronunciations = PronunciationWriteSerializer(many=True, required=False)
    thesaurus_entries = ThesaurusWriteSerializer(many=True, required=False)

    class Meta:
        model = Word
        fields = [
            "text",
            "language",
            "phonetic_text",
            "is_sophisticated",
            "difficulty_score",
            "source_api",
            "source_reference",
            "word_type",
            "is_active",
            "categories",
            "meanings",
            "pronunciations",
            "thesaurus_entries",
        ]

    def validate_text(self, value):
        value = (value or "").strip().lower()
        if not value:
            raise serializers.ValidationError("Word text cannot be empty.")
        return value

    def validate_language(self, value):
        value = (value or "").strip().lower() or "en"
        return value
    
    def _persist_relations(self, word, categories=None, meanings=None, pronunciations=None, thesaurus_entries=None):
        if categories is not None:
            word.categories.set(categories)

        if meanings is not None:
            Meaning.objects.filter(word=word).exclude(
                part_of_speech__in=[m["part_of_speech"] for m in meanings]
            ).delete()
            Meaning.objects.bulk_create([Meaning(word=word, **item) for item in meanings], ignore_conflicts=True)

        if pronunciations is not None:
            Pronunciation.objects.filter(word=word).delete()
            Pronunciation.objects.bulk_create([Pronunciation(word=word, **item) for item in pronunciations], ignore_conflicts=True)

        if thesaurus_entries is not None:
            instances = []
            for item in thesaurus_entries:
                related_word = item.get("related_word")
                related_word_text = item.get("related_word_text", "")
                if related_word and not related_word_text:
                    related_word_text = related_word.text
                instances.append(
                    Thesaurus(
                        word=word,
                        related_word=related_word,
                        related_word_text=related_word_text,
                        relation_type=item["relation_type"],
                    )
                )
            Thesaurus.objects.bulk_create(instances, ignore_conflicts=True)


    def create(self, validated_data):
        categories = validated_data.pop("categories", None)
        meanings = validated_data.pop("meanings", None)
        pronunciations = validated_data.pop("pronunciations", None)
        thesaurus_entries = validated_data.pop("thesaurus_entries", None)

        validated_data.setdefault("source_api", "MANUAL")
        word = Word.objects.create(**validated_data)
        self._persist_relations(word, categories, meanings, pronunciations, thesaurus_entries)
        return word

    def update(self, instance, validated_data):
        categories = validated_data.pop("categories", None)
        meanings = validated_data.pop("meanings", None)
        pronunciations = validated_data.pop("pronunciations", None)
        thesaurus_entries = validated_data.pop("thesaurus_entries", None)

        for attr, value in validated_data.items():
            if attr == "text" and value is not None:
                value = value.strip().lower()
            if attr == "language" and value is not None:
                value = value.strip().lower() or "en"
            setattr(instance, attr, value)

        instance.save()
        self._persist_relations(instance, categories, meanings, pronunciations, thesaurus_entries)
        return instance


class WordOfTheDayReadSerializer(serializers.ModelSerializer):
    word = WordReadSerializer(read_only=True)

    class Meta:
        model = WordOfTheDay
        fields = ["id", "date", "word", "created_at"]


class WordOfTheDayWriteSerializer(serializers.ModelSerializer):
    word = serializers.PrimaryKeyRelatedField(queryset=Word.objects.all())

    class Meta:
        model = WordOfTheDay
        fields = ["date", "word"]

    def validate(self, attrs):
        date = attrs.get("date")
        word = attrs.get("word")
        if date and word and word.language != "en":
            raise serializers.ValidationError({"word": "Word of the day must be in English."})
        return attrs


class DailyPracticeSetReadSerializer(serializers.ModelSerializer):
    words = WordReadSerializer(many=True, read_only=True)

    class Meta:
        model = DailyPracticeSet
        fields = ["id", "date", "words", "created_at"]


class DailyPracticeSetWriteSerializer(serializers.Serializer):
    date = serializers.DateField()
    words = serializers.PrimaryKeyRelatedField(queryset=Word.objects.all(), many=True)

    def validate_words(self, value):
        unique_words = []
        seen = set()
        for word in value:
            if word.pk in seen:
                continue
            seen.add(word.pk)
            unique_words.append(word)

        if len(unique_words) < 15 or len(unique_words) > 20:
            raise serializers.ValidationError("Daily practice sets must contain between 15 and 20 unique words.")

        return unique_words
