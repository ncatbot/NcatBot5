import inspect
import json
from functools import wraps


def extract_google_style_doc(func):
    """
    装饰器，用于提取函数的谷歌风格注释信息
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    # 获取函数的文档字符串
    doc = inspect.getdoc(func)
    if not doc:
        return wrapper

    # 获取函数的签名信息
    signature = inspect.signature(func)
    parameters = signature.parameters

    # 解析文档字符串
    doc_lines = doc.split("\n")
    doc_info = {
        "name": func.__name__,
        "args": [],
        "doc": "",
        "params": {},
        "returns": "",
        "raises": {},
        "annotations": {},
    }

    # 提取函数描述
    doc_info["doc"] = doc_lines[0].strip()

    # 定义状态标志
    in_args = False
    in_returns = False
    in_raises = False

    # 遍历文档字符串的每一行
    for line in doc_lines[1:]:
        line = line.strip()
        if line.startswith("Args:"):
            in_args = True
            in_returns = False
            in_raises = False
            continue
        elif line.startswith("Returns:"):
            in_args = False
            in_returns = True
            in_raises = False
            continue
        elif line.startswith("Raises:"):
            in_args = False
            in_returns = False
            in_raises = True
            continue

        # 提取参数信息
        if in_args and line:
            param_name = line.split(":")[0].strip()
            param_desc = line.split(":")[1].strip() if ":" in line else ""
            doc_info["args"].append(param_name)
            doc_info["params"][param_name] = param_desc
        # 提取返回值信息
        elif in_returns and line:
            doc_info["returns"] = line.strip()
        # 提取异常信息
        elif in_raises and line:
            exception_name = line.split(":")[0].strip()
            exception_desc = line.split(":")[1].strip() if ":" in line else ""
            doc_info["raises"][exception_name] = exception_desc

    # 提取参数的类型注释
    for param_name, param in parameters.items():
        if param.annotation != param.empty:
            doc_info["annotations"][param_name] = str(param.annotation)

    # 将解析结果作为函数的属性
    wrapper.doc_info = doc_info

    return wrapper


# 示例使用
@extract_google_style_doc
def re(self, path: str) -> str:
    """
    解析正则表达式

    Args:
        path: 正则表达式

    Returns:
        解析结果

    Raises:
        ValueError: 路径无效

    """
    pass


# {'name': 're', 'args': ['path'], 'doc': '解析正则表达式', 'params': {'path': '正则表达式'}, 'returns': '解析结果', 'raises': {'ValueError': '路径无效'}, 'annotations': {'path': "<class 'str'>"}}
# 测试提取结果
print(json.dumps(re.doc_info, indent=4, ensure_ascii=False))
