from typing import ClassVar, List, Optional

from presidio_analyzer import Pattern, PatternRecognizer

# (name, regex, score) of one pattern.
PatternRow = tuple[str, str, float]


class _TableRecognizer(PatternRecognizer):
    """Pattern recognizer configured by class attributes.

    A subclass sets ``ENTITY``, ``PATTERNS`` and, when it is not Dutch,
    ``LANGUAGE``.
    """

    ENTITY: ClassVar[str]
    PATTERNS: ClassVar[tuple[PatternRow, ...]]
    LANGUAGE: ClassVar[str] = "nl"

    def __init__(
        self,
        context: Optional[List[str]] = None,
        supported_language: Optional[str] = None,
    ) -> None:
        super().__init__(
            supported_entity=self.ENTITY,
            patterns=[
                Pattern(name, regex, score) for name, regex, score in self.PATTERNS
            ],
            context=context,  # type: ignore[arg-type]
            supported_language=(
                self.LANGUAGE if supported_language is None else supported_language
            ),
        )


class DutchPhoneNumberRecognizer(_TableRecognizer):
    """Herkenner voor Nederlandse telefoonnummers.

    Gebruikt een regex-patroon voor mobiele en vaste nummers in NL-formaat.
    """

    ENTITY = "PHONE_NUMBER"
    PATTERNS = (("DUTCH_PHONE", r"\b(?:0|(?:\+|00)31)[- ]?(?:\d[- ]?){9}\b", 0.6),)


class DutchIBANRecognizer(_TableRecognizer):
    """Herkenner voor IBAN bankrekeningnummers.

    Ondersteunt Nederlandse IBANs (beginnend met 'NL') en internationale IBANs,
    in zowel aaneengesloten als gespatieerde vormen.
    """

    ENTITY = "IBAN"
    PATTERNS = (
        # Specifiek NL-patroon met of zonder spaties
        (
            "DUTCH_IBAN",
            r"\bNL\d{2}\s?[A-Z]{4}(?:\s?\d{10}|\s?\d{4}\s?\d{4}\s?\d{2})\b",
            0.6,
        ),
        # Algemeen internationaal IBAN-patroon (min 15, max 34 tekens), met optionele spaties
        # Landcode (2 letters) + controlegetal (2 cijfers) + BBAN (alfa-numeriek)
        (
            "INTL_IBAN",
            r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){2,7}(?:\s?[A-Z0-9]{1,4})?\b",
            0.55,
        ),
    )


class EmailRecognizer(_TableRecognizer):
    """Herkenner voor e-mailadressen volgens het standaard e-mailpatroon."""

    ENTITY = "EMAIL"
    PATTERNS = (
        (
            "EMAIL_ADDRESS",
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
            0.6,
        ),
    )


class DutchBSNRecognizer(_TableRecognizer):
    ENTITY = "BSN"
    PATTERNS = (("NL_BSN", r"\b(?:\d{9}|\d{3}[- ]?\d{3}[- ]?\d{3})\b", 0.6),)

    def __init__(self, context: Optional[List[str]] = None) -> None:
        super().__init__(context=context)

    def _is_valid_bsn(self, bsn: str) -> bool:
        digits = [int(d) for d in bsn if d.isdigit()]
        return sum((9 - i) * d for i, d in enumerate(digits)) % 11 == 0


class DutchPostcodeRecognizer(_TableRecognizer):
    ENTITY = "POSTCODE"
    PATTERNS = (("NL_POSTCODE", r"\b\d{4}\s?[A-Z]{2}\b", 0.55),)


# BTW-/VAT-nummer (NL999999999B99 – nieuw formaat)
class DutchVATRecognizer(_TableRecognizer):
    ENTITY = "VAT_NUMBER"
    PATTERNS = (("NL_VAT", r"\bNL\d{9}B\d{2}\b", 0.6),)


# KvK-nummer (8 cijfers in Handelsregister)
class DutchKvKRecognizer(_TableRecognizer):
    ENTITY = "KVK_NUMBER"
    PATTERNS = (("KVK_8_DIGIT", r"\b\d{8}\b", 0.45),)  # raise score with context


# Nederlands kenteken (6 posities, diverse combinaties)
_LICENSE_PATTERNS = [
    r"[A-Z]{2}-\d{2}-\d{2}",
    r"\d{2}-\d{2}-[A-Z]{2}",
    r"\d{2}-[A-Z]{2}-\d{2}",
    r"[A-Z]{2}-\d{2}-[A-Z]{2}",
    r"[A-Z]{2}-[A-Z]{2}-\d{2}",
    r"\d{2}-[A-Z]{2}-[A-Z]{2}",
]


class DutchLicensePlateRecognizer(_TableRecognizer):
    ENTITY = "LICENSE_PLATE"
    PATTERNS = (("NL_PLATE", rf"\b(?:{'|'.join(_LICENSE_PATTERNS)})\b", 0.5),)


# Taal-onafhankelijke IPv4-adres-herkenner
class IPv4Recognizer(_TableRecognizer):
    ENTITY = "IP_ADDRESS"
    LANGUAGE = "any"
    PATTERNS = (
        (
            "IPV4",
            r"\b(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)"
            r"(?:\.(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}\b",
            0.5,
        ),
    )


