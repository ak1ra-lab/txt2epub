# 入门指南

## 前置条件

- Python 3.11 或更高版本。
- [uv](https://docs.astral.sh/uv/)。

PyPI 发行包名为 `txt2epub-cli`，命令行为 `txt2epub`。

## 从 PyPI 安装

```bash
# 推荐：安装为独立 CLI 工具
uv tool install txt2epub-cli

# 不安装，直接运行一次
uvx --from txt2epub-cli txt2epub --help
```

## 从源码 checkout 运行

```bash
git clone https://github.com/ak1ra-lab/txt2epub.git
cd txt2epub

uv sync
uv run txt2epub --help
```

开发时安装开发依赖组，并在同一个 checkout 中运行质量检查：

```bash
uv sync --group dev
uv run pre-commit install
```

## 检查文本

`inspect` 只解析源文件并输出报告，不写 EPUB：

```bash
txt2epub inspect book.txt
txt2epub inspect book.txt --json
txt2epub inspect examples/**/*.txt --json > report.json
```

人类可读输出包含编码、行数和字符数、前言、标题统计、首尾标题、问题摘要、
覆盖率以及简短的可疑行列表。使用 `--verbose` 显示全部警告，或使用
`--limit 0` 隐藏列表。

## 转换

```bash
# 在源文件旁边生成 book.epub
txt2epub convert book.txt

# 批量输出到目录
txt2epub convert *.txt -o out/

# 只解析和报告，不写文件
txt2epub convert book.txt --dry-run

# 为自动化流程写 JSON 报告
txt2epub convert *.txt -o out/ --report out/report.json

# 覆盖已有输出
txt2epub convert *.txt -o out/ --force
```

如果目标文件已存在，`convert` 会直接跳过，不会询问。需要覆盖时传入
`--force`。全部任务结束后会汇总成功、失败和跳过的数量：

```text
Summary: 3 succeeded, 1 failed, 2 skipped
```

写入 XHTML 前，正文段落会去掉源文件中的前导和尾随空格及制表符。缩进由
EPUB 样式表控制，默认使用 `text-indent: 2em`。可以用 `--no-indent`、
`--indent-em` 或 `--css` 调整。

## Shell 补全

```bash
eval "$(register-python-argcomplete txt2epub)"
```

## 下一步

- [命令行参考](cli.zh.md) - 全部选项、报告字段和退出码。
- [规则与 TOML 配置](configuration.zh.md) - 针对源文件调整章节识别规则。
- [工作原理](how-it-works.zh.md) - 覆盖率、重复处理、输出结构和已知限制。
