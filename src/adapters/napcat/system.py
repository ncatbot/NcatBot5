from typing import Any, Union, List, Dict, Optional
from .api_base import NCAPIBase


class NCAPISystem(NCAPIBase):
    '''系统接口'''
    
    def get_client_key(
            self,
            ) -> Any:
        """获取 client_key
        Returns:
            API响应数据
        """
        return (
            "get_clientkey", 
            {},
        )

    async def get_robot_uin_range(
        self,
    ) -> Any:
        """获取机器人 QQ 号范围
        Returns:
            API响应数据
        """
        return (
            "get_robot_uin_range", 
            {},
        )

    async def ocr_image(
        self, 
        image: str,
    ) -> Any:
        """OCR 图片识别
        Args:
            image: 图片路径,支持本地路径和网络路径
        Returns:
            API响应数据
        """
        return (
            "ocr_image", 
            {
                "image": image,
            },
        )

    async def ocr_image_new(
        self, 
        image: str,
    ) -> Any:
        """OCR 图片识别(新版)
        Args:
            image: 图片路径,支持本地路径和网络路径
        Returns:
            API响应数据
        """
        return (
            ".ocr_image", 
            {
                "image": image,
            },
        )

    async def translate_en2zh(
        self, 
        words: List[str],
    ) -> Any:
        """英文翻译为中文
        Args:
            words: 待翻译的单词列表
        Returns:
            API响应数据
        """
        return (
            "translate_en2zh", 
            {
                "words": words,
            },
        )

    async def get_login_info(
        self,
    ) -> Any:
        """获取登录信息
        Returns:
            API响应数据
        """
        return (
            "get_login_info", 
            {},
        )

    async def set_input_status(
        self, 
        event_type: int, 
        user_id: Union[int, str],
    ) -> Any:
        """设置输入状态
        Args:
            event_type: 状态类型
            user_id: QQ 号
        Returns:
            API响应数据
        """
        return (
            "set_input_status", 
            {
                "eventType": event_type, 
                "user_id": user_id,
            },
        )

    async def download_file(
        self,
        thread_count: int,
        headers: Union[Dict, str],
        base64: Optional[str] = None,
        url: Optional[str] = None,
        name: Optional[str] = None,
    ) -> Any:
        """下载文件
        Args:
            thread_count: 下载线程数
            headers: 请求头
            base64: base64 编码的图片,二选一
            url: 图片 URL,二选一
            name: 文件名（可选）
        Returns:
            API响应数据
        """
        params = {
            "thread_count": thread_count,
            "headers": headers,
        }
        if base64:
            params["base64"] = base64
            if name:
                params["name"] = name
        elif url:
            params["url"] = url
            if name:
                params["name"] = name
        return (
            "download_file", 
            params,
        )

    async def get_cookies(
        self, 
        domain: str,
    ) -> Any:
        """获取 cookies
        Args:
            domain: 域名
        Returns:
            API响应数据
        """
        return (
            "get_cookies", 
            {
                "domain": domain,
            },
        )

    async def handle_quick_operation(
        self, 
        context: Dict, 
        operation: Dict,
    ) -> Any:
        """对事件执行快速操作
        Args:
            context: 事件数据对象
            operation: 快速操作对象
        Returns:
            API响应数据
        """
        return (
            ".handle_quick_operation", 
            {
                "context": context, 
                "operation": operation,
            },
        )

    async def get_csrf_token(
        self,
    ) -> Any:
        """获取 CSRF Token
        Returns:
            API响应数据
        """
        return (
            "get_csrf_token", 
            {},
        )

    async def get_credentials(
        self, 
        domain: str,
    ) -> Any:
        """获取 QQ 相关接口凭证
        Args:
            domain: 域名
        Returns:
            API响应数据
        """
        return (
            "get_credentials", 
            {
                "domain": domain,
            },
        )

    async def get_model_show(
        self, 
        model: str,
    ) -> Any:
        """获取模型显示
        Args:
            model: 模型名
        Returns:
            API响应数据
        """
        return (
            "_get_model_show", 
            {
                "model": model,
            },
        )

    async def can_send_image(
        self,
    ) -> Any:
        """检查是否可以发送图片
        Returns:
            API响应数据
        """
        return (
            "can_send_image", 
            {},
        )

    async def nc_get_packet_status(
        self,
    ) -> Any:
        """获取 packet 状态
        Returns:
            API响应数据
        """
        return (
            "nc_get_packet_status", 
            {},
        )

    async def can_send_record(
        self,
    ) -> Any:
        """检查是否可以发送语音
        Returns:
            API响应数据
        """
        return (
            "can_send_record", 
            {},
        )

    async def get_status(
        self,
    ) -> Any:
        """获取状态
        Returns:
            API响应数据
        """
        return (
            "get_status", 
            {},
        )

    async def nc_get_rkey(
        self,
    ) -> Any:
        """获取 rkey
        Returns:
            API响应数据
        """
        return (
            "nc_get_rkey", 
            {},
        )

    async def get_version_info(
        self,
    ) -> Any:
        """获取版本信息
        Returns:
            API响应数据
        """
        return (
            "get_version_info", 
            {},
        )
    
    async def mark_all_as_read(
        self,
    ) -> Any:
        """设置所有消息已读
        Returns:
            API响应数据
        """
        return (
            "_mark_all_as_read", 
            {},
        )
    
    async def get_recent_contact(
        self, 
        count: int,
    ) -> Any:
        """最近消息列表
        
        获取的最新消息是每个会话最新的消息
        
        Args:
            count: 会话数量
        Returns:
            API响应数据
        """
        return (
            "get_recent_contact", 
            {
                "count": count,
            },
        )



