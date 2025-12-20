import subprocess
import sys
import os


def test_ci_wrapper_runs_ok(tmp_path, monkeypatch):
    # 确保在干运行环境下调用不会修改文件且返回 0
    monkeypatch.setenv("HC_DRY_RUN", "1")
    monkeypatch.setenv("FCAT_SKIP_TESTS", "1")

    # 使用 PYTHONPATH 指向 repo
    rv = subprocess.call([sys.executable, "-m", "cat.ci"], env={**os.environ, "PYTHONPATH": "."})
    assert rv == 0


def test_precommit_runs_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("HC_DRY_RUN", "1")
    monkeypatch.setenv("FCAT_SKIP_TESTS", "1")
    rv = subprocess.call([sys.executable, "-m", "cat.precommit"], env={**os.environ, "PYTHONPATH": "."})
    assert rv == 0
