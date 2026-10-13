"""
sanskrit_engine.py
==================
Core language engine for VakSetu (वाक्सेतुः, "bridge of speech"),
a multilingual computational Sanskrit chatbot.

This module is pure Python (no Flask), so every function can be unit-tested
directly in the Jenkins "Test / Validate" stage (see tests/test_engine.py).

Features
--------
* Replies in English, Sanskrit, Hindi and Tamil (automatic script detection)
* Transliteration: Devanagari <-> IAST
* Vowel sandhi (ac-sandhi), reporting the Paninian sutra that applies
* Shabda-rupa: full declension table of a-stem masculine nouns (with natva rule)
* Sanskrit numerals and a safe arithmetic calculator
* Mini four-language dictionary and classical subhashitas
"""

import ast
import operator
import random
import re
import unicodedata

VERSION = "1.0.0"
BOT_NAME = "VakSetu"   # ASCII on purpose: shows cleanly in Jenkins console logs

SUPPORTED_LANGUAGES = {
    "auto": "Auto-detect",
    "en": "English",
    "sa": "संस्कृतम्",
    "hi": "हिन्दी",
    "ta": "தமிழ்",
}
REPLY_LANGUAGES = ("en", "sa", "hi", "ta")

# ---------------------------------------------------------------------------
# 1. Script tables (Devanagari <-> IAST)
# ---------------------------------------------------------------------------
VIRAMA = "\u094d"
NUKTA = "\u093c"

DEV_VOWELS = {
    "अ": "a", "आ": "ā", "इ": "i", "ई": "ī", "उ": "u", "ऊ": "ū",
    "ऋ": "ṛ", "ॠ": "ṝ", "ऌ": "ḷ", "ॡ": "ḹ",
    "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au",
}
DEV_MATRAS = {
    "ा": "ā", "ि": "i", "ी": "ī", "ु": "u", "ू": "ū",
    "ृ": "ṛ", "ॄ": "ṝ", "ॢ": "ḷ", "ॣ": "ḹ",
    "े": "e", "ै": "ai", "ो": "o", "ौ": "au",
}
DEV_CONSONANTS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "ṅ",
    "च": "c", "छ": "ch", "ज": "j", "झ": "jh", "ञ": "ñ",
    "ट": "ṭ", "ठ": "ṭh", "ड": "ḍ", "ढ": "ḍh", "ण": "ṇ",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "v",
    "श": "ś", "ष": "ṣ", "स": "s", "ह": "h", "ळ": "ḻ",
}
DEV_SIGNS = {
    "ं": "ṃ", "ः": "ḥ", "ँ": "m̐", "ऽ": "'", "।": "|", "॥": "||", "ॐ": "oṃ",
}
DEV_DIGITS = "०१२३४५६७८९"
TO_DEV_DIGITS = str.maketrans("0123456789", DEV_DIGITS)
TO_ASCII_DIGITS = str.maketrans(DEV_DIGITS, "0123456789")

# Reverse tables used by to_devanagari()
_IAST_TOKENS = {lat: ("C", dev) for dev, lat in DEV_CONSONANTS.items()}
_IAST_TOKENS.update({lat: ("V", lat) for lat in DEV_VOWELS.values()})
_IAST_TOKENS.update({
    # convenient ASCII shortcuts for people without an IAST keyboard
    "aa": ("V", "ā"), "ii": ("V", "ī"), "uu": ("V", "ū"), "sh": ("C", "श"),
    # signs
    "ṃ": ("S", "ं"), "ṁ": ("S", "ं"), "ḥ": ("S", "ः"), "m̐": ("S", "ँ"),
    "'": ("S", "ऽ"), "’": ("S", "ऽ"), "|": ("S", "।"), "||": ("S", "॥"),
})
_IAST_VOWEL_TO_DEV = {lat: dev for dev, lat in DEV_VOWELS.items()}
_IAST_VOWEL_TO_MATRA = {lat: matra for matra, lat in DEV_MATRAS.items()}
_MAX_TOKEN = max(len(token) for token in _IAST_TOKENS)


def has_devanagari(text):
    return bool(re.search(r"[\u0900-\u097F]", text))


