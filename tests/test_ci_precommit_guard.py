import subprocess

from cat import ci


def test_ci_skips_precommit_when_in_precommit(monkeypatch):
    # 跳过 pytest 执行
    monkeypatch.setenv("FCAT_SKIP_TESTS", "1")
    # 模拟 pre-commit 环境
    monkeypatch.setenv("PRE_COMMIT", "1")

    called = []

    def fake_call(args, *a, **k):
        called.append(args)
        return 0

    monkeypatch.setattr(subprocess, "call", fake_call)

    # 运行 ci.main 并断言不会尝试调用 pre-commit run (即没有一次调用 args[0]=='pre-commit')
    rv = ci.main()
    assert rv == 0
    assert not any(getattr(c, 0, None) == "pre-commit" for c in called)


def test_ci_runs_precommit_when_not_in_precommit(monkeypatch):
    monkeypatch.setenv("FCAT_SKIP_TESTS", "1")
    monkeypatch.delenv("PRE_COMMIT", raising=False)

    calls = []

    def fake_call(args, *a, **k):
        calls.append(args)
        return 0

    monkeypatch.setattr(subprocess, "call", fake_call)

    rv = ci.main()
    assert rv == 0
    assert any(c and c[0] == "pre-commit" for c in calls)
