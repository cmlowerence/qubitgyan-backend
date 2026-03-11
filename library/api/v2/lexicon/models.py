import uuid
from django.db import models

class WordCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Word Categories"

    def __str__(self):
        return self.name

class Word(models.Model):
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('hi', 'Hindi'),
    ]
    SOURCE_CHOICES = [
        ('FDA', 'Free Dictionary API'),
        ('MW', 'Merriam-Webster'),
        ('MANUAL', 'Manual Entry'),
    ]
    WORD_TYPE_CHOICES = [
        ('WORD', 'Word'),
        ('IDIOM', 'Idiom'),
        ('PHRASAL', 'Phrasal Verb'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    text = models.CharField(max_length=100, db_index=True) 
    language = models.CharField(max_length=5, choices=LANGUAGE_CHOICES, default='en')
    phonetic_text = models.CharField(max_length=100, blank=True, null=True)
    
    is_sophisticated = models.BooleanField(default=False)
    source_api = models.CharField(max_length=10, choices=SOURCE_CHOICES, default='FDA')
    word_type = models.CharField(max_length=10, choices=WORD_TYPE_CHOICES, default='WORD')
    search_count = models.IntegerField(default=0)
    
    categories = models.ManyToManyField(WordCategory, related_name='words', blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['text', 'language'], name='unique_word_per_language')
        ]

    def __str__(self):
        return f"{self.text} ({self.language})"

class Pronunciation(models.Model):
    REGION_CHOICES = [
        ('UK', 'British English'),
        ('US', 'American English'),
        ('SCO', 'Scottish English'),
        ('IN', 'Indian English'),
        ('GEN', 'General/Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='pronunciations')
    audio_url = models.URLField(max_length=500)
    region = models.CharField(max_length=3, choices=REGION_CHOICES, default='GEN')

    def __str__(self):
        return f"{self.word.text} - {self.get_region_display()}"

class Meaning(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='meanings')
    part_of_speech = models.CharField(max_length=50)
    definition = models.TextField()
    example = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.word.text} ({self.part_of_speech})"

class Thesaurus(models.Model):
    RELATION_CHOICES = [
        ('SYN', 'Synonym'),
        ('ANT', 'Antonym'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='thesaurus_entries')
    related_word = models.CharField(max_length=100)
    relation_type = models.CharField(max_length=3, choices=RELATION_CHOICES)

    def __str__(self):
        return f"{self.get_relation_type_display()} of {self.word.text}: {self.related_word}"

class WordOfTheDay(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField(unique=True, db_index=True)
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='wotd_entries')

    def __str__(self):
        return f"{self.date} - {self.word.text}"

class DailyPracticeSet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField(unique=True, db_index=True)
    words = models.ManyToManyField(Word, related_name='practice_sets')

    def __str__(self):
        return f"Practice Set: {self.date}"