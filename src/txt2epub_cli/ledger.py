"""The line ledger: every source line gets exactly one disposition."""

from __future__ import annotations

from collections import Counter

from txt2epub_cli.model import Disposition, SourceLine


class LineLedger:
    def __init__(self, lines: list[SourceLine]) -> None:
        self.lines = lines
        self._by_no = {line.line_no: line for line in lines}

    def __iter__(self):
        return iter(self.lines)

    def __len__(self) -> int:
        return len(self.lines)

    def get(self, line_no: int) -> SourceLine:
        return self._by_no[line_no]

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

    def mark_all(
        self,
        line_nos: list[int] | set[int],
        disposition: Disposition,
        reason: str = "",
    ) -> None:
        for line_no in line_nos:
            self.mark(line_no, disposition, reason)

    def counts(self) -> dict[Disposition, int]:
        return dict(Counter(line.disposition for line in self.lines))

    def dropped(self) -> list[SourceLine]:
        return [
            line
            for line in self.lines
            if line.disposition
            in (Disposition.NOISE, Disposition.DUPLICATE, Disposition.TOC_PAGE)
        ]
