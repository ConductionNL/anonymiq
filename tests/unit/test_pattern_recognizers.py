"""The configuration of every pattern recognizer is pinned.

Entity, language, context and the (name, regex, score) of each pattern decide
what gets redacted, so a refactor of the recognizers must leave them unchanged.
"""

import pytest
from presidio_analyzer import PatternRecognizer

from src.api.analysis import patterns as p

# (recognizer class, entity, default language, [(pattern name, score)])
EXPECTED = [
    (p.DutchPhoneNumberRecognizer, "PHONE_NUMBER", "nl", [("DUTCH_PHONE", 0.6)]),
    (
        p.DutchIBANRecognizer,
        "IBAN",
        "nl",
        [("DUTCH_IBAN", 0.6), ("INTL_IBAN", 0.55)],
    ),
    (p.EmailRecognizer, "EMAIL", "nl", [("EMAIL_ADDRESS", 0.6)]),
    (p.DutchBSNRecognizer, "BSN", "nl", [("NL_BSN", 0.6)]),
    (p.DutchPostcodeRecognizer, "POSTCODE", "nl", [("NL_POSTCODE", 0.55)]),
    (p.DutchVATRecognizer, "VAT_NUMBER", "nl", [("NL_VAT", 0.6)]),
    (p.DutchKvKRecognizer, "KVK_NUMBER", "nl", [("KVK_8_DIGIT", 0.45)]),
    (p.DutchLicensePlateRecognizer, "LICENSE_PLATE", "nl", [("NL_PLATE", 0.5)]),
    (p.IPv4Recognizer, "IP_ADDRESS", "any", [("IPV4", 0.5)]),
    (
        p.DutchDateRecognizer,
        "DATE_TIME",
        "nl",
        [
            ("DATE_DD_MM_YYYY", 0.5),
            ("DATE_MM_DD_YYYY", 0.5),
            ("DATE_YYYY_MM_DD", 0.5),
            ("DATE_DD_MM_YY", 0.45),
            ("DATE_DD_MONTH_YYYY", 0.5),
        ],
    ),
    (
        p.DutchPassportIdRecognizer,
        "ID_NO",
        "nl",
        [("NL_DOC_OLD", 0.55), ("NL_DOC_NEW", 0.6)],
    ),
    (
        p.CaseNumberRecognizer,
        "CASE_NO",
        "nl",
        [
            ("CASE_Z", 0.55),
            ("CASE_PREFIXED", 0.6),
            ("CASE_YEAR_NUMBER", 0.45),
            ("CASE_BAG_ID", 0.4),
            ("CASE_UUID", 0.6),
            ("CASE_C_CIVIL", 0.55),
            ("CASE_AWB", 0.6),
            ("CASE_HR", 0.6),
            ("CASE_GERECHTSHOF", 0.55),
            ("CASE_OM", 0.6),
            ("CASE_COURT_GENERIC", 0.55),
        ],
    ),
    (
        p.DutchDriversLicenseRecognizer,
        "DRIVERS_LICENSE",
        "nl",
        [("NL_DRIVERS_LICENSE", 0.45)],
    ),
]

# (recognizer class, text, matched substring): one match per pattern family.
MATCHES = [
    # The phone pattern ends in an optional separator, so the match keeps it.
    (p.DutchPhoneNumberRecognizer, "bel 06-12345678 nu", "06-12345678 "),
    (
        p.DutchIBANRecognizer,
        "rekening NL91 ABNA 0417 1643 00.",
        "NL91 ABNA 0417 1643 00",
    ),
    (p.EmailRecognizer, "mail jan@example.nl graag", "jan@example.nl"),
    (p.DutchBSNRecognizer, "bsn 123-456-782 hier", "123-456-782"),
    (p.DutchPostcodeRecognizer, "te 1234 AB Utrecht", "1234 AB"),
    (p.DutchVATRecognizer, "btw NL123456789B01 x", "NL123456789B01"),
    (p.DutchKvKRecognizer, "kvk 12345678 x", "12345678"),
    (p.DutchLicensePlateRecognizer, "auto 12-AB-34 rood", "12-AB-34"),
    (p.IPv4Recognizer, "host 192.168.1.10 up", "192.168.1.10"),
    (p.DutchDateRecognizer, "op 1 september 2020 x", "1 september 2020"),
    (p.DutchPassportIdRecognizer, "nr XR1B23C45 x", "XR1B23C45"),
    (p.CaseNumberRecognizer, "zaak Z-2024-123456 x", "Z-2024-123456"),
    (p.DutchDriversLicenseRecognizer, "rb 1234567890 x", "1234567890"),
]


