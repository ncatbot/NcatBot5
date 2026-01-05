from . import SDKError


class ParseError(SDKError):
    def __init__(
        self, protocol_name: str, parse_type: str, data: object, e: Exception = None
    ):
        import json
        import time
        from pathlib import Path

        info = {
            "time": time.time(),
            "protocol": protocol_name,
            "type": parse_type,
            "data": data,
            "error": str(e) if e else None,
        }
        Path(f"./{protocol_name}_error_parse.json").write_text(
            json.dumps(info, ensure_ascii=False, indent=4), newline="\n"
        )
        super().__init__(f"协议 {protocol_name} 解析 {parse_type} 时出错: {e}")
