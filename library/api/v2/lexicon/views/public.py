import requests
from django.conf import settings
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from datetime import timedelta
import random
from ..models import Word, Pronunciation, Meaning, Thesaurus, DailyPracticeSet, WordOfTheDay
from ..serializers import WordSerializer, DailyPracticeSetSerializer, WordOfTheDaySerializer

class WordSearchView(APIView):
    def get(self, request):
        word_query = request.query_params.get('word', '').strip().lower()
        language = request.query_params.get('lang', 'en').strip().lower()

        if not word_query:
            return Response({"error": "Word parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        word_obj = Word.objects.filter(text=word_query, language=language).first()
        
        if word_obj:
            word_obj.search_count += 1
            word_obj.save(update_fields=['search_count'])
            return Response(WordSerializer(word_obj).data, status=status.HTTP_200_OK)

        return self.fetch_from_free_dictionary(word_query, language)

    def fetch_from_free_dictionary(self, word_query, language):
        url = f"https://api.dictionaryapi.dev/api/v2/entries/{language}/{word_query}"
        response = requests.get(url)
        
        if response.status_code == 200:
            return self._process_fda_response(word_query, language, response.json()[0])
        
        if language == 'en' and hasattr(settings, 'MERRIAM_WEBSTER_API_KEY'):
            return self.fetch_from_merriam_webster(word_query)

        return Response({"error": "Word not found in any dictionary"}, status=status.HTTP_404_NOT_FOUND)

    def _process_fda_response(self, word_query, language, data):
        try:
            with transaction.atomic():
                word_obj = Word.objects.create(
                    text=word_query, language=language,
                    phonetic_text=data.get('phonetic', ''), source_api='FDA',
                    search_count=1
                )

                for phonetic in data.get('phonetics', []):
                    audio = phonetic.get('audio')
                    if audio:
                        region = 'GEN'
                        if '-uk' in audio.lower(): region = 'UK'
                        elif '-us' in audio.lower(): region = 'US'
                        elif '-au' in audio.lower(): region = 'AU'
                        elif '-in' in audio.lower(): region = 'IN'
                        
                        Pronunciation.objects.create(word=word_obj, audio_url=audio, region=region)

                added_relations = set()
                for meaning in data.get('meanings', []):
                    pos = meaning.get('partOfSpeech', '')
                    for def_data in meaning.get('definitions', []):
                        Meaning.objects.create(
                            word=word_obj, part_of_speech=pos,
                            definition=def_data.get('definition', ''), example=def_data.get('example', '')
                        )
                        for syn in def_data.get('synonyms', []):
                            if syn not in added_relations:
                                Thesaurus.objects.create(word=word_obj, related_word=syn, relation_type='SYN')
                                added_relations.add(syn)
                        for ant in def_data.get('antonyms', []):
                            if ant not in added_relations:
                                Thesaurus.objects.create(word=word_obj, related_word=ant, relation_type='ANT')
                                added_relations.add(ant)

            return Response(WordSerializer(word_obj).data, status=status.HTTP_200_OK)
        except Exception:
            return Response({"error": "Failed to process FDA data"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def fetch_from_merriam_webster(self, word_query):
        api_key = settings.MERRIAM_WEBSTER_API_KEY
        url = f"https://www.dictionaryapi.com/api/v3/references/collegiate/json/{word_query}?key={api_key}"
        response = requests.get(url)

        if response.status_code != 200 or not response.json() or isinstance(response.json()[0], str):
            return Response({"error": "Word not found in MW dictionary"}, status=status.HTTP_404_NOT_FOUND)

        data = response.json()[0]
        
        try:
            with transaction.atomic():
                hwi = data.get('hwi', {})
                word_obj = Word.objects.create(
                    text=word_query, language='en',
                    phonetic_text=hwi.get('hw', '').replace('*', ''), source_api='MW',
                    search_count=1
                )

                prs = hwi.get('prs', [])
                if prs and 'sound' in prs[0] and 'audio' in prs[0]['sound']:
                    audio_base = prs[0]['sound']['audio']
                    if audio_base.startswith('bix'): subdir = 'bix'
                    elif audio_base.startswith('gg'): subdir = 'gg'
                    elif audio_base[0].isalpha(): subdir = audio_base[0]
                    else: subdir = 'number'
                    
                    audio_url = f"https://media.merriam-webster.com/audio/prons/en/us/mp3/{subdir}/{audio_base}.mp3"
                    Pronunciation.objects.create(word=word_obj, audio_url=audio_url, region='US')

                part_of_speech = data.get('fl', '')
                for definition in data.get('shortdef', []):
                    Meaning.objects.create(
                        word=word_obj, part_of_speech=part_of_speech, definition=definition
                    )

            return Response(WordSerializer(word_obj).data, status=status.HTTP_200_OK)
        except Exception:
            return Response({"error": "Failed to process MW data"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DailyPracticeSetView(APIView):
    """
    Generates a globally shared daily practice deck.
    Ensures a mix of complex/easy words and prevents 7-day repetition.
    """
    def get(self, request):
        today = timezone.now().date()
        
        practice_set = DailyPracticeSet.objects.prefetch_related(
            'words__categories', 'words__pronunciations', 
            'words__meanings', 'words__thesaurus_entries'
        ).filter(date=today).first()

        if not practice_set:
            with transaction.atomic():
                recent_dates = [today - timedelta(days=i) for i in range(1, 8)]
                recent_word_ids = DailyPracticeSet.objects.filter(
                    date__in=recent_dates
                ).values_list('words__id', flat=True)

                complex_words = list(Word.objects.filter(
                    language='en', is_sophisticated=True
                ).exclude(id__in=recent_word_ids).order_by('?')[:35])
                
                normal_words = list(Word.objects.filter(
                    language='en', is_sophisticated=False
                ).exclude(id__in=recent_word_ids).order_by('?')[:15])
                
                words = complex_words + normal_words

                if len(words) < 50:
                    shortfall = 50 - len(words)
                    used_ids = [w.id for w in words]
                    extra_words = list(Word.objects.filter(language='en')
                                     .exclude(id__in=used_ids).order_by('?')[:shortfall])
                    words += extra_words

                if not words:
                    return Response({"error": "Not enough words in database."}, status=status.HTTP_404_NOT_FOUND)
                
                practice_set = DailyPracticeSet.objects.create(date=today)
                practice_set.words.set(words)

        data = DailyPracticeSetSerializer(practice_set).data
        random.shuffle(data['words'])

        return Response(data, status=status.HTTP_200_OK)


class WordOfTheDayView(APIView):
    def get(self, request):
        today = timezone.now().date()
        wotd = WordOfTheDay.objects.filter(date=today).first()

        if not wotd:
            word = Word.objects.filter(language='en', is_sophisticated=True).order_by('?').first()
            if not word:
                word = Word.objects.filter(language='en').order_by('?').first()
            
            if not word:
                return Response({"error": "No words available."}, status=status.HTTP_404_NOT_FOUND)

            wotd = WordOfTheDay.objects.create(date=today, word=word)

        return Response(WordOfTheDaySerializer(wotd).data, status=status.HTTP_200_OK)


class TrendingWordsView(APIView):
    def get(self, request):
        words = Word.objects.filter(search_count__gt=0).order_by('-search_count')[:20]
        return Response(WordSerializer(words, many=True).data, status=status.HTTP_200_OK)
    
    