@pytest.mark.parametrize(
    ("cls", "entity", "language", "expected"),
    EXPECTED,
    ids=[row[0].__name__ for row in EXPECTED],
)
def test_recognizer_configuration(
    cls: type[PatternRecognizer], entity: str, language: str, expected: list
) -> None:
    """Entity, default language and pattern names and scores stay the same."""
    recognizer = cls()
    assert recognizer.supported_entities == [entity]
    assert recognizer.supported_language == language
    assert [(pat.name, pat.score) for pat in recognizer.patterns] == expected


@pytest.mark.parametrize("cls", [row[0] for row in EXPECTED], ids=lambda c: c.__name__)
def test_recognizer_passes_context_through(cls: type[PatternRecognizer]) -> None:
    """A context list given to the constructor reaches the recognizer."""
    assert cls(context=["woord"]).context == ["woord"]


@pytest.mark.parametrize(
    "cls",
    [row[0] for row in EXPECTED if row[0] is not p.DutchBSNRecognizer],
    ids=lambda c: c.__name__,
)
def test_recognizer_accepts_a_language(cls: type[PatternRecognizer]) -> None:
    """The language can be set, except on the BSN recognizer."""
    assert cls(supported_language="en").supported_language == "en"


def test_regex_of_every_pattern_is_pinned() -> None:
    """The regex of every pattern stays the same."""
    listing = [
        (cls.__name__, pat.name, pat.regex)
        for cls, *_ in EXPECTED
        for pat in cls().patterns
    ]
    assert listing == PINNED_REGEXES


@pytest.mark.parametrize(
    ("cls", "text", "found"), MATCHES, ids=[row[0].__name__ for row in MATCHES]
)
def test_recognizer_finds_its_entity(
    cls: type[PatternRecognizer], text: str, found: str
) -> None:
    """Each recognizer finds a typical value in running text."""
    recognizer = cls()
    results = recognizer.analyze(text, recognizer.supported_entities)
    assert found in {text[r.start : r.end] for r in results}


def test_bsn_eleven_test() -> None:
    """The BSN check digit helper applies the eleven test."""
    recognizer = p.DutchBSNRecognizer()
    assert recognizer._is_valid_bsn("100000002")
    assert not recognizer._is_valid_bsn("100000003")