def to_iast(text):
    """Transliterate Devanagari text into IAST (e.g. संस्कृतम् -> saṃskṛtam)."""
    out = []
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch in DEV_CONSONANTS:
            out.append(DEV_CONSONANTS[ch])
            i += 1
            if i < n and text[i] == NUKTA:
                i += 1
            if i < n and text[i] in DEV_MATRAS:      # consonant + vowel sign
                out.append(DEV_MATRAS[text[i]])
                i += 1
            elif i < n and text[i] == VIRAMA:        # bare consonant
                i += 1
            else:                                    # inherent 'a'
                out.append("a")
            continue
        if ch in DEV_VOWELS:
            out.append(DEV_VOWELS[ch])
        elif ch in DEV_SIGNS:
            out.append(DEV_SIGNS[ch])
        elif ch in DEV_DIGITS:
            out.append(ch.translate(TO_ASCII_DIGITS))
        elif ch != NUKTA:
            out.append(ch)
        i += 1
    return "".join(out)


def to_devanagari(text):
    """Transliterate IAST text into Devanagari (e.g. saṃskṛtam -> संस्कृतम्)."""
    text = unicodedata.normalize("NFC", text.lower())
    out = []
    pending = False          # True while the last consonant still needs a vowel
    i = 0
    while i < len(text):
        piece = None
        for size in range(_MAX_TOKEN, 0, -1):    # greedy longest match
            if text[i:i + size] in _IAST_TOKENS:
                piece = text[i:i + size]
                break
        if piece is None:                        # space, punctuation, digit ...
            if pending:
                out.append(VIRAMA)
                pending = False
            out.append(text[i].translate(TO_DEV_DIGITS))
            i += 1
            continue

        kind, value = _IAST_TOKENS[piece]
        if kind == "C":
            if pending:
                out.append(VIRAMA)               # conjunct consonant
            out.append(value)
            pending = True
        elif kind == "V":
            if pending:
                if value != "a":
                    out.append(_IAST_VOWEL_TO_MATRA[value])
                pending = False
            else:
                out.append(_IAST_VOWEL_TO_DEV[value])
        else:                                    # anusvara, visarga, danda ...
            if pending:
                out.append(VIRAMA)
                pending = False
            out.append(value)
        i += len(piece)
    if pending:
        out.append(VIRAMA)
    return "".join(out)


def detect_language(text):
    """Guess the reply language from the script used in the message."""
    if re.search(r"[\u0B80-\u0BFF]", text):
        return "ta"
    if has_devanagari(text):
        hindi_markers = ("है", "हैं", "मैं", "क्या", "आप", "नहीं", "मदद", "कैसे", "हूँ", "तुम")
        return "hi" if any(marker in text for marker in hindi_markers) else "sa"
    return "en"


