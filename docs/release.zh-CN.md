# 发布流程

> 🌐 Languages: [English](release.md) | **中文**

切 `toxi` 引擎 release 的维护者参考。引擎版本锁在 4 个 surface 上
（见 PRD §4.13）；GitHub Action 在它们不一致时会拒绝发布。

## 0. 前置条件

- PyPI **trusted publisher** 已经为 `toxi` 项目配置完成，scope 为
  本 repo + `pypi` GitHub Environment。**仓库里没有 API token**——
  只走 OIDC。
- 在 GitHub remote 上对 `main` 和 tag 有 push 权限。
- 工作树干净（`git status` 空）。

## 1. Bump 4 个版本 surface

锁定的 surface（PRD §4.13）：

```
pyproject.toml                                       [project] version = "X.Y.Z"
src/toxi/__init__.py                                 __version__ = "X.Y.Z"
claude-code-plugin/.claude-plugin/plugin.json        "version": "X.Y.Z"
plugins/toxi/.codex-plugin/plugin.json               "version": "X.Y.Z"
```

验证锁：

```bash
.venv/bin/python -m pytest tests/test_versions.py -v
```

继续前修掉任何不一致——`test_versions.py` 跑的就是 release
workflow 里那同一份校验。

## 2. Commit bump

```bash
git add pyproject.toml src/toxi/__init__.py \
        claude-code-plugin/.claude-plugin/plugin.json \
        plugins/toxi/.codex-plugin/plugin.json
git commit -m "chore(release): bump version to X.Y.Z"
```

每次 bump 一个 commit——不要和 feature 工作捆在一起。

## 3. 打 annotated tag

```bash
git tag -a vX.Y.Z -m "vX.Y.Z —— <一行摘要>

<简短 release notes：
- key change 1
- key change 2
- ...>"
```

Tag 名 **必须** 和 `pyproject.toml` 版本一致，前缀 `v`。

## 4. Push

```bash
git push origin main
git push origin vX.Y.Z
```

`vX.Y.Z` 的 push 会触发 `.github/workflows/publish.yml`。

## 5. Workflow 行为

`publish.yml` 在 `push` 一个匹配 `v*` 的 tag 时运行：

1. **校验 tag 与 pyproject 一致**——去掉前缀 `v` 后比对
   `pyproject.toml` 的 `[project] version`。不一致直接报错退出。
2. **Build**——`python -m build` 生成 sdist + wheel 到 `dist/`。
3. **上传 artifact**——把 `dist/` 存给 publish job。
4. **发到 PyPI**——用 `pypa/gh-action-pypi-publish@release/v1`，
   走 `pypi` GitHub Environment + OIDC trusted publisher。

如果第 1 步失败，workflow 会在构建之前就停下。重新 bump + retag
（用 `git tag -d vX.Y.Z && git push --delete origin vX.Y.Z` 删掉错的
tag，然后从第 3 步重做）。

## 6. PyPI 上验证

```bash
pip index versions toxi
pipx install "toxi[mcp]==X.Y.Z"   # 确认新版本可安装
```

Claude Code plugin 和 Codex plugin 各自的 manifest 都钉死了同一个
版本号；不需要单独的 plugin 发布步骤。

## 7. 发布后

- 如果这次发布对应一个 milestone（比如 v0.3 标记 cc-chat 吸收 +
  Codex plugin 集成），更新项目 README 顶部的 status 行。
- 在 PRD §5.1 step log 加一条 bullet。
- 如果这次发布包含 wire-format / envelope 变化，follow up 一个
  ToxiOS 工作项配套（见 `docs/WORKFLOWS.md` 跨 repo 表）。

## 反例

- **不要 `--amend` 一个已发布 tag 的 commit。** 已发布的 wheel 在
  metadata 里引用那个 commit SHA；重写它会让 wheel 失去引用。
- **不要 bump 部分 surface 然后 "晚点再发"。** `test_versions.py`
  强制的就是 4-surface lock；部分 bump 在下次 push 时同样会 fail
  CI。
- **不要手工上传 wheel。** GitHub Action 的 OIDC trusted publisher
  是唯一被授权的发布路径；手工 `twine upload` 会被 PyPI 拒（没有
  注册 API token）。