PINNED_REGEXES = [
    (
        "DutchPhoneNumberRecognizer",
        "DUTCH_PHONE",
        "\\b(?:0|(?:\\+|00)31)[- ]?(?:\\d[- ]?){9}\\b",
    ),
    (
        "DutchIBANRecognizer",
        "DUTCH_IBAN",
        "\\bNL\\d{2}\\s?[A-Z]{4}(?:\\s?\\d{10}|\\s?\\d{4}\\s?\\d{4}\\s?\\d{2})\\b",
    ),
    (
        "DutchIBANRecognizer",
        "INTL_IBAN",
        "\\b[A-Z]{2}\\d{2}(?:\\s?[A-Z0-9]{4}){2,7}(?:\\s?[A-Z0-9]{1,4})?\\b",
    ),
    (
        "EmailRecognizer",
        "EMAIL_ADDRESS",
        "\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b",
    ),
    ("DutchBSNRecognizer", "NL_BSN", "\\b(?:\\d{9}|\\d{3}[- ]?\\d{3}[- ]?\\d{3})\\b"),
    ("DutchPostcodeRecognizer", "NL_POSTCODE", "\\b\\d{4}\\s?[A-Z]{2}\\b"),
    ("DutchVATRecognizer", "NL_VAT", "\\bNL\\d{9}B\\d{2}\\b"),
    ("DutchKvKRecognizer", "KVK_8_DIGIT", "\\b\\d{8}\\b"),
    (
        "DutchLicensePlateRecognizer",
        "NL_PLATE",
        "\\b(?:[A-Z]{2}-\\d{2}-\\d{2}|\\d{2}-\\d{2}-[A-Z]{2}|\\d{2}-[A-Z]{2}-\\d{2}|[A-Z]{2}-\\d{2}-[A-Z]{2}|[A-Z]{2}-[A-Z]{2}-\\d{2}|\\d{2}-[A-Z]{2}-[A-Z]{2})\\b",
    ),
    (
        "IPv4Recognizer",
        "IPV4",
        "\\b(?:25[0-5]|2[0-4]\\d|1\\d{2}|[1-9]?\\d)(?:\\.(?:25[0-5]|2[0-4]\\d|1\\d{2}|[1-9]?\\d)){3}\\b",
    ),
    (
        "DutchDateRecognizer",
        "DATE_DD_MM_YYYY",
        "\\b(?:0?[1-9]|[12][0-9]|3[01])[\\-/.](?:0?[1-9]|1[0-2])[\\-/.](?:19|20)\\d{2}\\b",
    ),
    (
        "DutchDateRecognizer",
        "DATE_MM_DD_YYYY",
        "\\b(?:0?[1-9]|1[0-2])[\\-/.](?:0?[1-9]|[12][0-9]|3[01])[\\-/.](?:19|20)\\d{2}\\b",
    ),
    (
        "DutchDateRecognizer",
        "DATE_YYYY_MM_DD",
        "\\b(?:19|20)\\d{2}[\\-/.](?:0?[1-9]|1[0-2])[\\-/.](?:0?[1-9]|[12][0-9]|3[01])\\b",
    ),
    (
        "DutchDateRecognizer",
        "DATE_DD_MM_YY",
        "\\b(?:0?[1-9]|[12][0-9]|3[01])[\\s/.-](?:0?[1-9]|1[0-2])[\\s/.-]\\d{2}\\b",
    ),
    (
        "DutchDateRecognizer",
        "DATE_DD_MONTH_YYYY",
        "(?i)\\b(?:0?[1-9]|[12][0-9]|3[01])\\s+(?:januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december)\\s+(?:19|20)\\d{2}\\b",
    ),
    ("DutchPassportIdRecognizer", "NL_DOC_OLD", "\\b[A-NP-Z]{2}[A-NP-Z0-9]{6}\\d\\b"),
    (
        "DutchPassportIdRecognizer",
        "NL_DOC_NEW",
        "\\b[A-NP-Z]{2}(?:[A-NP-Z]|[1-9]){6}[1-9]\\b",
    ),
    ("CaseNumberRecognizer", "CASE_Z", "\\bZ[-\\/]?\\d{4}[-\\/]?\\d{4,6}\\b"),
    (
        "CaseNumberRecognizer",
        "CASE_PREFIXED",
        "\\b(?:WOO|BEZWAAR|INT|VTH|WP)[-\\/]?\\d{4}[-\\/]?\\d{3,6}\\b",
    ),
    ("CaseNumberRecognizer", "CASE_YEAR_NUMBER", "\\b\\d{4}[-\\/]\\d{4,6}\\b"),
    ("CaseNumberRecognizer", "CASE_BAG_ID", "\\b\\d{16}\\b"),
    (
        "CaseNumberRecognizer",
        "CASE_UUID",
        "(?i)\\b[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\\b",
    ),
    ("CaseNumberRecognizer", "CASE_C_CIVIL", "\\bC\\/\\d{2}\\/\\d{5,8}\\b"),
    ("CaseNumberRecognizer", "CASE_AWB", "\\bAWB\\s?\\d{2}\\/\\d{3,6}\\b"),
    ("CaseNumberRecognizer", "CASE_HR", "\\bHR\\s?\\d{2}\\/\\d{5}\\b"),
    ("CaseNumberRecognizer", "CASE_GERECHTSHOF", "\\b200\\.\\d{5}\\b"),
    ("CaseNumberRecognizer", "CASE_OM", "\\b\\d{2}\\/\\d{6}-\\d{2}\\b"),
    (
        "CaseNumberRecognizer",
        "CASE_COURT_GENERIC",
        "\\b[A-Z]{4,5}\\s?\\d{2}\\/\\d{3,6}\\b",
    ),
    ("DutchDriversLicenseRecognizer", "NL_DRIVERS_LICENSE", "\\b\\d{10}\\b"),
]
