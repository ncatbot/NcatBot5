import textwrap

from cat import hatch_hooks, precommit


def test_sync_requirements_auto_fix(tmp_path, monkeypatch):
    # 初始化临时仓库结构
    repo = tmp_path
    (repo / "requirements.txt").write_text("foo>=1.0\nbar==2.0\n")
    pyproject = textwrap.dedent(
        """
        [project]
        name = "example"
        dependencies = [
            "foo>=1.0",
        ]
        """
    )
    (repo / "pyproject.toml").write_text(pyproject)

    monkeypatch.chdir(repo)

    # 调用自动修复
    changed = precommit._sync_requirements_to_pyproject(auto_fix=True)
    assert changed is True

    data = (repo / "pyproject.toml").read_text()
    assert '"bar==2.0"' in data


def test_bump_dev_version_in_meta(tmp_path, monkeypatch):
    repo = tmp_path
    src = repo / "src"
    src.mkdir()
    meta = src / "meta.py"
    meta.write_text("__version__ = '1.2.3'\n")

    # monkeypatch hatch_hooks.META to point to our temp file
    monkeypatch.setattr(hatch_hooks, "META", meta)

    # bump once
    ok = precommit._bump_dev_version_in_meta()
    assert ok is True
    text = meta.read_text()
    assert '__version__ = "1.2.3-dev.0"' in text

    # bump again (dev increment)
    ok = precommit._bump_dev_version_in_meta()
    assert ok is True
    text = meta.read_text()
    assert '__version__ = "1.2.3-dev.1"' in text


def test_precommit_auto_bump_on_version_equal_tag(tmp_path, monkeypatch):
    repo = tmp_path
    src = repo / "src"
    src.mkdir()
    meta = src / "meta.py"
    meta.write_text(
        "__version__ = '1.2.3'\n__copyright__ = \"Copyright (c) 2024 Fish-LP\"\n"
    )

    monkeypatch.setattr(hatch_hooks, "META", meta)
    # simulate git tag being 1.2.3
    monkeypatch.setattr(hatch_hooks, "_get_latest_git_tag", lambda: "1.2.3")

    # ensure requirements and pyproject exist for sync step
    (repo / "requirements.txt").write_text("foo>=1.0\n")
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "example"\ndependencies = [\n    "foo>=1.0",\n]\n'
    )

    monkeypatch.chdir(repo)

    # run main (skip tests)
    monkeypatch.setenv("FCAT_SKIP_TESTS", "1")
    rv = precommit.main()
    assert rv == 0
    text = meta.read_text()
    assert "-dev." in text
