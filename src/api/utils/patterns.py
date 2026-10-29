from typing import List, Optional

from presidio_analyzer import Pattern, PatternRecognizer


class DutchPhoneNumberRecognizer(PatternRecognizer):
    """Herkenner voor Nederlandse telefoonnummers.

    Gebruikt een regex-patroon voor mobiele en vaste nummers in NL-formaat.
    """

    def __init__(
        self,
        context: Optional[List[str]] = None,
        supported_language: str = "nl",
    ) -> None:
        patterns = [
            Pattern("DUTCH_PHONE", r"\b(?:0|(?:\+|00)31)[- ]?(?:\d[- ]?){9}\b", 0.6)
        ]
        super().__init__(
            supported_entity="PHONE_NUMBER",
            patterns=patterns,
            context=context,  # type: ignore[arg-type]
            supported_language=supported_language,
        )


class DutchIBANRecognizer(PatternRecognizer):
    """Herkenner voor IBAN bankrekeningnummers.

    Ondersteunt Nederlandse IBANs (beginnend met 'NL') en internationale IBANs,
    in zowel aaneengesloten als gespatieerde vormen.
    """

    def __init__(
        self,
        context: Optional[List[str]] = None,
        supported_language: str = "nl",
    ) -> None:
        patterns = [
            # Specifiek NL-patroon met of zonder spaties
            Pattern(
                "DUTCH_IBAN",
                r"\bNL\d{2}\s?[A-Z]{4}(?:\s?\d{10}|\s?\d{4}\s?\d{4}\s?\d{2})\b",
                0.6,
            ),
            # Algemeen internationaal IBAN-patroon (min 15, max 34 tekens), met optionele spaties
            # Landcode (2 letters) + controlegetal (2 cijfers) + BBAN (alfa-numeriek)
            Pattern(
                "INTL_IBAN",
                r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){2,7}(?:\s?[A-Z0-9]{1,4})?\b",
                0.55,
            ),
        ]
        super().__init__(
            supported_entity="IBAN",
            patterns=patterns,
            context=context,  # type: ignore[arg-type]
            supported_language=supported_language,
        )


class EmailRecognizer(PatternRecognizer):
    """Herkenner voor e-mailadressen volgens het standaard e-mailpatroon."""

    def __init__(
        self,
        context: Optional[List[str]] = None,
        supported_language: str = "nl",
    ) -> None:
        patterns = [
            Pattern(
                "EMAIL_ADDRESS",
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
                0.6,
            )
        ]
        super().__init__(
            supported_entity="EMAIL",
            patterns=patterns,
            context=context,  # type: ignore[arg-type]
            supported_language=supported_language,
        )


class DutchBSNRecognizer(PatternRecognizer):
    def __init__(self, context: Optional[List[str]] = None) -> None:
        pattern = Pattern(
            "NL_BSN",
            r"\b(?:\d{9}|\d{3}[- ]?\d{3}[- ]?\d{3})\b",
            0.6,
        )
        super().__init__(
            supported_entity="BSN",
            patterns=[pattern],
            context=context,  # type: ignore[arg-type]
            supported_language="nl",
        )

    def _is_valid_bsn(self, bsn: str) -> bool:
        digits = [int(d) for d in bsn if d.isdigit()]
        return sum((9 - i) * d for i, d in enumerate(digits)) % 11 == 0


class DutchPostcodeRecognizer(PatternRecognizer):
    def __init__(
        self, context: Optional[List[str]] = None, supported_language: str = "nl"
    ) -> None:
        pattern = Pattern("NL_POSTCODE", r"\b\d{4}\s?[A-Z]{2}\b", 0.55)
        super().__init__(
            "POSTCODE",
            patterns=[pattern],
            context=context,  # type: ignore[arg-type]
            supported_language=supported_language,
        )


# BTW-/VAT-nummer (NL999999999B99 – nieuw formaat)
class DutchVATRecognizer(PatternRecognizer):
    def __init__(
        self, context: Optional[List[str]] = None, supported_language: str = "nl"
    ) -> None:
        pattern = Pattern("NL_VAT", r"\bNL\d{9}B\d{2}\b", 0.6)
        super().__init__(
            "VAT_NUMBER",
            patterns=[pattern],
            context=context,  # type: ignore[arg-type]
            supported_language=supported_language,
        )


# KvK-nummer (8 cijfers in Handelsregister)
class DutchKvKRecognizer(PatternRecognizer):
    def __init__(
        self, context: Optional[List[str]] = None, supported_language: str = "nl"
    ) -> None:
        patterns = [
            Pattern("KVK_8_DIGIT", r"\b\d{8}\b", 0.45)  # raise score with context
        ]
        super().__init__(
            "KVK_NUMBER",
            patterns=patterns,
            context=context,  # type: ignore[arg-type]
            supported_language=supported_language,
        )


