def test_precommit_contains_formatters_and_local_hook():
    data = open(".pre-commit-config.yaml", "r", encoding="utf-8").read()
    assert "repo: https://github.com/psf/black" in data, "black 未在 pre-commit 配置中"
    assert (
        "repo: https://github.com/PyCQA/isort" in data
    ), "isort 未在 pre-commit 配置中"
    assert (
        "repo: https://github.com/charliermarsh/ruff-pre-commit" in data
    ), "ruff 未在 pre-commit 配置中"
    assert "fcatbot-precommit" in data, "本地 fcatbot-precommit 钩子缺失"
