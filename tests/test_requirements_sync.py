def test_requirements_sync_with_pyproject():
    req_lines = []
    with open("requirements.txt", "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            req_lines.append(line)

    # 从 pyproject.toml 中取出 dependencies 列表（简单文本解析，适用于常见格式）
    with open("pyproject.toml", "r", encoding="utf-8") as fh:
        data = fh.read()

    deps_block = ""
    start = data.find("dependencies = [")
    if start != -1:
        start = data.find("[", start)
        end = data.find("]", start)
        deps_block = data[start+1:end]

    py_deps = []
    for item in deps_block.splitlines():
        item = item.strip().rstrip(",")
        if not item:
            continue
        # 去掉引号
        item = item.strip(" '\"\n")
        py_deps.append(item)

    # 要求 requirements.txt 中的每一项都至少在 pyproject dependencies 中出现
    for req in req_lines:
        assert req in py_deps, f"{req} 不在 pyproject.toml 的 dependencies 中"