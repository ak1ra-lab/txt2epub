# 开发

## 环境准备

```bash
uv sync --group dev
uv run pre-commit install
```

仓库使用 `just` 作为 `uv run` 的便捷封装。代理和脚本也可以直接调用
`uv run ...`，两种方式等价。

```bash
just lint        # ruff check --fix + ruff format
just typecheck   # ty check src/
just test        # pytest -v tests/
just coverage    # 带覆盖率的 pytest
just build       # uv build
just docs-build  # mkdocs build
just docs-serve  # 本地预览文档
```

提交前运行完整的 pre-commit 检查：

```bash
uv run pre-commit run --all-files
```

## 测试与 fixture

提交到仓库的测试只使用合成的占位 fixture，禁止提交真实书籍正文。
`tests/golden/samples.json` 是 fixture 的计数和首尾标题快照；只有 fixture
行为有意改变时才更新它。

`examples/txt/` 和 `examples/epub/` 下的本地样本已被 git 忽略。运行可选的
冒烟测试：

```bash
TXT2EPUB_LOCAL_SAMPLES=1 uv run pytest -m local
```

## 文档

文档站由 mkdocs 和 i18n 插件构建，使用后缀式文件：

- `docs/page.md` 是英文。
- `docs/page.zh.md` 是简体中文。

用户可见行为发生变化时，两种语言的页面都要更新。文档构建产物由 docs
workflow 部署到 GitHub Pages。

## 版本与发布

版本由 `hatch-vcs` 从 Git 标签生成；`fallback_version` 为 `0.1.0`。不要手动
修改版本字符串，也不要添加 `__version__` 常量。
`src/txt2epub_cli/__init__.py` 读取已安装包的元数据。

推送 `v*` 标签会触发 PyPI 发布流程。只有确实要发布时才这样做。
`CHANGELOG.md` 遵循 Keep a Changelog 和语义化版本。

## 模板

项目由 [`copier-pyproject`](https://github.com/ak1ra-lab/copier-pyproject)
生成。`.copier-answers.yml` 记录模板版本以及发行包名、命令名和导入包名。
执行 `copier update` 前先用 `--pretend` 验证。