# Nederlands kenteken (6 posities, diverse combinaties)
_LICENSE_PATTERNS = [
    r"[A-Z]{2}-\d{2}-\d{2}",
    r"\d{2}-\d{2}-[A-Z]{2}",
    r"\d{2}-[A-Z]{2}-\d{2}",
    r"[A-Z]{2}-\d{2}-[A-Z]{2}",
    r"[A-Z]{2}-[A-Z]{2}-\d{2}",
    r"\d{2}-[A-Z]{2}-[A-Z]{2}",
]


class DutchLicensePlateRecognizer(PatternRecognizer):
    def __init__(
        self, context: Optional[List[str]] = None, supported_language: str = "nl"
    ) -> None:
        pattern = Pattern("NL_PLATE", rf"\b(?:{'|'.join(_LICENSE_PATTERNS)})\b", 0.5)
        super().__init__(
            "LICENSE_PLATE",
            patterns=[pattern],
            context=context,  # type: ignore[arg-type]
            supported_language=supported_language,
        )


# Taal-onafhankelijke IPv4-adres-herkenner
class IPv4Recognizer(PatternRecognizer):
    def __init__(
        self, context: Optional[List[str]] = None, supported_language: str = "any"
    ) -> None:
        pattern = Pattern(
            "IPV4",
            r"\b(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)"
            r"(?:\.(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}\b",
            0.5,
        )
        super().__init__(
            "IP_ADDRESS",
            patterns=[pattern],
            context=context,  # type: ignore[arg-type]
            supported_language=supported_language,
        )


class DutchDateRecognizer(PatternRecognizer):
    def __init__(
        self, context: Optional[List[str]] = None, supported_language: str = "nl"
    ) -> None:
        patterns = [
            # dd-mm-yyyy, dd/mm/yyyy, dd.mm.yyyy
            Pattern(
                "DATE_DD_MM_YYYY",
                r"\b(?:0?[1-9]|[12][0-9]|3[01])[\-/.](?:0?[1-9]|1[0-2])[\-/.](?:19|20)\d{2}\b",
                0.5,
            ),
            # mm-dd-yyyy, mm/dd/yyyy, mm.dd.yyyy
            Pattern(
                "DATE_MM_DD_YYYY",
                r"\b(?:0?[1-9]|1[0-2])[\-/.](?:0?[1-9]|[12][0-9]|3[01])[\-/.](?:19|20)\d{2}\b",
                0.5,
            ),
            # yyyy-mm-dd
            Pattern(
                "DATE_YYYY_MM_DD",
                r"\b(?:19|20)\d{2}[\-/.](?:0?[1-9]|1[0-2])[\-/.](?:0?[1-9]|[12][0-9]|3[01])\b",
                0.5,
            ),
            # dd mm yy (space-separated, 2-digit year)
            Pattern(
                "DATE_DD_MM_YY",
                r"\b(?:0?[1-9]|[12][0-9]|3[01])[\s/.-](?:0?[1-9]|1[0-2])[\s/.-]\d{2}\b",
                0.45,
            ),
            # 1 september 2020 (spelled-out months in Dutch, case-insensitive)
            Pattern(
                "DATE_DD_MONTH_YYYY",
                r"(?i)\b(?:0?[1-9]|[12][0-9]|3[01])\s+(?:januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december)\s+(?:19|20)\d{2}\b",
                0.5,
            ),
        ]
        super().__init__(
            supported_entity="DATE_TIME",
            patterns=patterns,
            context=context,  # type: ignore[arg-type]
            supported_language=supported_language,
        )


class DutchPassportIdRecognizer(PatternRecognizer):
    """Herkenner voor Nederlandse paspoort-/identiteitskaartnummers.

    Regels:
    - Positie 1-2: letters (hoofdletters), zonder de letter 'O'.
    - Positie 3-8: letters (zonder 'O') of cijfers; sinds 2019 geen '0' meer in nieuwe documenten.
    - Positie 9: cijfer (in nieuwe documenten 1-9).

    We ondersteunen daarom twee patronen:
    - NL_DOC_OLD: toestaat '0' (oude documenten)
    - NL_DOC_NEW: sluit '0' uit (nieuwe documenten)
    """

    def __init__(
        self, context: Optional[List[str]] = None, supported_language: str = "nl"
    ) -> None:
        patterns = [
            # Oud formaat: letters zonder 'O', pos 3-8 letters/cijfers (0-9), pos 9 cijfer (0-9)
            Pattern(
                "NL_DOC_OLD",
                r"\b[A-NP-Z]{2}[A-NP-Z0-9]{6}\d\b",
                0.55,
            ),
            # Nieuw formaat: geen '0' meer; cijfers 1-9, pos 9 ook 1-9
            Pattern(
                "NL_DOC_NEW",
                r"\b[A-NP-Z]{2}(?:[A-NP-Z]|[1-9]){6}[1-9]\b",
                0.6,
            ),
        ]
        super().__init__(
            supported_entity="ID_NO",
            patterns=patterns,
            context=context,  # type: ignore[arg-type]
            supported_language=supported_language,
        )


