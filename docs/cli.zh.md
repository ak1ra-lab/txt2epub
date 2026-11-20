# 命令行参考

```text
txt2epub [COMMON OPTIONS] inspect PATH...
txt2epub [COMMON OPTIONS] convert PATH... [CONVERT OPTIONS]
```

## 通用选项

| 选项 | 说明 |
| --- | --- |
| `PATH...` | 一个或多个源文件。通配符由 shell 展开。 |
| `--profile {auto,strict,loose}` | 内置规则预设（默认：`auto`）。 |
| `--rules PATH` | 在预设之上加载 TOML 规则覆盖。 |
| `--encoding NAME` | 强制指定源文件编码（例如 `gb18030`）。 |
| `--max-heading-length N` | 在预设和 TOML 之后覆盖标题长度上限。 |
| `--keep-noise` | 保留站点广告和水印，作为正文写入。 |
| `--keep-toc` | 保留内嵌目录页，作为前言写入。 |
| `--dedupe {off,exact,similar}` | 可选的章节去重模式（默认：`off`）。 |

## inspect

`inspect` 只解析源文件并输出报告，不写文件。

| 选项 | 说明 |
| --- | --- |
| `--json` | 输出机器可读的 JSON，而不是人类可读报告。 |
| `--limit N` | 人类可读输出中显示的可疑问题数量（默认：10；`0` 表示隐藏列表）。 |
| `--verbose` | 显示全部可疑问题。 |
| `--ignore-issue CODE` | 从人类可读列表中隐藏指定问题代码。可重复使用或用逗号分隔。 |
| `--only-issue CODE` | 只显示指定问题代码。可重复使用或用逗号分隔。 |

`--ignore-issue` 和 `--only-issue` 只影响人类可读的可疑列表；`--json` 始终
包含完整的问题列表。

常见问题代码包括 `number_gap`、`duplicate_number`、`number_conflict` 和
`duplicate_indented`。

```bash
# 隐藏已知的源文件序号缺口
txt2epub inspect book.txt --verbose --ignore-issue number_gap

# 隐藏多个问题代码
txt2epub inspect book.txt --verbose \
  --ignore-issue number_gap,duplicate_number

# 只显示冲突和缺口
txt2epub inspect book.txt --only-issue number_conflict,number_gap

# 缩进重复标题的严重级别为 info
txt2epub inspect book.txt --only-issue duplicate_indented
```

只处理一个文件时，`--json` 输出单个报告对象；处理多个文件时输出
`{"schema_version": 1, "files": [...]}`。

## convert

`convert` 解析每个源文件、校验覆盖率并写出 EPUB。

| 选项 | 说明 |
| --- | --- |
| `-o, --output-dir DIR` | 输出目录（默认：每个源文件所在目录）。 |
| `--dry-run` | 只解析和报告，不写 EPUB；在汇总中计为成功。 |
| `--report PATH` | 写出 JSON 报告。 |
| `--force` | 覆盖已存在的输出文件；不加此选项时跳过。 |
| `--allow-loss` | 即使覆盖率校验失败也写出 EPUB。 |
| `--split-size BYTES` | 超过该 UTF-8 字节数的章节会被拆分（默认：`262144`，必须为正数）。 |
| `--indent-em EM` | 正文段落的 CSS 首行缩进（默认：`2.0`；`0` 表示不缩进）。 |
| `--no-indent` | 等同于 `--indent-em 0`。 |
| `--css PATH` | 替换内置样式表，优先级高于 `--indent-em`。 |
| `--verbose` | 失败时显示 traceback。 |

```bash
# 在源文件旁边生成 EPUB
txt2epub convert book.txt

# 批量输出到目录
txt2epub convert *.txt -o out/

# 只解析和报告
txt2epub convert book.txt --dry-run

# 写 JSON 报告
txt2epub convert *.txt -o out/ --report out/report.json

# 覆盖已有输出
txt2epub convert *.txt -o out/ --force

# 不缩进首行
txt2epub convert book.txt --no-indent

# 自定义首行缩进（单位 em）
txt2epub convert book.txt --indent-em 1.5

# 完全替换内置样式表
txt2epub convert book.txt --css my-style.css
```

### 已有输出与批量汇总

`convert` 不会询问。目标文件已存在且没有传入 `--force` 时，源文件会在解析
前直接跳过。因此重复执行批量转换既快又安全：

```text
SKIP book.txt: out/book.epub exists (use --force to overwrite)
Summary: 2 succeeded, 1 failed, 3 skipped
```

- 跳过不算失败。如果全部文件都被跳过，退出码为 `0`。
- `--dry-run` 不写文件，因此不会因为输出已存在而跳过。
- 单个文件失败后会继续处理其余文件。汇总始终报告成功、失败和跳过的数量。

### JSON 报告

`convert` 的每个报告条目都有 `status` 字段：

| 状态 | 含义 |
| --- | --- |
| `converted` | EPUB 已成功写出。 |
| `dry-run` | 已解析和报告，未写 EPUB。 |
| `skipped` | 目标已存在且未传入 `--force`。 |
| `failed` | 解析、覆盖率或写入失败。 |

成功、试运行和解析后失败的条目包含完整的 inspect 报告字段。解析前就失败
的条目只包含 `file`、`status` 和 `error`。单文件报告是一个对象；批量报告
是 `{"schema_version": 1, "files": [...]}`。

## 退出码

| 退出码 | 含义 |
| ---: | --- |
| 0 | 成功（包括跳过文件）。 |
| 1 | 至少一个文件发生解析 / 写入 / 输入错误，或批量中混有非覆盖率失败。 |
| 2 | 所有失败文件都是覆盖率或校验失败。 |
| 3 | 规则或配置错误。 |

批量处理时，单个文件失败后仍会继续处理其余文件；最终退出码反映失败的
文件，而不包括被跳过的文件。
