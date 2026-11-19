"""Generic advertisement / watermark / site-noise detection."""

from __future__ import annotations

from txt2epub_cli.model import SourceLine
from txt2epub_cli.rules import RuleSet


def noise_reason(line: SourceLine, rules: RuleSet) -> str | None:
    """Return the matched pattern when a line looks like short site noise.

    Long body paragraphs are never deleted just because they contain a keyword
    such as "免费阅读"; only short lines (or lines that start with an obvious ad
    marker) are considered.
    """

    text = line.stripped
    if not text:
        return None
    if len(text) > rules.noise_max_length:
        return None
    for pattern in rules.noise_patterns:
        if pattern.search(text):
            return pattern.pattern
    return None
