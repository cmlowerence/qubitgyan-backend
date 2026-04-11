# qubitgyan-backend/library/api/v2/lexicon/admin.py

from django.contrib import admin

from .models import (
    DailyPracticeSet,
    Meaning,
    Pronunciation,
    Thesaurus,
    Word,
    WordCategory,
    WordOfTheDay,
    WordUsage,
)


class MeaningInline(admin.TabularInline):
    model = Meaning
    extra = 1


class PronunciationInline(admin.TabularInline):
    model = Pronunciation
    extra = 1


class ThesaurusInline(admin.TabularInline):
    model = Thesaurus
    fk_name = "word"
    extra = 1


class WordUsageInline(admin.TabularInline):
    model = WordUsage
    extra = 0
    readonly_fields = ("usage_type", "used_on")
    can_delete = False
    max_num = 0


@admin.register(Word)
class WordAdmin(admin.ModelAdmin):
    list_display = (
        "text",
        "language",
        "word_type",
        "is_sophisticated",
        "difficulty_score",
        "search_count",
        "source_api",
        "is_active",
    )
    list_filter = ("language", "word_type", "is_sophisticated", "source_api", "is_active")
    search_fields = ("text", "phonetic_text", "meanings__definition")
    ordering = ("text",)
    autocomplete_fields = ("categories",)
    inlines = [MeaningInline, PronunciationInline, ThesaurusInline, WordUsageInline]


@admin.register(WordCategory)
class WordCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name", "description")
    ordering = ("name",)


@admin.register(WordOfTheDay)
class WordOfTheDayAdmin(admin.ModelAdmin):
    list_display = ("date", "word")
    search_fields = ("word__text",)
    ordering = ("-date",)


@admin.register(DailyPracticeSet)
class DailyPracticeSetAdmin(admin.ModelAdmin):
    list_display = ("date", "created_at")
    search_fields = ("words__text",)
    ordering = ("-date",)
    filter_horizontal = ("words",)


@admin.register(WordUsage)
class WordUsageAdmin(admin.ModelAdmin):
    list_display = ("word", "usage_type", "used_on")
    list_filter = ("usage_type", "used_on")
    search_fields = ("word__text",)
    ordering = ("-used_on",)


admin.site.register(Meaning)
admin.site.register(Pronunciation)
admin.site.register(Thesaurus)
