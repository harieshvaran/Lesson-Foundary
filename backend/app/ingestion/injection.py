"""Prompt injection scanner for untrusted source text."""

import re
from typing import TypedDict


class InjectionMatch(TypedDict):
    pattern: str
    match_text: str
    position: int


class InjectionFlagResult(TypedDict):
    flagged: bool
    matches: list[InjectionMatch]


INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(above|safety)\s+instructions",
    r"you\s+are\s+now\s+(a|an)?",
    r"reveal\s+(the\s+)?system\s+prompt",
    r"output\s+(the\s+)?answer\s+key",
    r"</?SOURCE_DATA>",
    r"</?SYSTEM>",
    r"<OVERRIDE>",
]


def scan_for_prompt_injection(text: str) -> InjectionFlagResult:
    """Scans text for prompt injection patterns.
    
    Returns structured dict of flags. Non-empty matches indicate flagged text.
    Source text is STILL treated as data (never instructions).
    """
    matches: list[InjectionMatch] = []

    for pattern in INJECTION_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            matches.append({
                "pattern": pattern,
                "match_text": match.group(0),
                "position": match.start(),
            })

    return {
        "flagged": len(matches) > 0,
        "matches": matches,
    }
