# Rules and TOML Configuration

Heading detection is deliberately line-oriented. Every pattern is applied to
one source line after outer whitespace and simple heading decoration are
stripped; patterns never see the whole document.

Start with a built-in profile, then add a TOML override:

```bash
txt2epub inspect book.txt --profile auto --rules my-rules.toml
```

The order is:

1. Built-in profile (`auto` by default).
2. TOML file from `--rules`.
3. `--max-heading-length` from the command line.

Unknown TOML keys and invalid regular expressions produce a rule/config error
(exit code `3`) instead of a traceback. The rules file is read as UTF-8 (a BOM
is allowed).

## Built-in profiles

| Profile | Behavior |
| --- | --- |
| `auto` (default) | Common web-novel formats, allows indented headings. |
| `strict` | Column-zero headings only, separator required, 40-character limit. |
| `loose` | Indented headings, longer titles, and pure-number headings. |

Site-specific cleanup is intentionally not a built-in profile. Put those
patterns in a local rules file instead; see the 知轩藏书 example below.

## TOML reference

### `[heading]`

| Key | Type | Default | Meaning |
| --- | --- | --- | --- |
| `max_length` | integer | `50` | Maximum heading length. `strict` uses `40`; `loose` uses `80`. |
| `allow_indented_headings` | boolean | `true` | Accept headings indented with U+3000, spaces, or tabs. `strict` sets this to `false`. |
| `pure_number_headings` | boolean | `false` | Recognize pure-number headings such as `1. 标题`. `loose` enables it. |
| `volume_suffix_special_suffixes` | list of strings | `["序", "章", "篇", "传", "记", "录"]` | Suffixes that can turn a combined volume title into a special section, for example `第一卷 卷名 卷首序`. |

### `[patterns]`

Each pattern key is a regular expression string or a list of strings. Patterns
are applied with `re.match`, so anchor them with `^` and usually `$` as well.

| Key | Named groups | Meaning |
| --- | --- | --- |
| `volume` | `num`, `title` | Volume headings such as `第一卷 卷名`. |
| `chapter` | `num`, `title`; optional `num2` | Chapter headings. Add `num2` for span headings such as `第1037章—第1038章`. |
| `section` | `num`, `title` | Section headings such as `第1节 标题`. |
| `combined` | `volume`, `vnum`, `chapter`, `cnum` | One-line volume + chapter headings. The chapter title is parsed from `chapter`. |
| `special` | `title` or `special` | Special sections. If neither group is present, the whole line becomes the title. |
| `replace_patterns` | boolean | When `true`, each supplied pattern key replaces the built-in list for that key instead of appending. |

By default, custom patterns are appended to the built-in lists. Named groups
are optional for matching, but the parser uses them for numbering, TOC titles,
gap detection, and dedupe. Prefer the names above.

### `[exclude]`

These lists prevent false positives. They are appended by default.

| Key | Meaning |
| --- | --- |
| `volume_suffixes` | Text after a volume unit that means the line is body text, not a heading. Example: `第三部门…` is not `第三部`. |
| `chapter_suffixes` | Text after `回` that means the line is body text. Example: `第一回合…` is not chapter one. |
| `replace_exclude` | When `true`, the supplied suffix lists replace the built-in lists instead of appending. |

### `[noise]`

| Key | Meaning |
| --- | --- |
| `patterns` | One regex string or a list. Noise patterns use `re.search`, so they can match anywhere in a short line. |
| `replace` | When `true`, replace the built-in noise list instead of appending. |

Noise removal only applies to short lines (80 characters or fewer). Removed
lines are recorded in the ledger and counted as dropped text, so coverage still
balances. `--keep-noise` keeps them as body paragraphs.

## Examples

The examples use `[0-9]` for brevity. The built-in number class also covers
full-width digits, Chinese numerals, financial numerals, 廿/卅, and Roman
numerals: `0-9０-９零〇一二三四五六七八九十百千万两壹贰叁肆伍陆柒捌玖拾佰仟廿卅IVXLCDMivxlcdm`.

### Standard volumes and chapters

```text
第一卷 占位卷名
第1章 占位标题
```

This is handled by the `auto` profile; no rule file is needed.

### No separator between number and title

```text
第一章占位标题
```

`auto` and `loose` already accept this. `strict` requires a separator. To keep
the strict profile but also accept no-separator chapter headings:

```toml
[patterns]
chapter = '^第(?P<num>[0-9零〇一二三四五六七八九十百千万两]+)[章节回集幕](?P<title>.+)$'
```

Because patterns are appended by default, this adds a fallback without
discarding the strict built-ins.

### A different chapter unit, such as 话

```text
第12话 占位标题
```

```toml
[patterns]
chapter = '^第(?P<num>[0-9零〇一二三四五六七八九十百千万两]+)话\s*(?P<title>.*)$'
```

`\s` matches ordinary spaces and the ideographic space U+3000.

### Indented headings

```text
　　第一章 占位标题
```

The `auto` and `loose` profiles accept indented headings. To turn that off:

```toml
[heading]
allow_indented_headings = false
```

Indented volume names have extra guards: they must be short (20 characters or
fewer) and followed by a chapter. Indented special sections that look like
ordinary sentences are kept as body text.

### Volume and chapter on one line

```text
第一卷 占位卷名 第1章 占位章名
```

The `auto` profile splits this into a volume node and a nested chapter. To
support a different unit, add a combined pattern:

```toml
[patterns]
combined = '^(?P<volume>第(?P<vnum>[0-9]+)篇.*?)[\s　:：]+(?P<chapter>第(?P<cnum>[0-9]+)回.*)$'
```

The one source line becomes two TOC levels: the volume from `volume`, and the
chapter from `chapter`.

### Pure-number headings

```text
1. 占位标题
001、序
```

```toml
[heading]
pure_number_headings = true
```

The built-in pure-number patterns accept `1. 标题` and `001、序`. For another
separator, add a chapter pattern instead:

```toml
[patterns]
chapter = '^(?P<num>[0-9]+)[）)]\s*(?P<title>.+)$'
```

### Custom special sections

```text
卷首语
设定集
```

```toml
[patterns]
special = [
  '^(?P<special>卷首语)$',
  '^(?P<title>设定集.*)$',
]
```

### Site noise and false positives

```toml
[noise]
patterns = ["免费阅读", "最新网址", "请收藏本站"]

[exclude]
volume_suffixes = ["门", "队"]
chapter_suffixes = ["回廊"]
```

### Site-specific noise

Site-specific cleanup belongs in a local rules file, not in a built-in profile.
For example, 知轩藏书-style pages can use:

```toml
[noise]
patterns = ["知轩藏书", "更多精校小说", 'zxcs\.me']
```

Save it as, for example, `zxs.toml` and pass `--rules zxs.toml`. These patterns
are appended to the built-in noise list. Add `replace = true` inside `[noise]`
if you want only these patterns instead.

### Replacing built-ins instead of appending

```toml
[patterns]
replace_patterns = true
chapter = '^第(?P<num>[0-9]+)话\s*(?P<title>.*)$'
```

This replaces the built-in chapter patterns but leaves the built-in volume,
section, combined, and special patterns untouched.
