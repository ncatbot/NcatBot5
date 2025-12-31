from typing import Any, Union

from .api_base import NCAPIBase


class NCAPIMessage(NCAPIBase):
    """napcatAPI消息类"""

    abc = False

    async def delete_msg(
        self,
        message_id: Union[int, str],
    ) -> Any:
        """删除消息
        Args:
            message_id: 消息ID
        Returns:
            API响应数据
        """
        return (
            "delete_msg",
            {
                "message_id": message_id,
            },
        )

    async def get_msg(
        self,
        message_id: Union[int, str],
    ) -> Any:
        """获取消息
        Args:
            message_id: 消息ID
        Returns:
            API响应数据
        """
        return (
            "get_msg",
            {
                "message_id": message_id,
            },
        )

    async def get_image(
        self,
        image_id: str,
    ) -> Any:
        """获取图片消息详情
        Args:
            image_id: 图片ID
        Returns:
            API响应数据
        """
        return (
            "get_image",
            {
                "file_id": image_id,
            },
        )

    async def get_record(
        self,
        record_id: str,
        output_type: str = "mp3",
    ) -> Any:
        """获取语音消息详情
        Args:
            record_id: 语音ID
            output_type: 输出类型,枚举值: mp3, amr, wma, m4a, spx, ogg, wav, flac,默认为mp3
        Returns:
            API响应数据
        """
        return (
            "get_record",
            {
                "file_id": record_id,
                "out_format": output_type,
            },
        )

    async def get_file(
        self,
        file_id: str,
    ) -> Any:
        """获取文件消息详情
        Args:
            file_id: 文件ID
        Returns:
            API响应数据
        """
        return (
            "get_file",
            {
                "file_id": file_id,
            },
        )

    async def set_msg_emoji_like(
        self,
        message_id: Union[int, str],
        emoji_id: str,
        emoji_set: bool,
    ) -> Any:
        """设置消息表情点赞
        Args:
            message_id: 消息ID
            emoji_id: 表情ID
            emoji_set: 设置
        Returns:
            API响应数据
        """
        return (
            "set_msg_emoji_like",
            {
                "message_id": message_id,
                "emoji_id": emoji_id,
                "set": emoji_set,
            },
        )

    async def fetch_emoji_like(
        self,
        message_id: Union[int, str],
        emoji_id: str,
        emoji_type: str,
        group_id: Union[int, str] = None,
        user_id: Union[int, str] = None,
        count: int = None,
    ) -> Any:
        """获取贴表情详情
        Args:
            message_id: 消息ID
            emoji_id: 表情ID
            emoji_type: 表情类型
            group_id: 群号, 二选一
            user_id: QQ号, 二选一
            count: 数量, 可选
        Returns:
            API响应数据
        """
        params = {
            "message_id": message_id,
            "emojiId": emoji_id,
            "emojiType": emoji_type,
        }
        if group_id:
            params["group_id"] = group_id
        elif user_id:
            params["user_id"] = user_id
        if count:
            params["count"] = count
        return (
            "fetch_emoji_like",
            params,
        )

    async def get_forward_msg(
        self,
        message_id: str,
    ) -> Any:
        """获取合并转发消息
        Args:
            message_id: 消息ID
        Returns:
            API响应数据
        """
        return (
            "get_forward_msg",
            {
                "message_id": message_id,
            },
        )

    async def send_poke(
        self,
        user_id: Union[int, str],
        group_id: Union[int, str] = None,
    ) -> Any:
        """发送戳一戳
        Args:
            user_id: QQ号
            group_id: 群号, 可选,不填则为私聊
        Returns:
            API响应数据
        """
        params = {"user_id": user_id}
        if group_id:
            params["group_id"] = group_id
        return (
            "send_poke",
            params,
        )

    async def forward_friend_single_msg(
        self,
        message_id: str,
        user_id: Union[int, str],
    ) -> Any:
        """转发消息给好友
        Args:
            message_id: 消息ID
            user_id: 发送对象QQ号
        Returns:
            API响应数据
        """
        return (
            "forward_friend_single_msg",
            {
                "user_id": user_id,
                "message_id": message_id,
            },
        )

    async def send_private_forward_msg(
        self,
        user_id: Union[int, str],
        messages: dict,
    ) -> Any:
        """合并转发消息给好友
        Args:
            user_id: 发送对象QQ号
            messages: 消息列表
        Returns:
            API响应数据
        """
        if len(messages) == 0:
            return None

        return (
            "send_private_forward_msg",
            {
                "messages": messages,
                "user_id": user_id,
            },
        )
