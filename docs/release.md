# Release flow

> 🌐 Languages: **English** | [中文](release.zh-CN.md)

Maintainer reference for cutting a `toxi` engine release. Engine version
is locked across 4 surfaces (see PRD §4.13); the GitHub Action will
refuse to publish if they drift.

## 0. Prerequisites

- PyPI **trusted publisher** is configured for the `toxi` project,
  scoped to this repo + the `pypi` GitHub Environment. No API token in
  the repo — OIDC only.
- Push permission to `main` + tags on the GitHub remote.
- A clean working tree (`git status` empty).

## 1. Bump the 4 version surfaces

The locked surfaces (PRD §4.13):

```
pyproject.toml                                       [project] version = "X.Y.Z"
src/toxi/__init__.py                                 __version__ = "X.Y.Z"
claude-code-plugin/.claude-plugin/plugin.json        "version": "X.Y.Z"
plugins/toxi/.codex-plugin/plugin.json               "version": "X.Y.Z"
```

Verify the lock:

```bash
.venv/bin/python -m pytest tests/test_versions.py -v
```

Fix any mismatch before continuing — `test_versions.py` is the same
check the release workflow runs.

## 2. Commit the bump

```bash
git add pyproject.toml src/toxi/__init__.py \
        claude-code-plugin/.claude-plugin/plugin.json \
        plugins/toxi/.codex-plugin/plugin.json
git commit -m "chore(release): bump version to X.Y.Z"
```

One commit per bump — don't bundle the bump with feature work.

## 3. Create an annotated tag

```bash
git tag -a vX.Y.Z -m "vX.Y.Z — <one-line summary>

<short release notes:
- key change 1
- key change 2
- ...>"
```

Tag name **must** match `pyproject.toml` version with a leading `v`.

## 4. Push

```bash
git push origin main
git push origin vX.Y.Z
```

The push of `vX.Y.Z` triggers `.github/workflows/publish.yml`.

## 5. Workflow behavior

`publish.yml` (on `push` of tag matching `v*`):

1. **Verify tag matches pyproject** — strips the leading `v` and compares
   to `pyproject.toml`'s `[project] version`. Exits with a clear error
   if they differ.
2. **Build** — `python -m build` produces sdist + wheel under `dist/`.
3. **Upload artifact** — stores `dist/` for the publish job.
4. **Publish to PyPI** — uses `pypa/gh-action-pypi-publish@release/v1`
   with the `pypi` GitHub Environment + OIDC trusted publisher.

If step 1 fails, the workflow stops before building. Re-bump and retag
(use `git tag -d vX.Y.Z && git push --delete origin vX.Y.Z` to remove a
mistaken tag, then start over from step 3).

## 6. Verify on PyPI

```bash
pip index versions toxi
pipx install "toxi[mcp]==X.Y.Z"   # confirm the new release is installable
```

The Claude Code plugin and Codex plugin both pin to the same version
through their manifest; no separate release step is needed.

## 7. Post-release

- Update the project README's status line if the version is a milestone
  (e.g. v0.3 marks the cc-chat absorption + Codex plugin integration).
- Update the PRD §5.1 step log with a new bullet.
- If the release introduced wire-format / envelope changes, follow up
  with a ToxiOS work-item to match (see `docs/WORKFLOWS.md` cross-repo
  table).

## Anti-patterns

- **Don't `--amend` a published tag's commit.** The published wheel
  references that commit SHA in metadata; rewriting it strands the
  wheel.
- **Don't bump partial surfaces and "release later".** The 4-surface
  lock is what `test_versions.py` enforces; partial bumps will fail CI
  on the next push too.
- **Don't manually upload wheels.** The GitHub Action's OIDC trusted
  publisher is the only authorized publishing path; manual `twine
  upload` will be rejected by PyPI (no API token registered).
