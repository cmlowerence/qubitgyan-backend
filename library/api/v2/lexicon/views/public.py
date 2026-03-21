import logging
import random
import requests
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from ..models import Word, Pronunciation, Meaning, Thesaurus, DailyPracticeSet, WordOfTheDay
from ..serializers import WordSerializer, DailyPracticeSetSerializer, WordOfTheDaySerializer

logger = logging.getLogger(__name__)

# A pool of words to fuel the DB when it runs low.
# You can expand this array to thousands of words later.
SEED_WORDS = [
    "aberration", "benevolent", "capricious", "dichotomy", "ephemeral",
    "fastidious", "garrulous", "harangue", "iconoclast", "juxtapose",
    "cacophony", "luminous", "malleable", "nefarious", "obfuscate",
    "paradigm", "quixotic", "resilient", "sycophant", "trepidation",
    "ubiquitous", "vacillate", "wane", "xenophobia", "zealous",
    "apple", "brave", "cat", "dog", "elephant", "forest", "guitar"
]

# ==========================================
# CORE UTILITY: Fetch & Store Logic
# ==========================================
def fetch_and_store_word(word_query, language='en'):
    """
    Fetches a word from FDA and MW, consolidates it, and saves it.
    Returns: (Word Object, List of Suggestions)
    """
    # Prevent duplicate fetching if multiple views request it simultaneously
    existing_word = Word.objects.filter(text=word_query, language=language).first()
    if existing_word:
        return existing_word, []

    fda_data, mw_dict_data, mw_thes_data = None, None, None
    suggestions = []

    # --- STEP 1: Fetch Free Dictionary API (FDA) ---
    try:
        resp = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/{language}/{word_query}", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data and isinstance(data, list):
                fda_data = data[0]
    except (requests.RequestException, ValueError) as e:
        logger.warning(f"FDA fetch failed for {word_query}: {e}")

    has_audio = False
    has_meanings = False
    has_thesaurus = False

    if fda_data:
        has_meanings = bool(fda_data.get('meanings'))
        has_audio = any(p.get('audio') for p in fda_data.get('phonetics', []))
        for meaning in fda_data.get('meanings', []):
            if meaning.get('synonyms') or meaning.get('antonyms'):
                has_thesaurus = True

    # --- STEP 2: Fill in the blanks with Merriam-Webster ---
    if language == 'en':
        dict_key = getattr(settings, 'MW_DICTIONARY_KEY', None)
        thes_key = getattr(settings, 'MW_THESAURUS_KEY', None)

        if dict_key and (not fda_data or not has_audio or not has_meanings):
            try:
                resp = requests.get(f"https://www.dictionaryapi.com/api/v3/references/collegiate/json/{word_query}?key={dict_key}", timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    if data:
                        if isinstance(data[0], str):
                            suggestions = data[:5]
                        else:
                            mw_dict_data = data[0]
            except Exception as e:
                logger.warning(f"MW Dict fetch failed for {word_query}: {e}")

        if thes_key and not has_thesaurus and (fda_data or mw_dict_data):
            try:
                resp = requests.get(f"https://www.dictionaryapi.com/api/v3/references/thesaurus/json/{word_query}?key={thes_key}", timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    if data and not isinstance(data[0], str):
                        mw_thes_data = data[0]
            except Exception as e:
                logger.warning(f"MW Thesaurus fetch failed for {word_query}: {e}")

    # --- STEP 3: Abort if no data found ---
    if not fda_data and not mw_dict_data:
        return None, suggestions

    # --- STEP 4: Consolidate and Save to Database ---
    try:
        with transaction.atomic():
            phonetic_text = ''
            if fda_data and fda_data.get('phonetic'):
                phonetic_text = fda_data.get('phonetic')
            elif mw_dict_data:
                phonetic_text = mw_dict_data.get('hwi', {}).get('hw', '').replace('*', '')

            source = 'FDA+MW' if fda_data and (mw_dict_data or mw_thes_data) else ('FDA' if fda_data else 'MW')

            # Determine if it's likely sophisticated based on length as a fallback
            is_sophisticated = len(word_query) > 7 

            word_obj = Word.objects.create(
                text=word_query, language=language,
                phonetic_text=phonetic_text, source_api=source, 
                search_count=1, is_sophisticated=is_sophisticated
            )

            # Process Audio 
            if has_audio:
                for phonetic in fda_data.get('phonetics', []):
                    audio = phonetic.get('audio')
                    if audio:
                        region = 'GEN'
                        if '-uk' in audio.lower(): region = 'UK'
                        elif '-us' in audio.lower(): region = 'US'
                        elif '-au' in audio.lower(): region = 'AU'
                        elif '-in' in audio.lower(): region = 'IN'
                        Pronunciation.objects.create(word=word_obj, audio_url=audio, region=region)
            elif mw_dict_data:
                prs = mw_dict_data.get('hwi', {}).get('prs', [])
                if prs and 'sound' in prs[0] and 'audio' in prs[0]['sound']:
                    audio_base = prs[0]['sound']['audio']
                    subdir = audio_base[0] if audio_base[0].isalpha() else 'number'
                    if audio_base.startswith('bix'): subdir = 'bix'
                    elif audio_base.startswith('gg'): subdir = 'gg'
                    audio_url = f"https://media.merriam-webster.com/audio/prons/en/us/mp3/{subdir}/{audio_base}.mp3"
                    Pronunciation.objects.create(word=word_obj, audio_url=audio_url, region='US')

            # Process Meanings
            if has_meanings:
                for meaning in fda_data.get('meanings', []):
                    pos = meaning.get('partOfSpeech', '')
                    for def_data in meaning.get('definitions', []):
                        Meaning.objects.create(
                            word=word_obj, part_of_speech=pos,
                            definition=def_data.get('definition', ''),
                            example=def_data.get('example', '')
                        )
            elif mw_dict_data:
                pos = mw_dict_data.get('fl', '')
                for definition in mw_dict_data.get('shortdef', []):
                    Meaning.objects.create(word=word_obj, part_of_speech=pos, definition=definition)

            # Process Thesaurus Entries
            added_relations = set()
            if has_thesaurus:
                for meaning in fda_data.get('meanings', []):
                    for syn in meaning.get('synonyms', []) + [s for d in meaning.get('definitions', []) for s in d.get('synonyms', [])]:
                        if syn not in added_relations:
                            Thesaurus.objects.create(word=word_obj, related_word=syn, relation_type='SYN')
                            added_relations.add(syn)
                    for ant in meaning.get('antonyms', []) + [a for d in meaning.get('definitions', []) for a in d.get('antonyms', [])]:
                        if ant not in added_relations:
                            Thesaurus.objects.create(word=word_obj, related_word=ant, relation_type='ANT')
                            added_relations.add(ant)
            if mw_thes_data:
                meta = mw_thes_data.get('meta', {})
                for syn_list in meta.get('syns', []):
                    for syn in syn_list:
                        if syn not in added_relations:
                            Thesaurus.objects.create(word=word_obj, related_word=syn, relation_type='SYN')
                            added_relations.add(syn)
                for ant_list in meta.get('ants', []):
                    for ant in ant_list:
                        if ant not in added_relations:
                            Thesaurus.objects.create(word=word_obj, related_word=ant, relation_type='ANT')
                            added_relations.add(ant)

        return word_obj, []

    except Exception as e:
        logger.error(f"DB Saving Error for {word_query}: {str(e)}")
        return None, []


# ==========================================
# API VIEWS
# ==========================================
class WordSearchView(APIView):
    def get(self, request):
        word_query = request.query_params.get('word', '').strip(' "\'').lower()
        language = request.query_params.get('lang', 'en').strip().lower()

        if not word_query:
            return Response({"error": "Word parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        word_obj = Word.objects.filter(text=word_query, language=language).first()
        
        if word_obj:
            word_obj.search_count += 1
            word_obj.save(update_fields=['search_count'])
            return Response(WordSerializer(word_obj).data, status=status.HTTP_200_OK)

        word_obj, suggestions = fetch_and_store_word(word_query, language)
        
        if word_obj:
            return Response(WordSerializer(word_obj).data, status=status.HTTP_200_OK)
        
        if suggestions:
            return Response({"error": "Word not found. Did you mean?", "suggestions": suggestions}, status=status.HTTP_404_NOT_FOUND)
            
        return Response({"error": "Word not found in any dictionary"}, status=status.HTTP_404_NOT_FOUND)


class DailyPracticeSetView(APIView):
    def get(self, request):
        today = timezone.now().date()
        
        practice_set = DailyPracticeSet.objects.prefetch_related(
            'words__categories', 'words__pronunciations', 
            'words__meanings', 'words__thesaurus_entries'
        ).filter(date=today).first()

        if not practice_set:
            # 1. Find words we've used recently (last 14 days to ensure variety)
            recent_dates = [today - timedelta(days=i) for i in range(1, 15)]
            recent_word_ids = DailyPracticeSet.objects.filter(date__in=recent_dates).values_list('words__id', flat=True)

            # 2. Get available unused words from DB
            available_words = list(Word.objects.filter(language='en').exclude(id__in=recent_word_ids))
            
            # 3. If we don't have 30 words, fetch new ones from the SEED_WORDS list!
            target_count = 30
            if len(available_words) < target_count:
                existing_texts = set(Word.objects.values_list('text', flat=True))
                new_seeds_needed = target_count - len(available_words)
                
                # Find seed words that aren't in the DB yet
                unused_seeds = [w for w in SEED_WORDS if w not in existing_texts]
                random.shuffle(unused_seeds)
                
                # Fetch them from APIs and save them
                for seed in unused_seeds[:new_seeds_needed]:
                    new_word, _ = fetch_and_store_word(seed)
                    if new_word:
                        available_words.append(new_word)

            # 4. If we STILL don't have enough (API failures, etc.), just use what we have, 
            # or recycle some old ones if it's completely empty.
            if len(available_words) < target_count:
                all_words = list(Word.objects.all())
                available_words += random.sample(all_words, min(target_count - len(available_words), len(all_words)))

            # Make sure they are unique and exactly 30
            final_words = list({w.id: w for w in available_words}.values())[:target_count]

            if not final_words:
                return Response({"error": "Database is entirely empty."}, status=status.HTTP_404_NOT_FOUND)

            with transaction.atomic():
                practice_set = DailyPracticeSet.objects.create(date=today)
                practice_set.words.set(final_words)

        serialized_data = DailyPracticeSetSerializer(practice_set).data
        response_data = dict(serialized_data)
        words_list = list(response_data.get('words', []))
        random.shuffle(words_list)
        response_data['words'] = words_list

        return Response(response_data, status=status.HTTP_200_OK)


class WordOfTheDayView(APIView):
    def get(self, request):
        today = timezone.now().date()
        wotd = WordOfTheDay.objects.filter(date=today).first()

        if not wotd:
            # Look back 30 days to avoid repeating the WOTD
            recent_dates = [today - timedelta(days=i) for i in range(1, 31)]
            used_wotd_ids = WordOfTheDay.objects.filter(date__in=recent_dates).values_list('word_id', flat=True)

            # First, try to find a sophisticated word we haven't used recently
            word = Word.objects.filter(language='en', is_sophisticated=True).exclude(id__in=used_wotd_ids).order_by('?').first()

            if not word:
                # If we run out, actively fetch a new sophisticated word from the Seed List
                existing_texts = set(Word.objects.values_list('text', flat=True))
                # Filter seed words that are long (sophisticated) and not in DB
                sophisticated_seeds = [w for w in SEED_WORDS if len(w) > 7 and w not in existing_texts]
                
                if sophisticated_seeds:
                    word, _ = fetch_and_store_word(random.choice(sophisticated_seeds))

            # Ultimate fallback: just pick any word
            if not word:
                word = Word.objects.filter(language='en').exclude(id__in=used_wotd_ids).order_by('?').first()

            if not word:
                return Response({"error": "Unable to generate word of the day."}, status=status.HTTP_404_NOT_FOUND)

            wotd = WordOfTheDay.objects.create(date=today, word=word)

        return Response(WordOfTheDaySerializer(wotd).data, status=status.HTTP_200_OK)


class TrendingWordsView(APIView):
    def get(self, request):
        words = Word.objects.filter(search_count__gt=0).order_by('-search_count')[:20]
        return Response(WordSerializer(words, many=True).data, status=status.HTTP_200_OK)