# ---------------------------------------------------------------------------
# 2. Multilingual phrases
# ---------------------------------------------------------------------------
TEXT = {
    "greet": {
        "en": "Namaste! 🙏 I am VākSetu, a computational Sanskrit assistant. Type 'help' to see what I can do.",
        "sa": "नमो नमः! 🙏 अहं वाक्सेतुः, सङ्गणकीयः संस्कृतसहायकः। मम सामर्थ्यं ज्ञातुं 'help' इति लिखतु।",
        "hi": "नमस्ते! 🙏 मैं वाक्सेतु हूँ, एक कम्प्यूटेशनल संस्कृत सहायक। मेरी क्षमताएँ देखने के लिए 'help' लिखें।",
        "ta": "வணக்கம்! 🙏 நான் வாக்சேது, ஒரு கணினிசார் சமஸ்கிருத உதவியாளர். நான் செய்யக்கூடியவற்றைக் காண 'help' என்று தட்டச்சு செய்யுங்கள்.",
    },
    "intro": {
        "en": "I am VākSetu (वाक्सेतुः, 'bridge of speech'). I apply simple computational linguistics to Sanskrit: transliteration, sandhi, noun declension, numerals and more.",
        "sa": "अहं वाक्सेतुः (वाचः सेतुः)। लिप्यन्तरणं सन्धिं शब्दरूपाणि सङ्ख्याः च सङ्गणकेन साधयामि।",
        "hi": "मैं वाक्सेतु ('वाणी का सेतु') हूँ। मैं लिप्यंतरण, संधि, शब्दरूप और संख्याओं पर काम करने वाला संस्कृत चैटबॉट हूँ।",
        "ta": "நான் வாக்சேது ('பேச்சின் பாலம்'). ஒலிபெயர்ப்பு, சந்தி, சொல் வடிவங்கள், எண்கள் போன்றவற்றைக் கணினி மூலம் செய்யும் சமஸ்கிருத சாட்பாட்.",
    },
    "thanks": {
        "en": "You're welcome! शुभमस्तु (may all be well).",
        "sa": "स्वागतम्! शुभमस्तु।",
        "hi": "आपका स्वागत है! शुभमस्तु।",
        "ta": "மகிழ்ச்சி! சுபமஸ்து (எல்லாம் நலமாகட்டும்).",
    },
    "fallback": {
        "en": "Sorry, I didn't understand that. Type 'help' to see the commands I know.",
        "sa": "क्षम्यताम्, तत् मया न अवगतम्। 'help' इति लिखतु।",
        "hi": "क्षमा करें, मैं समझ नहीं पाया। आदेश देखने के लिए 'help' लिखें।",
        "ta": "மன்னிக்கவும், எனக்குப் புரியவில்லை. கட்டளைகளைக் காண 'help' என்று தட்டச்சு செய்யுங்கள்.",
    },
    "help_header": {
        "en": "Here is what I can do:",
        "sa": "अहम् एतानि कार्याणि कर्तुं शक्नोमि:",
        "hi": "मैं ये काम कर सकता हूँ:",
        "ta": "நான் செய்யக்கூடியவை:",
    },
    "result": {"en": "Result", "sa": "परिणामः", "hi": "परिणाम", "ta": "விடை"},
    "invalid_expr": {
        "en": "That is not a valid arithmetic expression.",
        "sa": "इयं गणना अशुद्धा।",
        "hi": "यह मान्य गणना नहीं है।",
        "ta": "இது சரியான கணக்கீடு அல்ல.",
    },
    "number": {"en": "Number", "sa": "सङ्ख्या", "hi": "संख्या", "ta": "எண்"},
    "translit": {"en": "Transliteration", "sa": "लिप्यन्तरणम्", "hi": "लिप्यंतरण", "ta": "ஒலிபெயர்ப்பு"},
    "sandhi": {"en": "Sandhi", "sa": "सन्धिः", "hi": "संधि", "ta": "சந்தி"},
    "rule": {"en": "Rule", "sa": "सूत्रम्", "hi": "नियम", "ta": "விதி"},
    "declension": {"en": "Declension of", "sa": "शब्दरूपाणि:", "hi": "शब्दरूप:", "ta": "சொல் வடிவங்கள்:"},
    "unsupported_noun": {
        "en": "Sorry, I can only decline a-ending masculine nouns such as राम, देव or बालक.",
        "sa": "क्षम्यताम्, सम्प्रति अकारान्त-पुंलिङ्ग-शब्दानाम् (राम, देव, बालक) एव रूपाणि ददामि।",
        "hi": "क्षमा करें, अभी केवल अकारांत पुल्लिंग शब्द (राम, देव, बालक) समर्थित हैं।",
        "ta": "மன்னிக்கவும், தற்போது அகர ஈற்று ஆண்பால் பெயர்ச்சொற்கள் (राम, देव, बालक) மட்டுமே ஆதரிக்கப்படுகின்றன.",
    },
    "meaning": {"en": "Meaning", "sa": "अर्थः", "hi": "अर्थ", "ta": "பொருள்"},
    "not_found": {
        "en": "I don't know that word yet. Words I know:",
        "sa": "एषः शब्दः मम कोशे नास्ति। मम कोशे एते शब्दाः सन्ति:",
        "hi": "यह शब्द अभी मेरे शब्दकोश में नहीं है। मुझे ये शब्द आते हैं:",
        "ta": "இந்தச் சொல் இன்னும் என் அகராதியில் இல்லை. எனக்குத் தெரிந்த சொற்கள்:",
    },
    "subhashita": {"en": "Subhāṣita", "sa": "सुभाषितम्", "hi": "सुभाषित", "ta": "சுபாஷிதம்"},
    "usage": {"en": "Usage", "sa": "प्रयोगः", "hi": "उपयोग", "ta": "பயன்பாடு"},
}

