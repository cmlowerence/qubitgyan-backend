# qubitgyan-backend/library/api/v2/lexicon/application/constants.py

DEFAULT_PRACTICE_COUNT = 18
MIN_PRACTICE_COUNT = 15
MAX_PRACTICE_COUNT = 20

# Keep daily sets useful and avoid obvious repeats.
PRACTICE_BLACKLIST_DAYS = 7
WOTD_BLACKLIST_DAYS = 30

PRACTICE_IMPORTANCE_THRESHOLD = 0.45
WOTD_IMPORTANCE_THRESHOLD = 0.55

TRENDING_CACHE_SECONDS = 900
WORD_CACHE_SECONDS = 86400

SEED_WORDS = [
    "aberration", "benevolent", "capricious", "dichotomy", "ephemeral",
    "fastidious", "garrulous", "harangue", "iconoclast", "juxtapose",
    "laconic", "maverick", "nebulous", "obfuscate", "paradigm",
    "quixotic", "resilient", "sycophant", "trepidation", "ubiquitous",
    "vacillate", "xenophobia", "zealous", "alacrity", "bellicose",
    "conundrum", "deleterious", "enervate", "fortuitous", "gratuitous",
    "hegemony", "impetuous", "judicious", "kaleidoscope", "loquacious",
    "meticulous", "nonchalant", "obstinate", "perfunctory", "reticent",
    "scrupulous", "tangible", "unfettered", "vindicate", "winsome",
    "yearning", "zephyr", "ascetic", "catharsis", "deference",
    "equanimity", "fervent", "gregarious", "halcyon", "inscrutable",
    "juxtaposition", "knavish", "legitimate", "melancholy", "nostalgic",
]
