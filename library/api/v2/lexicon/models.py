
# qubitgyan-backend/library/api/v2/lexicon/models.py

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

try:
    from pgvector.django import VectorField  # type: ignore
except Exception:  # pragma: no cover
    VectorField = None


def _clean_text(value, *, lower: bool = False) -> str:
    text = (value or "").strip()
    return text.lower() if lower else text


class WordCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Word Categories"
        indexes = [models.Index(fields=["name"])]

    def save(self, *args, **kwargs):
        self.name = _clean_text(self.name)
        if not self.name:
            raise ValidationError({"name": "Category name cannot be empty."})
        if self.description is not None:
            self.description = self.description.strip() or None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Word(models.Model):
    LANGUAGE_CHOICES = [
        ("en", "English"),
        ("hi", "Hindi"),
    ]

    SOURCE_CHOICES = [
        ("FDA", "Free Dictionary API"),
        ("MW", "Merriam-Webster"),
        ("MIXED", "Mixed Sources"),
        ("MANUAL", "Manual Entry"),
        ("IMPORT", "Imported"),
    ]

    WORD_TYPE_CHOICES = [
        ("WORD", "Word"),
        ("IDIOM", "Idiom"),
        ("PHRASAL", "Phrasal Verb"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    text = models.CharField(max_length=100, db_index=True)
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default="en", db_index=True)
    phonetic_text = models.CharField(max_length=100, blank=True, null=True)

    is_sophisticated = models.BooleanField(default=False, db_index=True)
    difficulty_score = models.FloatField(default=0.0, db_index=True)

    source_api = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="MANUAL")
    source_reference = models.CharField(max_length=255, blank=True, null=True)

    word_type = models.CharField(max_length=10, choices=WORD_TYPE_CHOICES, default="WORD")
    search_count = models.PositiveIntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    categories = models.ManyToManyField(WordCategory, related_name="words", blank=True)

    if VectorField is not None:
        embedding = VectorField(dimensions=384, null=True, blank=True)
    else:
        embedding = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["text", "language"], name="unique_word_per_language")
        ]
        indexes = [
            models.Index(fields=["text", "language"]),
            models.Index(fields=["is_sophisticated", "language"]),
            models.Index(fields=["search_count"]),
            models.Index(fields=["is_active", "language"]),
        ]

    def save(self, *args, **kwargs):
        self.text = _clean_text(self.text, lower=True)
        if not self.text:
            raise ValidationError({"text": "Word text cannot be empty."})
        self.language = _clean_text(self.language, lower=True) or "en"
        if self.phonetic_text is not None:
            self.phonetic_text = _clean_text(self.phonetic_text) or None
        if self.source_api:
            self.source_api = str(self.source_api).strip().upper()
        if self.source_reference is not None:
            self.source_reference = self.source_reference.strip() or None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.text} ({self.language})"


class Pronunciation(models.Model):
    REGION_CHOICES = [
        ("UK", "British English"),
        ("US", "American English"),
        ("SCO", "Scottish English"),
        ("IN", "Indian English"),
        ("GEN", "General/Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name="pronunciations")
    audio_url = models.URLField(max_length=500)
    region = models.CharField(max_length=3, choices=REGION_CHOICES, default="GEN")

    class Meta:
        indexes = [models.Index(fields=["region"])]

    def save(self, *args, **kwargs):
        self.audio_url = _clean_text(self.audio_url)
        self.region = _clean_text(self.region, lower=False).upper() or "GEN"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.word.text} - {self.get_region_display()}"


class Meaning(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name="meanings")
    part_of_speech = models.CharField(max_length=50, db_index=True)
    definition = models.TextField()
    example = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [models.Index(fields=["part_of_speech"])]

    def save(self, *args, **kwargs):
        self.part_of_speech = _clean_text(self.part_of_speech)
        self.definition = _clean_text(self.definition)
        if not self.part_of_speech:
            raise ValidationError({"part_of_speech": "Part of speech cannot be empty."})
        if not self.definition:
            raise ValidationError({"definition": "Definition cannot be empty."})
        if self.example is not None:
            self.example = self.example.strip() or None
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.word.text} ({self.part_of_speech})"


class Thesaurus(models.Model):
    RELATION_CHOICES = [
        ("SYN", "Synonym"),
        ("ANT", "Antonym"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name="thesaurus_entries")
    related_word = models.ForeignKey(
        Word,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reverse_thesaurus_entries",
    )
    related_word_text = models.CharField(max_length=100, blank=True, null=True, default="")
    relation_type = models.CharField(max_length=3, choices=RELATION_CHOICES, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["relation_type"]),
            models.Index(fields=["related_word_text"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["word", "related_word_text", "relation_type"],
                name="unique_thesaurus_relation_per_word",
            )
        ]

    def save(self, *args, **kwargs):
        if self.related_word and not self.related_word_text:
            self.related_word_text = self.related_word.text

        self.related_word_text = (self.related_word_text or "").strip().lower()
        self.relation_type = (self.relation_type or "").strip().upper()

        if not self.related_word_text:
            raise ValidationError({"related_word_text": "Related word text cannot be empty."})

        if self.relation_type not in {"SYN", "ANT"}:
            raise ValidationError({"relation_type": "Invalid relation type."})

        self.full_clean(exclude=None)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_relation_type_display()} of {self.word.text}: {self.related_word_text}"


class WordOfTheDay(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField(unique=True, db_index=True)
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name="wotd_entries")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.date} - {self.word.text}"


class DailyPracticeSet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField(unique=True, db_index=True)
    words = models.ManyToManyField(Word, related_name="practice_sets")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Practice Set: {self.date}"


class WordUsage(models.Model):
    USAGE_TYPE = [
        ("WOTD", "Word of the Day"),
        ("PRACTICE", "Practice Set"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name="usages")
    usage_type = models.CharField(max_length=10, choices=USAGE_TYPE, db_index=True)
    used_on = models.DateField(db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["word", "usage_type", "used_on"], name="unique_word_usage_per_day")
        ]
        indexes = [
            models.Index(fields=["usage_type", "used_on"]),
            models.Index(fields=["word", "used_on"]),
        ]

    def save(self, *args, **kwargs):
        self.usage_type = _clean_text(self.usage_type, lower=False).upper()
        if self.usage_type not in {"WOTD", "PRACTICE"}:
            raise ValidationError({"usage_type": "Invalid usage type."})
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.word.text} - {self.usage_type} - {self.used_on}"
    
