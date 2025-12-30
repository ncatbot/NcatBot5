from typing import Any, List, Union

from .message import NCAPIMessage


class NCAPIUser(NCAPIMessage):
    """napcatAPI用户类"""

    async def send_private_msg(
        self,
        user_id: Union[str, int],
        message: List[dict],
    ) -> Any:
        """发送私聊消息(顶级接口，应当继续使用消息段封装)
        Args:
            user_id: 目标用户ID
            message: 消息段列表
        Returns:
            API响应数据
        """
        return (
            "send_private_msg",
            {
                "user_id": user_id,
                "message": message,
            },
        )

    async def set_qq_profile(
        self,
        nickname: str,
        personal_note: str,
        sex: str,
    ) -> Any:
        """设置账号信息
        Args:
            nickname: 昵称
            personal_note: 个性签名
            sex: 性别
        Returns:
            API响应数据
        """
        return (
            "set_qq_profile",
            {
                "nickname": nickname,
                "personal_note": personal_note,
                "sex": sex,
            },
        )

    async def get_user_card(
        self,
        user_id: str,
        phone_number: str,
    ) -> Any:
        """获取用户名片
        Args:
            user_id: QQ号
            phone_number: 手机号
        Returns:
            API响应数据
        """
        return (
            "ArkSharePeer",
            {
                "user_id": user_id,
                "phoneNumber": phone_number,
            },
        )

    async def get_group_card(
        self,
        group_id: str,
        phone_number: str,
    ) -> Any:
        """获取群名片
        Args:
            group_id: 群号
            phone_number: 手机号
        Returns:
            API响应数据
        """
        return (
            "ArkSharePeer",
            {
                "group_id": group_id,
                "phoneNumber": phone_number,
            },
        )

    async def get_share_group_card(
        self,
        group_id: str,
    ) -> Any:
        """获取群共享名片
        Args:
            group_id: 群号
        Returns:
            API响应数据
        """
        return (
            "ArkShareGroup",
            {
                "group_id": group_id,
            },
        )

    async def set_online_status(
        self,
        status: str,
    ) -> Any:
        """设置在线状态
        Args:
            status: 在线状态
        Returns:
            API响应数据
        """
        return (
            "set_online_status",
            {
                "status": status,
            },
        )

    async def get_friends_with_category(
        self,
    ) -> Any:
        """获取好友列表
        Returns:
            API响应数据
        """
        return (
            "get_friends_with_category",
            {},
        )

    async def set_qq_avatar(
        self,
        avatar: str,
    ) -> Any:
        """设置头像
        Args:
            avatar: 头像路径,支持本地路径和网络路径
        Returns:
            API响应数据
        """
        return (
            "set_qq_avatar",
            {
                "file": avatar,
            },
        )

    async def send_like(
        self,
        user_id: str,
        times: int,
    ) -> Any:
        """发送赞
        Args:
            user_id: QQ号
            times: 次数
        Returns:
            API响应数据
        """
        return (
            "send_like",
            {
                "user_id": user_id,
                "times": times,
            },
        )

    async def create_collection(
        self,
        rawdata: str,
        brief: str,
    ) -> Any:
        """创建收藏
        Args:
            rawdata: 内容
            brief: 标题
        Returns:
            API响应数据
        """
        return (
            "create_collection",
            {
                "rawData": rawdata,
                "brief": brief,
            },
        )

    async def set_friend_add_request(
        self,
        flag: str,
        approve: bool,
        remark: str,
    ) -> Any:
        """设置好友请求
        Args:
            flag: 请求ID
            approve: 是否同意
            remark: 备注
        Returns:
            API响应数据
        """
        return (
            "set_friend_add_request",
            {
                "flag": flag,
                "approve": approve,
                "remark": remark,
            },
        )

    async def set_self_long_nick(
        self,
        longnick: str,
    ) -> Any:
        """设置个性签名
        Args:
            longnick: 个性签名内容
        Returns:
            API响应数据
        """
        return (
            "set_self_longnick",
            {
                "longNick": longnick,
            },
        )

    async def get_stranger_info(
        self,
        user_id: Union[int, str],
    ) -> Any:
        """获取限生人信息
        Args:
            user_id: QQ号
        Returns:
            API响应数据
        """
        return (
            "get_stranger_info",
            {
                "user_id": user_id,
            },
        )

    async def get_friend_list(
        self,
        cache: bool = False,
    ) -> Any:
        """获取好友列表
        Args:
            cache: 是否使用缓存
        Returns:
            API响应数据
        """
        return (
            "get_friend_list",
            {
                "no_cache": cache,
            },
        )

    async def get_profile_like(
        self,
    ) -> Any:
        """获取个人资料卡点赞数
        Returns:
            API响应数据
        """
        return (
            "get_profile_like",
            {},
        )

    async def fetch_custom_face(
        self,
        count: int,
    ) -> Any:
        """获取收藏表情
        Args:
            count: 数量
        Returns:
            API响应数据
        """
        return (
            "fetch_custom_face",
            {
                "count": count,
            },
        )

    async def upload_private_file(
        self,
        user_id: Union[int, str],
        file: str,
        name: str,
    ) -> Any:
        """上传私聊文件
        Args:
            user_id: QQ号
            file: 文件路径
            name: 文件名
        Returns:
            API响应数据
        """
        return (
            "upload_private_file",
            {
                "user_id": user_id,
                "file": file,
                "name": name,
            },
        )

    async def delete_friend(
        self,
        user_id: Union[int, str],
        friend_id: Union[int, str],
        temp_block: bool,
        temp_both_del: bool,
    ) -> Any:
        """删除好友
        Args:
            user_id: QQ号
            friend_id: 好友ID
            temp_block: 拉黑
            temp_both_del: 双向删除
        Returns:
            API响应数据
        """
        return (
            "delete_friend",
            {
                "user_id": user_id,
                "friend_id": friend_id,
                "temp_block": temp_block,
                "temp_both_del": temp_both_del,
            },
        )

    async def nc_get_user_status(
        self,
        user_id: Union[int, str],
    ) -> Any:
        """获取用户状态
        Args:
            user_id: QQ号
        Returns:
            API响应数据
        """
        return (
            "nc_get_user_status",
            {
                "user_id": user_id,
            },
        )

    async def get_mini_app_ark(
        self,
        app_json: dict,
    ) -> Any:
        """获取小程序卡片
        Args:
            app_json: 小程序 JSON
        Returns:
            API响应数据
        """
        return (
            "get_mini_app_ark",
            app_json,
        )

    async def mark_private_msg_as_read(
        self,
        user_id: Union[int, str],
    ) -> Any:
        """设置私聊已读
        Args:
            user_id: QQ号
        Returns:
            API响应数据
        """
        return (
            "mark_private_msg_as_read",
            {
                "user_id": user_id,
            },
        )

    async def get_friend_msg_history(
        self,
        user_id: Union[int, str],
        message_seq: Union[int, str],
        count: int,
        reverse_order: bool,
    ) -> Any:
        """获取好友消息历史记录
        Args:
            user_id: QQ号
            message_seq: 消息序号
            count: 数量
            reverse_order: 是否倒序
        Returns:
            API响应数据
        """
        return (
            "get_friend_msg_history",
            {
                "user_id": user_id,
                "message_seq": message_seq,
                "count": count,
                "reverseOrder": reverse_order,
            },
        )

    async def set_friend_remark(
        self,
        user_id: Union[int, str],
        remark: str,
    ) -> Any:
        """设置好友备注
        Args:
            user_id: QQ号
            remark: 备注
        Returns:
            API响应数据
        """
        return (
            "set_friend_remark",
            {
                "user_id": user_id,
                "remark": remark,
            },
        )