class CaseNumberRecognizer(PatternRecognizer):
    """Herkenner voor diverse (rechts)zaak- en dossiernummers.

    Ondersteunt o.a. Z-/WOO-/BEZWAAR-/INT-/VTH-/WP-nummers, algemene jaar/nummer,
    BAG-ID (16 cijfers), UUID-achtige zaak-ID's, en bekende gerecht-formats.
    """

    def __init__(
        self, context: Optional[List[str]] = None, supported_language: str = "nl"
    ) -> None:
        patterns = [
            # Z-YYYY-999999 (Z-jaar-nummer), ook permissief met '-' of '/'
            Pattern(
                "CASE_Z",
                r"\bZ[-\/]?\d{4}[-\/]?\d{4,6}\b",
                0.55,
            ),
            # WOO/BEZWAAR/INT/VTH/WP-YYYY-999 (of langer)
            Pattern(
                "CASE_PREFIXED",
                r"\b(?:WOO|BEZWAAR|INT|VTH|WP)[-\/]?\d{4}[-\/]?\d{3,6}\b",
                0.6,
            ),
            # Algemeen Jaar-Nummer (risico op false positives, lagere score)
            Pattern(
                "CASE_YEAR_NUMBER",
                r"\b\d{4}[-\/]\d{4,6}\b",
                0.45,
            ),
            # BAG ID, exact 16 cijfers (lager vertrouwen want generiek)
            Pattern(
                "CASE_BAG_ID",
                r"\b\d{16}\b",
                0.4,
            ),
            # UUID-stijl Zaak-ID (case-insensitive hex)
            Pattern(
                "CASE_UUID",
                r"(?i)\b[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}\b",
                0.6,
            ),
            # Civiel: C/XX/NNNNNN (meer digits toegestaan)
            Pattern(
                "CASE_C_CIVIL",
                r"\bC\/\d{2}\/\d{5,8}\b",
                0.55,
            ),
            # Bestuurlijk: AWB 21/12345
            Pattern(
                "CASE_AWB",
                r"\bAWB\s?\d{2}\/\d{3,6}\b",
                0.6,
            ),
            # Hoge Raad: HR 21/00123
            Pattern(
                "CASE_HR",
                r"\bHR\s?\d{2}\/\d{5}\b",
                0.6,
            ),
            # Gerechtshof: 200.12345
            Pattern(
                "CASE_GERECHTSHOF",
                r"\b200\.\d{5}\b",
                0.55,
            ),
            # Strafzaak OM: 08/123456-89
            Pattern(
                "CASE_OM",
                r"\b\d{2}\/\d{6}-\d{2}\b",
                0.6,
            ),
            # Algemeen: RBAMS 21/12345 (of andere rechtbankcodes 4-5 letters)
            Pattern(
                "CASE_COURT_GENERIC",
                r"\b[A-Z]{4,5}\s?\d{2}\/\d{3,6}\b",
                0.55,
            ),
        ]
        super().__init__(
            supported_entity="CASE_NO",
            patterns=patterns,
            context=context,  # type: ignore[arg-type]
            supported_language=supported_language,
        )


class DutchDriversLicenseRecognizer(PatternRecognizer):
    """Herkenner voor Nederlands rijbewijsnummer (10 cijfers).

    Detecteert exact 10 opeenvolgende cijfers. Score relatief laag vanwege
    mogelijke false positives bij generieke cijfersreeksen.
    """

    def __init__(
        self, context: Optional[List[str]] = None, supported_language: str = "nl"
    ) -> None:
        patterns = [
            Pattern(
                "NL_DRIVERS_LICENSE",
                r"\b\d{10}\b",
                0.45,
            )
        ]
        super().__init__(
            supported_entity="DRIVERS_LICENSE",
            patterns=patterns,
            context=context,  # type: ignore[arg-type]
            supported_language=supported_language,
        )
