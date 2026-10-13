"""Unit tests for sanskrit_engine.py (run by the Jenkins 'Test / Validate' stage)."""

import pytest

from sanskrit_engine import (
    SUBHASHITAS,
    apply_sandhi,
    decline_a_stem,
    detect_language,
    get_reply,
    lookup_word,
    safe_calculate,
    sanskrit_number,
    to_devanagari,
    to_iast,
)


# ---------- transliteration ----------
def test_devanagari_to_iast():
    assert to_iast("संस्कृतम्") == "saṃskṛtam"
    assert to_iast("धर्मक्षेत्रे") == "dharmakṣetre"


def test_iast_to_devanagari():
    assert to_devanagari("saṃskṛtam") == "संस्कृतम्"
    assert to_devanagari("jñānam") == "ज्ञानम्"


def test_ascii_shortcuts():
    assert to_devanagari("raamaayana") == "रामायन"
    assert to_devanagari("shiva") == "शिव"


@pytest.mark.parametrize("word", ["रामः", "विद्या", "सूर्योदयः", "वनेऽस्मिन्", "कृष्णः"])
def test_round_trip(word):
    assert to_devanagari(to_iast(word)) == word


# ---------- sandhi ----------
@pytest.mark.parametrize("first, second, expected", [
    ("deva", "ālaya", "devālaya"),      # savarna-dirgha
    ("sūrya", "udaya", "sūryodaya"),    # guna
    ("mahā", "indra", "mahendra"),      # guna
    ("sadā", "eva", "sadaiva"),         # vrddhi
    ("iti", "ādi", "ityādi"),           # yan
    ("su", "āgatam", "svāgatam"),       # yan
    ("vane", "asmin", "vane'smin"),     # purvarupa
])
def test_vowel_sandhi(first, second, expected):
    joined, rule = apply_sandhi(first, second)
    assert joined == expected
    assert rule


def test_consonant_junction_is_plain_join():
    assert apply_sandhi("vāk", "devī")[0] == "vākdevī"


# ---------- declension ----------
def test_rama_declension_with_natva():
    forms = decline_a_stem("राम")
    assert forms["nom"] == ["रामः", "रामौ", "रामाः"]
    assert forms["ins"][0] == "रामेण"          # n -> n (retroflex) after r
    assert forms["gen"][2] == "रामाणाम्"
    assert forms["loc"][2] == "रामेषु"


def test_deva_declension_without_natva():
    forms = decline_a_stem("देव")
    assert forms["ins"][0] == "देवेन"
    assert forms["gen"][2] == "देवानाम्"


def test_natva_blocked_by_retroflex_consonant():
    assert decline_a_stem("कृष्ण")["ins"][0] == "कृष्णेन"


def test_unsupported_stem_raises():
    with pytest.raises(ValueError):
        decline_a_stem("माला")


# ---------- numbers and calculator ----------
def test_sanskrit_numbers():
    assert sanskrit_number(18) == ("१८", "अष्टादश")
    assert sanskrit_number(47) == ("४७", "चत्वारिंशत् + सप्त")


@pytest.mark.parametrize("expression, expected", [
    ("12 * (3 + 4)", 84),
    ("१० + ५", 15),
    ("7 / 2", 3.5),
    ("2 ^ 10", 1024),
])
def test_safe_calculate(expression, expected):
    assert safe_calculate(expression) == expected


@pytest.mark.parametrize("expression", ["__import__('os')", "1/0", "9 ** 999", "abc"])
def test_calculator_rejects_bad_input(expression):
    with pytest.raises((ValueError, SyntaxError, ZeroDivisionError)):
        safe_calculate(expression)


# ---------- dictionary ----------
def test_dictionary_lookup_in_four_languages():
    assert lookup_word("water") == "water"
    assert lookup_word("जलम्") == "water"
    assert lookup_word("suryah") == "sun"
    assert lookup_word("மரம்") == "tree"


# ---------- language detection and replies ----------
@pytest.mark.parametrize("text, lang", [
    ("hello there", "en"),
    ("रामः वनं गच्छति", "sa"),
    ("आप कैसे हैं", "hi"),
    ("வணக்கம்", "ta"),
])
def test_detect_language(text, lang):
    assert detect_language(text) == lang


def test_greeting_in_tamil():
    reply = get_reply("vanakkam", "ta")
    assert reply["intent"] == "greet"
    assert "வணக்கம்" in reply["reply"]


def test_decline_command_returns_table():
    reply = get_reply("decline rāma", "en")
    assert reply["intent"] == "decline"
    assert len(reply["table"]["rows"]) == 8


def test_plain_arithmetic_is_detected():
    assert get_reply("6 * 7")["intent"] == "calc"


def test_subhashita_comes_from_list():
    reply = get_reply("subhashita", "en")
    assert any(verse in reply["reply"] for verse, _, _ in SUBHASHITAS)


def test_unknown_message_falls_back():
    assert get_reply("qwerty zxcv", "en")["intent"] == "fallback"
