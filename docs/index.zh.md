# txt2epub

可审计的中文 TXT 转 EPUB 3 工具，生成多级目录，适用于 KOReader、Kindle
以及其他 EPUB 阅读器。

设计目标很简单：**绝不静默丢失正文**。每一行源文本都会在逐行台账
（line ledger）中记录处置结果；除非显式传入 `--allow-loss`，否则当源文本、
输出文本和丢弃文本的多重集不平衡时，转换会拒绝写出 EPUB。

!!! warning "AI 使用声明"

    本项目的大部分代码由 AI 编码代理生成。人类维护者通过自动化测试和真实书籍
    转换验证了功能行为，但尚未进行严格的逐行代码审核。在敏感环境中使用前，
    请自行审查源码。

## 特性

- 自动识别 UTF-8、UTF-8 BOM、UTF-16、GB18030 和 Big5，并兼容 CRLF 与 LF
  换行。
- 识别卷 / 章 / 节标题，以及 `序章`、`前传`、`番外`、`终章`、`后记`、
  `完本感言` 等特殊章节。
- 处理常见的复杂标题：`第一章活着`、`第0001章`、
  `第一卷 卷名 第1章 章名`、合章序号，以及带缩进的标题。
- 清理常见站点广告和水印，识别内嵌目录页；重复章号和序号缺口只报告，
  不改写原标题。
- 同时生成嵌套的 EPUB 3 `nav.xhtml` 和 EPUB 2 `toc.ncx`，新旧阅读器都能
  获得完整的多级目录。
- 支持单文件或批量转换；单个文件失败不会中断其余文件。已存在的输出默认
  跳过，只有使用 `--force` 才会覆盖。
- 可选精确或相似章节去重，并支持由 CSS 控制的首行缩进和自定义样式表。

## 安装

发行包已发布到 PyPI，包名为 `txt2epub-cli`：

```bash
uv tool install txt2epub-cli
```

命令行为 `txt2epub`。不安装、只运行一次时使用
`uvx --from txt2epub-cli txt2epub`。

## 快速开始

```bash
# 只检查，不写文件
txt2epub inspect book.txt

# 在源文件旁边生成 book.epub
txt2epub convert book.txt

# 批量输出到目录
txt2epub convert *.txt -o out/
```

## 文档

- [入门指南](getting-started.zh.md) - 安装、检查和转换。
- [命令行参考](cli.zh.md) - 全部选项、批量汇总和退出码。
- [规则与 TOML 配置](configuration.zh.md) - 规则预设，以及针对不同章节结构的
  示例。
- [工作原理](how-it-works.zh.md) - 覆盖率、重复处理、输出结构和已知限制。
- [开发](development.zh.md) - 测试、文档和发布流程。
