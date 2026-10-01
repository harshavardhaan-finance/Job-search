"""Rule filter (SPEC.md Section 5, Stage 1).

Phase 2 only needs the title check, so collectors can skip obviously
unrelated jobs (e.g. software engineers) before storing them. The full
Stage-1 filter (exclude words, experience, salary, age) arrives in Phase 4.
"""
import re


def _keyword_pattern(keyword: str) -> re.Pattern:
    # Match at the start of a word, so "cost" matches "Costing" but
    # "mis" does not match inside "Commission".
    return re.compile(r"(?<![a-z0-9])" + re.escape(keyword.lower()))


def title_matches_include(title: str, include_keywords: list[str]) -> bool:
    text = (title or "").lower()
    return any(_keyword_pattern(k).search(text) for k in include_keywords)