class DutchDateRecognizer(_TableRecognizer):
    ENTITY = "DATE_TIME"
    PATTERNS = (
        # dd-mm-yyyy, dd/mm/yyyy, dd.mm.yyyy
        (
            "DATE_DD_MM_YYYY",
            r"\b(?:0?[1-9]|[12][0-9]|3[01])[\-/.](?:0?[1-9]|1[0-2])[\-/.](?:19|20)\d{2}\b",
            0.5,
        ),
        # mm-dd-yyyy, mm/dd/yyyy, mm.dd.yyyy
        (
            "DATE_MM_DD_YYYY",
            r"\b(?:0?[1-9]|1[0-2])[\-/.](?:0?[1-9]|[12][0-9]|3[01])[\-/.](?:19|20)\d{2}\b",
            0.5,
        ),
        # yyyy-mm-dd
        (
            "DATE_YYYY_MM_DD",
            r"\b(?:19|20)\d{2}[\-/.](?:0?[1-9]|1[0-2])[\-/.](?:0?[1-9]|[12][0-9]|3[01])\b",
            0.5,
        ),
        # dd mm yy (space-separated, 2-digit year)
        (
            "DATE_DD_MM_YY",
            r"\b(?:0?[1-9]|[12][0-9]|3[01])[\s/.-](?:0?[1-9]|1[0-2])[\s/.-]\d{2}\b",
            0.45,
        ),
        # 1 september 2020 (spelled-out months in Dutch, case-insensitive)
        (
            "DATE_DD_MONTH_YYYY",
            r"(?i)\b(?:0?[1-9]|[12][0-9]|3[01])\s+(?:januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december)\s+(?:19|20)\d{2}\b",
            0.5,
        ),
    )


class DutchPassportIdRecognizer(_TableRecognizer):
    """Herkenner voor Nederlandse paspoort-/identiteitskaartnummers.

    Regels:
    - Positie 1-2: letters (hoofdletters), zonder de letter 'O'.
    - Positie 3-8: letters (zonder 'O') of cijfers; sinds 2019 geen '0' meer in nieuwe documenten.
    - Positie 9: cijfer (in nieuwe documenten 1-9).

    We ondersteunen daarom twee patronen:
    - NL_DOC_OLD: toestaat '0' (oude documenten)
    - NL_DOC_NEW: sluit '0' uit (nieuwe documenten)
    """

    ENTITY = "ID_NO"
    PATTERNS = (
        # Oud formaat: letters zonder 'O', pos 3-8 letters/cijfers (0-9), pos 9 cijfer (0-9)
        ("NL_DOC_OLD", r"\b[A-NP-Z]{2}[A-NP-Z0-9]{6}\d\b", 0.55),
        # Nieuw formaat: geen '0' meer; cijfers 1-9, pos 9 ook 1-9
        ("NL_DOC_NEW", r"\b[A-NP-Z]{2}(?:[A-NP-Z]|[1-9]){6}[1-9]\b", 0.6),
    )


class CaseNumberRecognizer(_TableRecognizer):
    """Herkenner voor diverse (rechts)zaak- en dossiernummers.

    Ondersteunt o.a. Z-/WOO-/BEZWAAR-/INT-/VTH-/WP-nummers, algemene jaar/nummer,
    BAG-ID (16 cijfers), UUID-achtige zaak-ID's, en bekende gerecht-formats.
    """

    ENTITY = "CASE_NO"
    PATTERNS = (
        # Z-YYYY-999999 (Z-jaar-nummer), ook permissief met '-' of '/'
        ("CASE_Z", r"\bZ[-\/]?\d{4}[-\/]?\d{4,6}\b", 0.55),
        # WOO/BEZWAAR/INT/VTH/WP-YYYY-999 (of langer)
        (
            "CASE_PREFIXED",
            r"\b(?:WOO|BEZWAAR|INT|VTH|WP)[-\/]?\d{4}[-\/]?\d{3,6}\b",
            0.6,
        ),
        # Algemeen Jaar-Nummer (risico op false positives, lagere score)
        ("CASE_YEAR_NUMBER", r"\b\d{4}[-\/]\d{4,6}\b", 0.45),
        # BAG ID, exact 16 cijfers (lager vertrouwen want generiek)
        ("CASE_BAG_ID", r"\b\d{16}\b", 0.4),
        # UUID-stijl Zaak-ID (case-insensitive hex)
        (
            "CASE_UUID",
            r"(?i)\b[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\b",
            0.6,
        ),
        # Civiel: C/XX/NNNNNN (meer digits toegestaan)
        ("CASE_C_CIVIL", r"\bC\/\d{2}\/\d{5,8}\b", 0.55),
        # Bestuurlijk: AWB 21/12345
        ("CASE_AWB", r"\bAWB\s?\d{2}\/\d{3,6}\b", 0.6),
        # Hoge Raad: HR 21/00123
        ("CASE_HR", r"\bHR\s?\d{2}\/\d{5}\b", 0.6),
        # Gerechtshof: 200.12345
        ("CASE_GERECHTSHOF", r"\b200\.\d{5}\b", 0.55),
        # Strafzaak OM: 08/123456-89
        ("CASE_OM", r"\b\d{2}\/\d{6}-\d{2}\b", 0.6),
        # Algemeen: RBAMS 21/12345 (of andere rechtbankcodes 4-5 letters)
        ("CASE_COURT_GENERIC", r"\b[A-Z]{4,5}\s?\d{2}\/\d{3,6}\b", 0.55),
    )


class DutchDriversLicenseRecognizer(_TableRecognizer):
    """Herkenner voor Nederlands rijbewijsnummer (10 cijfers).

    Detecteert exact 10 opeenvolgende cijfers. Score relatief laag vanwege
    mogelijke false positives bij generieke cijfersreeksen.
    """

    ENTITY = "DRIVERS_LICENSE"
    PATTERNS = (("NL_DRIVERS_LICENSE", r"\b\d{10}\b", 0.45),)
