"""Deterministic checks for text that would leave the machine (search queries, cloud questions).

This is the Phase 0 seed of the Phase 2 search-broker policy. The rules borrow from the HIPAA
Safe Harbor identifier list: no names or other supplied sensitive terms, no dates finer than a
year, no ZIP-level geography, no ages over 89, no record/account-style numbers, no contact
details. A query that passes has fewer obvious identifiers. It is not proven anonymous:
paraphrases, rare combinations of facts and rounded values can still identify a person.

Findings name the rule and the character span only, never the matched text, so callers can log
them without copying private values into logs. Standard library only; Python 3.9+.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
import unicodedata
from typing import Iterable, List, Sequence, Tuple, Union

# Rules that justify blocking or owner approval. 'too-long' is advisory.
HARD_RULES = frozenset({
    'sensitive-term', 'personal-number', 'date-finer-than-year', 'zip-like', 'age-over-89',
    'long-digit-run', 'email', 'phone', 'url-with-query', 'ip-address',
})

MONTHS = ('january|february|march|april|may|june|july|august|september|october|november|'
          'december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec')
DIGIT_WORDS = {'zero': '0', 'oh': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
               'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9'}

_DATE_PATTERNS = (
    re.compile(r'\b\d{4}-\d{1,2}-\d{1,2}\b'),                                  # 2026-03-04
    re.compile(r'\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b'),                         # 3/4, 03/04/26
    re.compile(r'\b\d{1,2}\.\d{1,2}\.\d{2,4}\b'),                              # 03.04.2026
    re.compile(rf'\b(?:{MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?\b', re.I),     # March 3rd
    re.compile(rf'\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:{MONTHS})\b', re.I),  # 3rd of March
    re.compile(rf'\b(?:{MONTHS})\.?\s+\d{{4}}\b', re.I),                       # March 2026
)
_AGE_PATTERNS = (
    re.compile(r'\b(\d{2,3})[\s-]*(?:years?|yrs?|y/?o)[\s-]*old\b', re.I),
    re.compile(r'\b(\d{2,3})[\s-]*(?:y/?o)\b', re.I),
    re.compile(r'\b(?:age|aged)\s*(\d{2,3})\b', re.I),
)
_EMAIL = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')
_PHONE = re.compile(r'(?:\+\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b')
_URL_WITH_QUERY = re.compile(r'https?://\S+\?\S+', re.I)
_IPV4 = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
_DIGIT_RUN = re.compile(r'\d(?:[\s-]?\d){5,}')        # 6+ digits, allowing spaces/dashes
_ZIP = re.compile(r'(?<![\d.,])\d{5}(?:-\d{4})?(?![\d.,])')
_NUMBER = re.compile(r'(?<![\w.])\d[\d,]*(?:\.\d+)?')
_WORD = re.compile(r'[a-z]+', re.I)

Span = Tuple[int, int]
NumberLike = Union[str, int, float, Decimal]


@dataclass(frozen=True)
class Finding:
    rule: str
    span: Span

    @property
    def hard(self) -> bool:
        return self.rule in HARD_RULES


def normalize(text: str) -> str:
    """Casefold, strip accents and punctuation, collapse whitespace."""
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(ch for ch in text if not unicodedata.combining(ch)).casefold()
    return ' '.join(re.sub(r'[^\w]+', ' ', text).split())


def _decimal(value: NumberLike):
    try:
        return Decimal(str(value).replace(',', '').replace('$', '').strip())
    except InvalidOperation:
        return None


def _number_forms(values: Iterable[NumberLike]) -> set:
    """Exact values, plus the integer part when it has 3+ digits (18,437.29 also blocks 18437)."""
    forms = set()
    for value in values:
        number = _decimal(value)
        if number is None:
            continue
        forms.add(number)
        whole = int(number)
        if abs(whole) >= 100:
            forms.add(Decimal(whole))
    return forms


def spelled_digits(text: str) -> List[Tuple[str, Span]]:
    """Find runs of 2+ spelled digit words ('one eight seven' -> '187') with their spans."""
    runs: List[Tuple[str, Span]] = []
    digits, start, end = '', 0, 0
    for match in _WORD.finditer(text):
        digit = DIGIT_WORDS.get(match.group().lower())
        contiguous = bool(digits) and re.fullmatch(r'[\s,-]*', text[end:match.start()])
        if digit is not None and (not digits or contiguous):
            start = match.start() if not digits else start
            digits, end = digits + digit, match.end()
            continue
        if len(digits) >= 2:
            runs.append((digits, (start, end)))
        digits, start, end = (digit, match.start(), match.end()) if digit else ('', 0, 0)
    if len(digits) >= 2:
        runs.append((digits, (start, end)))
    return runs


def check(query: str, *, terms: Sequence[str] = (), numbers: Sequence[NumberLike] = (),
          max_chars: int = 256, max_words: int = 32) -> List[Finding]:
    """Return policy findings for an outbound query. An empty list means no rule matched."""
    findings: List[Finding] = []

    def add(rule: str, span: Span) -> None:
        findings.append(Finding(rule, span))

    padded = f' {normalize(query)} '
    for term in terms:
        needle = normalize(term)
        if needle and f' {needle} ' in padded:
            add('sensitive-term', (0, len(query)))   # normalized text has no stable original span

    personal = _number_forms(numbers)
    for match in _NUMBER.finditer(query):
        value = _decimal(match.group())
        if value is not None and value in personal:
            add('personal-number', match.span())
    for digits, span in spelled_digits(query):
        value = Decimal(digits)
        if value in personal or len(digits) >= 6:
            add('personal-number' if value in personal else 'long-digit-run', span)

    for pattern in _DATE_PATTERNS:
        for match in pattern.finditer(query):
            add('date-finer-than-year', match.span())
    for pattern in _AGE_PATTERNS:
        for match in pattern.finditer(query):
            if int(match.group(1)) > 89:
                add('age-over-89', match.span())
    for rule, pattern in (('email', _EMAIL), ('url-with-query', _URL_WITH_QUERY),
                          ('ip-address', _IPV4), ('phone', _PHONE)):
        for match in pattern.finditer(query):
            add(rule, match.span())
    for match in _DIGIT_RUN.finditer(query):
        add('long-digit-run', match.span())
    for match in _ZIP.finditer(query):
        add('zip-like', match.span())

    if len(query) > max_chars or len(query.split()) > max_words:
        add('too-long', (0, len(query)))
    return sorted(set(findings), key=lambda f: (f.span, f.rule))


def hard_findings(query: str, **kwargs) -> List[Finding]:
    return [finding for finding in check(query, **kwargs) if finding.hard]
