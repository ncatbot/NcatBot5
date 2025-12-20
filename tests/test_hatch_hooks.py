import subprocess

import pytest

from cat import hatch_hooks


def test_read_meta_and_license(tmp_path, monkeypatch, caplog):
    # setup temp repo structure
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    (repo / "License.txt").write_text("Copyright (c) 2020 Fish-LP\n")
    (src / "meta.py").write_text(
        "__version__ = '1.2.3'\n__copyright__ = \"Copyright (c) 2020 Fish-LP\"\n"
    )

    monkeypatch.setattr(hatch_hooks, "ROOT", repo)
    monkeypatch.setattr(hatch_hooks, "LICENSE", repo / "License.txt")
    monkeypatch.setattr(hatch_hooks, "META", src / "meta.py")
    monkeypatch.setenv("HC_DRY_RUN", "1")

    # no git tags -> should warn and not raise
    monkeypatch.setattr(
        subprocess,
        "check_output",
        lambda *a, **k: (_ for _ in ()).throw(Exception("no git")),
    )

    hatch_hooks.pre_build()
    assert "未找到 git" in caplog.text or "跳过版本差异" in caplog.text


def test_version_equal_to_tag_fails(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    src = repo / "src"
    src.mkdir(parents=True)
    (repo / "License.txt").write_text("Copyright (c) 2020 Fish-LP\n")
    (src / "meta.py").write_text(
        "__version__ = '1.2.3'\n__copyright__ = \"Copyright (c) 2020 Fish-LP\"\n"
    )

    monkeypatch.setattr(hatch_hooks, "ROOT", repo)
    monkeypatch.setattr(hatch_hooks, "LICENSE", repo / "License.txt")
    monkeypatch.setattr(hatch_hooks, "META", src / "meta.py")

    monkeypatch.setenv("HC_DRY_RUN", "1")

    # git returns the same tag
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: b"1.2.3")

    with pytest.raises(SystemExit):
        hatch_hooks.pre_build()
