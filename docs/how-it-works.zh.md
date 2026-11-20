# 工作原理

## 逐行台账与覆盖率

每条物理源文本行都会获得一个处置结果：前言、标题、正文、噪声、重复、
内嵌目录页或空行。解析完成后会校验源文本、输出文本和有意丢弃文本的多重集
是否平衡。

`inspect` 和 `convert` 都会报告：

```text
Coverage:   100.00% (source 1,234,567 / output 1,234,567 / dropped 0)
```

- `source` 统计每个非空源文本行中的规范化文本单元。
- `output` 统计标题、前言和正文段落。
- `dropped` 统计有意删除的噪声、重复标题和内嵌目录页，因此总数仍然平衡。
- 如果多重集不平衡，`convert` 会以退出码 `2` 结束，并且不写文件。只有在
  明确理解原因时才使用 `--allow-loss`。

`--keep-noise` 会把站点广告保留为正文。`--keep-toc` 会把内嵌目录页保留为
前言，而不是删除。

## 噪声与内嵌目录页

常见站点广告、水印和短噪声行会被删除并记录在逐行台账中。内嵌目录页默认
会被识别并删除。这些内容不会静默消失：报告中会同时出现在丢弃文本统计和
问题列表里。

## 重复章号与可选去重

默认情况下，重复章号只**报告，不重编号**。如果两个标题章号相同、标题也
相同，后一个标题会合并到第一次出现的位置，正文保留。章号相同但标题不同
时报告为 `number_conflict`，两章都会保留。

仅仅重复已有顶格章节的缩进标题（例如带站点后缀的重复标题）会记录为
`duplicate_indented`，严重级别为 `info`，不会淹没警告列表。

可选的内容去重：

```bash
txt2epub convert book.txt --dedupe exact    # 标题 + 正文哈希完全相同
txt2epub convert book.txt --dedupe similar  # 正文近似相同（>= 0.9）
```

两种模式默认都关闭。

## 输出结构

```text
mimetype
META-INF/container.xml
OEBPS/content.opf
OEBPS/nav.xhtml
OEBPS/toc.ncx
OEBPS/style.css
OEBPS/text/front-matter.xhtml
OEBPS/text/part-0001.xhtml
OEBPS/text/chapter-0001.xhtml
...
```

卷和特殊章节的父节点始终会生成真实的 XHTML 页面，因此每个 nav/NCX 条目
都有有效链接。超过 `--split-size`（默认 256 KiB）的章节会按段落边界拆分；
只有第一个片段会出现在目录中。

## 已知限制

- 一行源文本仍然对应一个段落；转换器不会重排或重新分段。
- 不生成封面图。未来可以提供传入外部封面的选项。
- 不做 AI 改写，也不自动生成章节标题。
- Big5 检测是尽力而为；简体中文样本大多使用 GB18030，因此会优先尝试。
- 不支持 MOBI/AZW3 输出，没有 GUI，也没有 KOReader 插件。
- 只支持无 DRM 的输入文件。