HELP_COMMANDS = [
    "• translit <text>: Devanagari ⇄ IAST  (translit संस्कृतम्)",
    "• sandhi <word> + <word>: vowel sandhi  (sandhi deva + ālaya)",
    "• decline <noun>: śabda-rūpa table  (decline rāma)",
    "• number <n>: Sanskrit numeral  (number 18)",
    "• calc <expression>: arithmetic  (calc 12 * (3 + 4))",
    "• meaning <word>: 4-language dictionary  (meaning water)",
    "• subhashita: a classical Sanskrit saying",
]


def _t(key, lang):
    return TEXT[key].get(lang, TEXT[key]["en"])


def _reply(text, lang, intent, table=None):
    response = {"reply": text, "language": lang, "intent": intent}
    if table:
        response["table"] = table
    return response


def _usage(example, lang, intent):
    return _reply(f"{_t('usage', lang)}: {example}", lang, intent)


# ---------------------------------------------------------------------------
# 3. Vowel sandhi (works on IAST strings)
# ---------------------------------------------------------------------------
_IAST_VOWELS = ("ai", "au", "a", "ā", "i", "ī", "u", "ū", "ṛ", "ṝ", "ḷ", "e", "o")
_SAVARNA_GROUPS = ({"a", "ā"}, {"i", "ī"}, {"u", "ū"}, {"ṛ", "ṝ"})
_LONG = {"a": "ā", "ā": "ā", "i": "ī", "ī": "ī", "u": "ū", "ū": "ū", "ṛ": "ṝ", "ṝ": "ṝ"}
_YAN = {"i": "y", "ī": "y", "u": "v", "ū": "v", "ṛ": "r", "ṝ": "r", "ḷ": "l"}
_AYADI = {"e": "ay", "ai": "āy", "o": "av", "au": "āv"}

RULE_DIRGHA = "Savarṇa-dīrgha: akaḥ savarṇe dīrghaḥ (6.1.101)"
RULE_GUNA = "Guṇa: ād guṇaḥ (6.1.87)"
RULE_VRDDHI = "Vṛddhi: vṛddhir eci (6.1.88)"
RULE_YAN = "Yaṇ: iko yaṇ aci (6.1.77)"
RULE_PURVARUPA = "Pūrvarūpa: eṅaḥ padāntād ati (6.1.109)"
RULE_AYADI = "Ayādi: eco'yavāyāvaḥ (6.1.78)"
RULE_NONE = "No vowel meets a vowel here, so the words are simply joined."


def _final_vowel(word):
    return next((v for v in _IAST_VOWELS if word.endswith(v)), "")


def _initial_vowel(word):
    return next((v for v in _IAST_VOWELS if word.startswith(v)), "")


def apply_sandhi(first, second):
    """Join two IAST words with vowel sandhi. Returns (joined_word, rule)."""
    first, second = first.strip(), second.strip()
    v1, v2 = _final_vowel(first), _initial_vowel(second)
    if not v1 or not v2:
        return first + second, RULE_NONE

    head, tail = first[:-len(v1)], second[len(v2):]

    for group in _SAVARNA_GROUPS:
        if v1 in group and v2 in group:
            return head + _LONG[v1] + tail, RULE_DIRGHA

    if v1 in ("a", "ā"):
        if v2 in ("i", "ī"):
            return head + "e" + tail, RULE_GUNA
        if v2 in ("u", "ū"):
            return head + "o" + tail, RULE_GUNA
        if v2 in ("ṛ", "ṝ"):
            return head + "ar" + tail, RULE_GUNA
        if v2 == "ḷ":
            return head + "al" + tail, RULE_GUNA
        if v2 in ("e", "ai"):
            return head + "ai" + tail, RULE_VRDDHI
        return head + "au" + tail, RULE_VRDDHI          # o / au

    if v1 in _YAN:
        return head + _YAN[v1] + v2 + tail, RULE_YAN

    if v1 in ("e", "o") and v2 == "a":
        return first + "'" + tail, RULE_PURVARUPA

    return head + _AYADI[v1] + v2 + tail, RULE_AYADI


