# Synthetic TXT fixtures

Every fixture is original placeholder text. It deliberately imitates *format*
patterns from Chinese web novels without copying any real book, author, chapter
title, or body text.

| fixture | purpose |
|---|---|
| `simple_arabic.txt` | `第1章 标题` |
| `simple_chinese.txt` | `第一章 标题` |
| `zero_padded.txt` | `第0001章 标题` |
| `no_separator.txt` | `第一章标题` (no separator) |
| `volume_chapter.txt` | volume + chapter nesting |
| `volume_no_blank.txt` | volume heading with no blank line before it |
| `combined_prefix.txt` | repeated `第X卷 卷名 第Y章 章名` on one line |
| `combined_volume_special.txt` | `第X卷 卷名 卷首序` split into volume + special |
| `multi_number.txt` | `第104、105章` and `第1037章—第1038章` stay one node |
| `special_sections.txt` | 序章/前传/番外/终章/后记/完本感言 hierarchy |
| `duplicates_noise.txt` | same-number duplicate + indented noise heading + ad line |
| `toc_page.txt` | explicit embedded TOC page |
| `front_matter.txt` | 书名/作者/简介 metadata and front matter |
| `false_positives.txt` | narrative lines that look like headings but must be body |
| `indented_headings.txt` | all headings indented with U+3000 |

Encoding fixtures are generated at runtime in `tmp_path` (UTF-8, UTF-16, GB18030)
so no binary files are committed.
