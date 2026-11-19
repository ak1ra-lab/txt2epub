"""The line ledger: every source line gets exactly one disposition."""

from __future__ import annotations

from collections import Counter

from txt2epub_cli.model import Disposition, SourceLine


class LineLedger:
    def __init__(self, lines: list[SourceLine]) -> None:
        self._by_no = {line.line_no: line for line in lines}

    def mark(
        self,
        line_no: int,
        disposition: Disposition,
        reason: str = "",
        owner_id: str | None = None,
    ) -> SourceLine:
        line = self._by_no[line_no]
        line.disposition = disposition
        line.reason = reason
        line.owner_id = owner_id
        return line

    def counts(self) -> dict[Disposition, int]:
        return dict(Counter(line.disposition for line in self._by_no.values()))