# ---------------------------------------------------------------------------
# 4. Noun declension (śabda-rūpa) for a-stem masculine nouns
# ---------------------------------------------------------------------------
CASES = [
    ("nom", "प्रथमा", "Nominative"),
    ("acc", "द्वितीया", "Accusative"),
    ("ins", "तृतीया", "Instrumental"),
    ("dat", "चतुर्थी", "Dative"),
    ("abl", "पञ्चमी", "Ablative"),
    ("gen", "षष्ठी", "Genitive"),
    ("loc", "सप्तमी", "Locative"),
    ("voc", "सम्बोधनम्", "Vocative"),
]
_NATVA_TRIGGERS = set("रषऋॠृॄ")
# letters that do not block natva: vowels/h/y/v/r (aṭ), gutturals (ku), labials (pu), anusvara
_NATVA_TRANSPARENT = set("अआइईउऊऋॠएऐओऔािीुूृॄेैोौं" + VIRAMA + "कखगघङपफबभमयवरह")


def _natva_n(stem):
    """Return 'ण' when raṣābhyāṃ no ṇaḥ samānapade (8.4.1-2) applies, otherwise 'न'."""
    last = max((i for i, ch in enumerate(stem) if ch in _NATVA_TRIGGERS), default=-1)
    if last == -1:
        return "न"
    return "ण" if all(ch in _NATVA_TRANSPARENT for ch in stem[last + 1:]) else "न"


def decline_a_stem(stem):
    """Return all 24 forms of an a-stem masculine noun such as राम or देव."""
    stem = stem.strip()
    if stem.endswith("ः"):
        stem = stem[:-1]
    is_devanagari = stem and all("\u0900" <= ch <= "\u097F" for ch in stem)
    if not is_devanagari or stem[-1] not in DEV_CONSONANTS:
        raise ValueError("Only a-stem (अकारान्त) masculine nouns are supported")

    s, n = stem, _natva_n(stem)
    return {
        "nom": [s + "ः", s + "ौ", s + "ाः"],
        "acc": [s + "म्", s + "ौ", s + "ान्"],
        "ins": [s + "े" + n, s + "ाभ्याम्", s + "ैः"],
        "dat": [s + "ाय", s + "ाभ्याम्", s + "ेभ्यः"],
        "abl": [s + "ात्", s + "ाभ्याम्", s + "ेभ्यः"],
        "gen": [s + "स्य", s + "योः", s + "ा" + n + "ाम्"],
        "loc": [s + "े", s + "योः", s + "ेषु"],
        "voc": ["हे " + s, "हे " + s + "ौ", "हे " + s + "ाः"],
    }


# ---------------------------------------------------------------------------
# 5. Numerals and safe arithmetic
# ---------------------------------------------------------------------------
NUMBER_WORDS = {
    0: "शून्यम्", 1: "एकम्", 2: "द्वे", 3: "त्रीणि", 4: "चत्वारि", 5: "पञ्च",
    6: "षट्", 7: "सप्त", 8: "अष्ट", 9: "नव", 10: "दश",
    11: "एकादश", 12: "द्वादश", 13: "त्रयोदश", 14: "चतुर्दश", 15: "पञ्चदश",
    16: "षोडश", 17: "सप्तदश", 18: "अष्टादश", 19: "नवदश", 20: "विंशतिः",
    30: "त्रिंशत्", 40: "चत्वारिंशत्", 50: "पञ्चाशत्", 60: "षष्टिः",
    70: "सप्ततिः", 80: "अशीतिः", 90: "नवतिः", 100: "शतम्", 1000: "सहस्रम्",
}


def sanskrit_number(n):
    """Return (Devanagari numeral, Sanskrit words) for an integer."""
    numeral = str(n).translate(TO_DEV_DIGITS)
    if n in NUMBER_WORDS:
        return numeral, NUMBER_WORDS[n]
    if 20 < n < 100:
        tens, units = divmod(n, 10)
        return numeral, f"{NUMBER_WORDS[tens * 10]} + {NUMBER_WORDS[units]}"
    return numeral, ""


