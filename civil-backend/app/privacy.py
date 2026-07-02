import re


PATTERNS = {
    "phone": re.compile(r"01[016789]-?\d{3,4}-?\d{4}"),
    "rrn": re.compile(r"\d{6}-?[1-4]\d{6}"),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "account": re.compile(r"\b\d{2,6}-\d{2,6}-\d{2,8}\b"),
}


def detect_personal_info(text: str) -> list[str]:
    """Lightweight local privacy scan used before/alongside the LLM reviewer."""
    findings: list[str] = []
    for name, pattern in PATTERNS.items():
        if pattern.search(text):
            findings.append(name)
    return findings

