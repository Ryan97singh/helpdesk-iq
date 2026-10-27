"""Input guardrails applied before any text reaches a third-party LLM."""

import re

PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("CARD", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("AADHAAR", re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b")),
    ("PAN", re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")),
    ("PHONE", re.compile(r"(?:\+91[ -]?)?\b[6-9]\d{9}\b")),
]

INJECTION_PATTERNS = [
    re.compile(p, re.I)
    for p in [
        r"ignore (all |any )?(the )?(previous|prior|above) (instructions|prompts?)",
        r"disregard (the |your )?(system|previous) (prompt|instructions)",
        r"(reveal|show|print) (me )?(the |your )?(system prompt|hidden instructions)",
        r"you are now (in )?(developer|dan|jailbreak) mode",
    ]
]


def redact_pii(text: str) -> tuple[str, list[str]]:
    """Replace PII with typed placeholders. Returns (redacted_text, kinds_found)."""
    found: list[str] = []
    for kind, pattern in PII_PATTERNS:
        text, n = pattern.subn(f"[{kind}]", text)
        if n:
            found.append(kind)
    return text, found


def looks_like_injection(text: str) -> bool:
    return any(p.search(text) for p in INJECTION_PATTERNS)
