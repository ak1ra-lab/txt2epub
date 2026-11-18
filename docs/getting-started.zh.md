# 入门指南

## 前置条件

- Python 3.11 或更高版本。
- 推荐使用 [uv](https://docs.astral.sh/uv/)；也可以使用 `pip` 进行可编辑
  安装。

发行包名为 `txt2epub-cli`，命令行为 `txt2epub`，导入包为 `txt2epub_cli`。
推荐在仓库根目录使用 `uv tool install .` 或虚拟环境安装；独立的导入包名可以
避免与 PyPI 上无关的 `txt2epub` 包冲突。

## 从源码安装

```bash
git clone git@github.com:ak1ra-lab/txt2epub.git
cd txt2epub

uv sync --group dev
uv run txt2epub --help
```

如果要把当前工作树安装到现有环境：

```bash
pip install -e .
txt2epub --help
```

也可以使用 `python -m txt2epub_cli ...` 运行。

## 检查文本

`inspect` 只解析源文件并输出报告，不写 EPUB：

```bash
uv run txt2epub inspect book.txt
uv run txt2epub inspect book.txt --json
uv run txt2epub inspect examples/**/*.txt --json > report.json
```

人类可读输出包含编码、行数和字符数、前言、标题统计、首尾标题、问题摘要、
覆盖率以及简短的可疑行列表。使用 `--verbose` 显示全部警告，或使用
`--limit 0` 隐藏列表。

## 转换

```bash
# 在源文件旁边生成 book.epub
uv run txt2epub convert book.txt

# 批量输出到目录
uv run txt2epub convert *.txt -o out/

# 只解析和报告，不写文件
uv run txt2epub convert book.txt --dry-run

# 为自动化流程写 JSON 报告
uv run txt2epub convert *.txt -o out/ --report out/report.json

# 非交互覆盖已有输出
uv run txt2epub convert *.txt -o out/ --yes
```

写入 XHTML 前，正文段落会去掉源文件中的前导和尾随空格及制表符。缩进由
EPUB 样式表控制，默认使用 `text-indent: 2em`。可以用 `--no-indent`、
`--indent-em` 或 `--css` 调整。

## Shell 补全

```bash
eval "$(register-python-argcomplete txt2epub)"
```

## 开发

```bash
uv sync --group dev
uv run pre-commit install

just lint
just typecheck
just test
just coverage
just build
just docs-build
```

提交到仓库的测试只使用合成的占位 fixture。`examples/txt/` 和
`examples/epub/` 下的本地样本已被 git 忽略：

```bash
TXT2EPUB_LOCAL_SAMPLES=1 uv run pytest -m local
```

## 退出码

| 退出码 | 含义 |
| ---: | --- |
| 0 | 成功 |
| 1 | 解析 / 写入 / 输入错误 |
| 2 | 覆盖率或校验失败 |
| 3 | 规则或配置错误 |

批量处理时，单个文件失败后会继续处理其余文件；最终退出码反映是否发生过
失败。
