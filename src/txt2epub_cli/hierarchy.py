"""Build the volume / chapter / section tree from accepted headings."""

from __future__ import annotations

from txt2epub_cli.model import Heading, HeadingKind, Node


def _attach(parent: Node, child: Node) -> None:
    child.parent = parent
    parent.children.append(child)


def build_tree(headings: list[Heading]) -> tuple[list[Node], dict[int, Node]]:
    """Return roots plus a mapping from heading source line to the body target.

    A combined heading line produces a volume event followed by a chapter event;
    the chapter wins as the body target, which is what readers expect.
    """

    roots: list[Node] = []
    line_targets: dict[int, Node] = {}
    current_volume: Node | None = None
    current_container: Node | None = None
    current_chapter: Node | None = None

    for heading in headings:
        node = Node(heading=heading)

        if heading.kind == HeadingKind.VOLUME:
            roots.append(node)
            current_volume = node
            current_container = None
            current_chapter = None
        elif heading.kind == HeadingKind.SPECIAL:
            if heading.detail.get("in_volume") and current_volume is not None:
                _attach(current_volume, node)
                current_chapter = node
            elif heading.detail.get("container"):
                roots.append(node)
                current_container = node
                current_volume = None
                current_chapter = None
            else:
                roots.append(node)
                current_chapter = node
        elif heading.kind == HeadingKind.CHAPTER:
            parent = current_container or current_volume
            if parent is None:
                roots.append(node)
            else:
                _attach(parent, node)
            current_chapter = node
        elif heading.kind == HeadingKind.SECTION:
            parent = current_chapter or current_container or current_volume
            if parent is None:
                roots.append(node)
            else:
                _attach(parent, node)

        # Normalize depth: roots=1, children=2, grandchildren=3 (capped in output).
        if node.parent is None:
            heading.level = 1
        else:
            heading.level = min(node.parent.heading.level + 1, 3)

        line_targets[heading.line_no] = node

    return roots, line_targets


def flatten(roots: list[Node]) -> list[Node]:
    result: list[Node] = []
    for root in roots:
        result.extend(root.walk())
    return result