_BIN_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_MAX_VALUE = 10 ** 18


def safe_calculate(expression):
    """Evaluate + - * / // % ** on numbers only (no eval, no names, no calls)."""
    expr = (expression.translate(TO_ASCII_DIGITS)
            .replace("×", "*").replace("÷", "/").replace("^", "**"))
    if len(expr) > 80:
        raise ValueError("expression too long")

    def evaluate(node):
        if isinstance(node, ast.Expression):
            return evaluate(node.body)
        if (isinstance(node, ast.Constant) and isinstance(node.value, (int, float))
                and not isinstance(node.value, bool)):
            return node.value
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            return _UNARY_OPS[type(node.op)](evaluate(node.operand))
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            left, right = evaluate(node.left), evaluate(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 50:
                raise ValueError("exponent too large")
            value = _BIN_OPS[type(node.op)](left, right)
            if abs(value) > _MAX_VALUE:
                raise ValueError("result too large")
            return value
        raise ValueError("unsupported expression")

    result = evaluate(ast.parse(expr, mode="eval"))
    if isinstance(result, float):
        result = int(result) if result.is_integer() else round(result, 6)
    return result


# ---------------------------------------------------------------------------
# 6. Dictionary and subhāṣitas
# ---------------------------------------------------------------------------
DICTIONARY = {
    "water": {"sa": "जलम्", "hi": "पानी", "ta": "தண்ணீர்"},
    "fire": {"sa": "अग्निः", "hi": "आग", "ta": "நெருப்பு"},
    "sun": {"sa": "सूर्यः", "hi": "सूरज", "ta": "சூரியன்"},
    "moon": {"sa": "चन्द्रः", "hi": "चाँद", "ta": "நிலா"},
    "earth": {"sa": "पृथिवी", "hi": "धरती", "ta": "பூமி"},
    "book": {"sa": "पुस्तकम्", "hi": "किताब", "ta": "புத்தகம்"},
    "teacher": {"sa": "गुरुः", "hi": "शिक्षक", "ta": "ஆசிரியர்"},
    "student": {"sa": "छात्रः", "hi": "छात्र", "ta": "மாணவர்"},
    "friend": {"sa": "मित्रम्", "hi": "दोस्त", "ta": "நண்பன்"},
    "house": {"sa": "गृहम्", "hi": "घर", "ta": "வீடு"},
    "tree": {"sa": "वृक्षः", "hi": "पेड़", "ta": "மரம்"},
    "knowledge": {"sa": "विद्या", "hi": "ज्ञान", "ta": "அறிவு"},
    "truth": {"sa": "सत्यम्", "hi": "सच", "ta": "உண்மை"},
    "mother": {"sa": "माता", "hi": "माँ", "ta": "அம்மா"},
    "father": {"sa": "पिता", "hi": "पिता", "ta": "அப்பா"},
    "food": {"sa": "अन्नम्", "hi": "खाना", "ta": "உணவு"},
    "computer": {"sa": "सङ्गणकम्", "hi": "कंप्यूटर", "ta": "கணினி"},
}

SUBHASHITAS = [
    ("सत्यमेव जयते", "Truth alone triumphs.", "Muṇḍaka Upaniṣad 3.1.6"),
    ("वसुधैव कुटुम्बकम्", "The whole world is one family.", "Mahā Upaniṣad 6.71"),
    ("विद्या ददाति विनयम्", "Knowledge gives humility.", "Hitopadeśa"),
    ("उद्यमेन हि सिध्यन्ति कार्याणि न मनोरथैः", "Work succeeds through effort, not mere wishes.", "Hitopadeśa"),
    ("योगः कर्मसु कौशलम्", "Yoga is skill in action.", "Bhagavad Gītā 2.50"),
    ("अहिंसा परमो धर्मः", "Non-violence is the highest duty.", "Mahābhārata"),
]


def _plain(text):
    """Remove diacritics: sūryaḥ -> suryah."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def _build_dictionary_index():
    index = {}
    for english, entry in DICTIONARY.items():
        sa = entry["sa"]
        stems = {sa, sa[:-1] if sa.endswith("ः") else sa, sa[:-2] if sa.endswith("म्") else sa}
        keys = {english, entry["hi"], entry["ta"]}
        for form in stems:
            keys.update({form, to_iast(form), _plain(to_iast(form))})
        for key in keys:
            index[key.lower()] = english
    return index


_DICT_INDEX = _build_dictionary_index()


def lookup_word(word):
    key = unicodedata.normalize("NFC", word.strip().lower().strip("?.!।"))
    return _DICT_INDEX.get(key) or _DICT_INDEX.get(_plain(key))


# ---------------------------------------------------------------------------
# 7. Command handlers
# ---------------------------------------------------------------------------
def _cmd_help(arg, lang):
    return _reply(_t("help_header", lang) + "\n" + "\n".join(HELP_COMMANDS), lang, "help")


def _cmd_translit(arg, lang):
    if not arg:
        return _usage("translit संस्कृतम्  /  translit saṃskṛtam", lang, "translit")
    if has_devanagari(arg):
        result, direction = to_iast(arg), "Devanagari → IAST"
    else:
        result, direction = to_devanagari(arg), "IAST → Devanagari"
    return _reply(f"{_t('translit', lang)} ({direction}):\n{arg}  →  {result}", lang, "translit")


def _cmd_sandhi(arg, lang):
    parts = [p for p in re.split(r"\s*\+\s*|\s+", arg.strip()) if p]
    if len(parts) != 2:
        return _usage("sandhi deva + ālaya  /  sandhi देव + आलय", lang, "sandhi")
    # Normalise both words to IAST (Latin input passes through Devanagari to expand aa/ii/uu/sh)
    w1, w2 = (to_iast(p if has_devanagari(p) else to_devanagari(p)) for p in parts)
    joined, rule = apply_sandhi(w1, w2)
    text = (f"{_t('sandhi', lang)}:\n"
            f"{w1} + {w2}  →  {joined}\n"
            f"{to_devanagari(w1)} + {to_devanagari(w2)}  →  {to_devanagari(joined)}\n"
            f"{_t('rule', lang)}: {rule}")
    return _reply(text, lang, "sandhi")


def _cmd_decline(arg, lang):
    if not arg:
        return _usage("decline rāma  /  decline देव", lang, "decline")
    word = arg.split()[0]
    stem = word if has_devanagari(word) else to_devanagari(word)
    try:
        forms = decline_a_stem(stem)
    except ValueError:
        return _reply(_t("unsupported_noun", lang), lang, "decline")
    stem = stem.rstrip("ः")
    rows = [[f"{dev}\n{eng}"] + [f"{form}\n{to_iast(form)}" for form in forms[key]]
            for key, dev, eng in CASES]
    table = {
        "headers": ["विभक्तिः / Case", "एकवचनम् / Sg.", "द्विवचनम् / Du.", "बहुवचनम् / Pl."],
        "rows": rows,
    }
    title = f"{_t('declension', lang)} {stem} ({to_iast(stem)}), अकारान्तः पुंलिङ्गः"
    return _reply(title, lang, "decline", table)


def _cmd_number(arg, lang):
    digits = arg.strip().translate(TO_ASCII_DIGITS)
    if not re.fullmatch(r"-?\d{1,15}", digits):
        return _usage("number 18", lang, "number")
    n = int(digits)
    numeral, words = sanskrit_number(n)
    lines = [f"{_t('number', lang)}: {n}  →  {numeral}"]
    if words:
        lines.append(f"{words}  ({to_iast(words)})")
    return _reply("\n".join(lines), lang, "number")


def _cmd_calc(arg, lang):
    if not arg:
        return _usage("calc 12 * (3 + 4)", lang, "calc")
    try:
        result = safe_calculate(arg)
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError, TypeError):
        return _reply(_t("invalid_expr", lang), lang, "calc")
    expr = arg.strip().translate(TO_ASCII_DIGITS)
    text = (f"{_t('result', lang)}: {expr} = {result}\n"
            f"{expr.translate(TO_DEV_DIGITS)} = {str(result).translate(TO_DEV_DIGITS)}")
    if isinstance(result, int) and result in NUMBER_WORDS:
        text += f"\n({NUMBER_WORDS[result]})"
    return _reply(text, lang, "calc")


def _cmd_meaning(arg, lang):
    if not arg.strip():
        return _usage("meaning water  /  meaning जलम्", lang, "meaning")
    english = lookup_word(arg)
    if not english:
        return _reply(_t("not_found", lang) + "\n" + ", ".join(DICTIONARY), lang, "meaning")
    entry = DICTIONARY[english]
    text = (f"{_t('meaning', lang)}: {english}\n"
            f"संस्कृतम्: {entry['sa']} ({to_iast(entry['sa'])})\n"
            f"हिन्दी: {entry['hi']}\n"
            f"தமிழ்: {entry['ta']}\n"
            f"English: {english}")
    return _reply(text, lang, "meaning")


def _cmd_subhashita(arg, lang):
    verse, meaning, source = random.choice(SUBHASHITAS)
    text = f"{_t('subhashita', lang)}:\n{verse}\n{to_iast(verse)}\n\"{meaning}\" ({source})"
    return _reply(text, lang, "subhashita")


# Command word (and its aliases in several languages) -> handler
COMMANDS = [
    (("help", "सहायता", "मदद", "உதவி"), _cmd_help),
    (("translit", "transliterate", "लिप्यन्तरणम्", "लिप्यंतरण"), _cmd_translit),
    (("sandhi", "सन्धिः", "सन्धि", "संधि"), _cmd_sandhi),
    (("decline", "shabda", "śabda", "शब्दरूपम्", "शब्दरूप"), _cmd_decline),
    (("number", "sankhya", "saṅkhyā", "सङ्ख्या", "संख्या"), _cmd_number),
    (("calc", "calculate", "ganaya", "गणय", "गणना"), _cmd_calc),
    (("meaning", "word", "अर्थः", "अर्थ", "பொருள்"), _cmd_meaning),
    (("subhashita", "quote", "सुभाषितम्", "सुभाषित"), _cmd_subhashita),
]

_GREET_RE = re.compile(r"\b(hi|hello|hey|namaste|namaskar|namaskaram|pranam|vanakkam)\b")
_GREET_WORDS = ("नमस्ते", "नमस्कार", "नमो नमः", "प्रणाम", "வணக்கம்")
_WHO_WORDS = ("who are you", "your name", "what are you", "कः त्वम्", "कः भवान्",
              "किं तव नाम", "आप कौन", "तुम कौन", "நீ யார்", "நீங்கள் யார்")
_THANKS_WORDS = ("thank", "dhanyavad", "धन्यवाद", "शुक्रिया", "நன்றி")
_ARITHMETIC_RE = re.compile(r"^[\d०-९\s+\-*/().×÷^%]+$")


def _find_command(word):
    for aliases, handler in COMMANDS:
        if word in aliases:
            return handler
    return None


# ---------------------------------------------------------------------------
# 8. Public entry point used by the Flask app
# ---------------------------------------------------------------------------
def get_reply(message, language="auto"):
    """Return a reply dict: {"reply", "language", "intent", optional "table"}."""
    message = (message or "").strip()[:500]
    lang = language if language in REPLY_LANGUAGES else detect_language(message)
    if not message:
        return _reply(_t("fallback", lang), lang, "fallback")

    parts = message.split(maxsplit=1)
    command = parts[0].lower().strip("?!.,:;।")
    argument = parts[1] if len(parts) > 1 else ""

    handler = _find_command(command)
    if handler:
        return handler(argument.strip(), lang)

    lowered = message.lower()
    if any(word in lowered for word in _WHO_WORDS):
        return _reply(_t("intro", lang), lang, "intro")
    if _GREET_RE.search(lowered) or any(word in message for word in _GREET_WORDS):
        return _reply(_t("greet", lang), lang, "greet")
    if any(word in lowered for word in _THANKS_WORDS):
        return _reply(_t("thanks", lang), lang, "thanks")
    if (_ARITHMETIC_RE.match(message) and re.search(r"[\d०-९]", message)
            and re.search(r"[+\-*/×÷^%]", message)):
        return _cmd_calc(message, lang)

    return _reply(_t("fallback", lang), lang, "fallback")
