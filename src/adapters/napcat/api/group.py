from typing import Any, List, Union

from .message import NCAPIMessage


class NCAPIGroup(NCAPIMessage):
    """napcatAPI群组类"""

    abc = False

    async def send_group_message(
        self,
        group_id: Union[str, int],
        message: List[dict],
    ) -> Any:
        """发送群组消息(顶级接口，应当继续使用消息段封装)
        Args:
            group_id: 群号
            message: 消息段列表
        Returns:
            API响应数据
        """
        return (
            "send_group_msg",
            {
                "group_id": group_id,
                "message": message,
            },
        )

    async def get_group_list(
        self,
    ) -> Any:
        """获取群组列表
        Returns:
            API响应数据
        """
        return (
            "get_group_list",
            {},
        )

    async def get_group_info(
        self,
        group_id: int,
    ) -> Any:
        """获取群组信息
        Args:
            group_id: 群号
        Returns:
            API响应数据
        """
        return (
            "get_group_info",
            {
                "group_id": group_id,
            },
        )

    async def set_group_kick(
        self,
        group_id: Union[int, str],
        user_id: Union[int, str],
        reject_add_request: bool = False,
    ) -> Any:
        """踢出群成员
        Args:
            group_id: 群号
            user_id: QQ号
            reject_add_request: 是否群拉黑
        Returns:
            API响应数据
        """
        return (
            "set_group_kick",
            {
                "group_id": group_id,
                "user_id": user_id,
                "reject_add_request": reject_add_request,
            },
        )

    async def set_group_ban(
        self,
        group_id: Union[int, str],
        user_id: Union[int, str],
        duration: int,
    ) -> Any:
        """群组禁言
        Args:
            group_id: 群号
            user_id: QQ号
            duration: 禁言时长,单位秒,0为取消禁言
        Returns:
            API响应数据
        """
        return (
            "set_group_ban",
            {
                "group_id": group_id,
                "user_id": user_id,
                "duration": duration,
            },
        )

    async def get_group_system_msg(
        self,
        group_id: Union[int, str],
    ) -> Any:
        """获取群系统消息
        Args:
            group_id: 群号
        Returns:
            API响应数据
        """
        return (
            "get_group_system_msg",
            {
                "group_id": group_id,
            },
        )

    async def get_essence_msg_list(
        self,
        group_id: Union[int, str],
    ) -> Any:
        """获取精华消息列表
        Args:
            group_id: 群号
        Returns:
            API响应数据
        """
        return (
            "get_essence_msg_list",
            {
                "group_id": group_id,
            },
        )

    async def set_group_whole_ban(
        self,
        group_id: Union[int, str],
        enable: bool,
    ) -> Any:
        """群组全员禁言
        Args:
            group_id: 群号
            enable: 是否禁言
        Returns:
            API响应数据
        """
        return (
            "set_group_whole_ban",
            {
                "group_id": group_id,
                "enable": enable,
            },
        )

    async def set_group_portrait(
        self,
        group_id: Union[int, str],
        file: str,
    ) -> Any:
        """设置群头像
        Args:
            group_id: 群号
            file: 文件路径,支持网络路径和本地路径
        Returns:
            API响应数据
        """
        return (
            "set_group_portrait",
            {
                "group_id": group_id,
                "file": file,
            },
        )

    async def set_group_admin(
        self,
        group_id: Union[int, str],
        user_id: Union[int, str],
        enable: bool,
    ) -> Any:
        """设置群管理员
        Args:
            group_id: 群号
            user_id: QQ号
            enable: 是否设置为管理
        Returns:
            API响应数据
        """
        return (
            "set_group_admin",
            {
                "group_id": group_id,
                "user_id": user_id,
                "enable": enable,
            },
        )

    async def set_essence_msg(
        self,
        message_id: Union[int, str],
    ) -> Any:
        """设置精华消息
        Args:
            message_id: 消息ID
        Returns:
            API响应数据
        """
        return (
            "set_essence_msg",
            {
                "message_id": message_id,
            },
        )

    async def set_group_card(
        self,
        group_id: Union[int, str],
        user_id: Union[int, str],
        card: str,
    ) -> Any:
        """设置群名片
        Args:
            group_id: 群号
            user_id: QQ号
            card: 群名片,为空则为取消群名片
        Returns:
            API响应数据
        """
        return (
            "set_group_card",
            {
                "group_id": group_id,
                "user_id": user_id,
                "card": card,
            },
        )

    async def delete_essence_msg(
        self,
        message_id: Union[int, str],
    ) -> Any:
        """删除精华消息
        Args:
            message_id: 消息ID
        Returns:
            API响应数据
        """
        return (
            "delete_essence_msg",
            {
                "message_id": message_id,
            },
        )

    async def set_group_name(
        self,
        group_id: Union[int, str],
        group_name: str,
    ) -> Any:
        """设置群名
        Args:
            group_id: 群号
            group_name: 群名
        Returns:
            API响应数据
        """
        return (
            "set_group_name",
            {
                "group_id": group_id,
                "group_name": group_name,
            },
        )

    async def set_group_leave(
        self,
        group_id: Union[int, str],
    ) -> Any:
        """退出群组
        Args:
            group_id: 群号
        Returns:
            API响应数据
        """
        return (
            "set_group_leave",
            {
                "group_id": group_id,
            },
        )

    async def send_group_notice(
        self,
        group_id: Union[int, str],
        content: str,
        image: str = "",
    ) -> Any:
        """发送群公告
        Args:
            group_id: 群号
            content: 内容
            image: 图片路径,可选
        Returns:
            API响应数据
        """
        if image:
            return (
                "_send_group_notice",
                {
                    "group_id": group_id,
                    "content": content,
                    "image": image,
                },
            )
        else:
            return (
                "_send_group_notice",
                {
                    "group_id": group_id,
                    "content": content,
                },
            )

    async def get_group_notice(
        self,
        group_id: Union[int, str],
    ) -> Any:
        """获取群公告
        Args:
            group_id: 群号
        Returns:
            API响应数据
        """
        return (
            "_get_group_notice",
            {
                "group_id": group_id,
            },
        )

    async def set_group_special_title(
        self,
        group_id: Union[int, str],
        user_id: Union[int, str],
        special_title: str,
    ) -> Any:
        """设置群头衔
        Args:
            group_id: 群号
            user_id: QQ号
            special_title: 群头衔
        Returns:
            API响应数据
        """
        return (
            "set_group_special_title",
            {
                "group_id": group_id,
                "user_id": user_id,
                "special_title": special_title,
            },
        )

    async def upload_group_file(
        self,
        group_id: Union[int, str],
        file: str,
        name: str,
        folder_id: str,
    ) -> Any:
        """上传群文件
        Args:
            group_id: 群号
            file: 文件路径
            name: 文件名
            folder_id: 文件夹ID
        Returns:
            API响应数据
        """
        return (
            "upload_group_file",
            {
                "group_id": group_id,
                "file": file,
                "name": name,
                "folder_id": folder_id,
            },
        )

    async def set_group_add_request(
        self,
        flag: str,
        approve: bool,
        reason: str = "",
    ) -> Any:
        """处理加群请求
        Args:
            flag: 请求flag
            approve: 是否同意
            reason: 拒绝理由
        Returns:
            API响应数据
        """
        if approve:
            return (
                "set_group_add_request",
                {
                    "flag": flag,
                    "approve": approve,
                },
            )
        else:
            return (
                "set_group_add_request",
                {
                    "flag": flag,
                    "approve": approve,
                    "reason": reason,
                },
            )

    async def get_group_info_ex(
        self,
        group_id: Union[int, str],
    ) -> Any:
        """获取群信息(拓展)
        Args:
            group_id: 群号
        Returns:
            API响应数据
        """
        return (
            "get_group_info_ex",
            {
                "group_id": group_id,
            },
        )

    async def create_group_file_folder(
        self,
        group_id: Union[int, str],
        folder_name: str,
    ) -> Any:
        """创建群文件文件夹
        Args:
            group_id: 群号
            folder_name: 文件夹名
        Returns:
            API响应数据
        """
        return (
            "create_group_file_folder",
            {
                "group_id": group_id,
                "folder_name": folder_name,
            },
        )

    async def delete_group_file(
        self,
        group_id: Union[int, str],
        file_id: str,
    ) -> Any:
        """删除群文件
        Args:
            group_id: 群号
            file_id: 文件ID
        Returns:
            API响应数据
        """
        return (
            "delete_group_file",
            {
                "group_id": group_id,
                "file_id": file_id,
            },
        )

    async def delete_group_folder(
        self,
        group_id: Union[int, str],
        folder_id: str,
    ) -> Any:
        """删除群文件文件夹
        Args:
            group_id: 群号
            folder_id: 文件夹ID
        Returns:
            API响应数据
        """
        return (
            "delete_group_folder",
            {
                "group_id": group_id,
                "folder_id": folder_id,
            },
        )

    async def get_group_file_system_info(
        self,
        group_id: Union[int, str],
    ) -> Any:
        """获取群文件系统信息
        Args:
            group_id: 群号
        Returns:
            API响应数据
        """
        return (
            "get_group_file_system_info",
            {
                "group_id": group_id,
            },
        )

    async def get_group_root_files(
        self,
        group_id: Union[int, str],
    ) -> Any:
        """获取群根目录文件列表
        Args:
            group_id: 群号
        Returns:
            API响应数据
        """
        return (
            "get_group_root_files",
            {
                "group_id": group_id,
            },
        )

    async def get_group_files_by_folder(
        self,
        group_id: Union[int, str],
        folder_id: str,
        file_count: int,
    ) -> Any:
        """获取群文件列表
        Args:
            group_id: 群号
            folder_id: 文件夹ID
            file_count: 文件数量
        Returns:
            API响应数据
        """
        return (
            "get_group_files_by_folder",
            {
                "group_id": group_id,
                "folder_id": folder_id,
                "file_count": file_count,
            },
        )

    async def get_group_file_url(
        self,
        group_id: Union[int, str],
        file_id: str,
    ) -> Any:
        """获取群文件URL
        Args:
            group_id: 群号
            file_id: 文件ID
        Returns:
            API响应数据
        """
        return (
            "get_group_file_url",
            {
                "group_id": group_id,
                "file_id": file_id,
            },
        )

    async def get_group_member_info(
        self,
        group_id: Union[int, str],
        user_id: Union[int, str],
        no_cache: bool,
    ) -> Any:
        """获取群成员信息
        Args:
            group_id: 群号
            user_id: QQ号
            no_cache: 不缓存
        Returns:
            API响应数据
        """
        return (
            "get_group_member_info",
            {
                "group_id": group_id,
                "user_id": user_id,
                "no_cache": no_cache,
            },
        )

    async def get_group_member_list(
        self,
        group_id: Union[int, str],
        no_cache: bool = False,
    ) -> Any:
        """获取群成员列表
        Args:
            group_id: 群号
            no_cache: 不缓存
        Returns:
            API响应数据
        """
        return (
            "get_group_member_list",
            {
                "group_id": group_id,
                "no_cache": no_cache,
            },
        )

    async def get_group_honor_info(
        self,
        group_id: Union[int, str],
    ) -> Any:
        """获取群荣誉信息
        Args:
            group_id: 群号
        Returns:
            API响应数据
        """
        return (
            "get_group_honor_info",
            {
                "group_id": group_id,
            },
        )

    async def get_group_at_all_remain(
        self,
        group_id: Union[int, str],
    ) -> Any:
        """获取群 @全体成员 剩余次数
        Args:
            group_id: 群号
        Returns:
            API响应数据
        """
        return (
            "get_group_at_all_remain",
            {
                "group_id": group_id,
            },
        )

    async def get_group_ignored_notifies(
        self,
        group_id: Union[int, str],
    ) -> Any:
        """获取群过滤系统消息
        Args:
            group_id: 群号
        Returns:
            API响应数据
        """
        return (
            "get_group_ignored_notifies",
            {
                "group_id": group_id,
            },
        )

    async def set_group_sign(
        self,
        group_id: Union[int, str],
    ) -> Any:
        """群打卡
        Args:
            group_id: 群号
        Returns:
            API响应数据
        """
        return (
            "set_group_sign",
            {
                "group_id": group_id,
            },
        )

    async def send_group_sign(
        self,
        group_id: Union[int, str],
    ) -> Any:
        """群打卡
        Args:
            group_id: 群号
        Returns:
            API响应数据
        """
        return (
            "send_group_sign",
            {
                "group_id": group_id,
            },
        )

    async def get_ai_characters(
        self,
        group_id: Union[int, str],
        chat_type: Union[int, str],
    ) -> Any:
        """获取AI语音人物
        Args:
            group_id: 群号
            chat_type: 聊天类型
        Returns:
            API响应数据
        """
        return (
            "get_ai_characters",
            {
                "group_id": group_id,
                "chat_type": chat_type,
            },
        )

    async def send_group_ai_record(
        self,
        group_id: Union[int, str],
        character: str,
        text: str,
    ) -> Any:
        """发送群AI语音
        Args:
            group_id: 群号
            character: AI语音人物,即character_id
            text: 文本
        Returns:
            API响应数据
        """
        return (
            "send_group_ai_record",
            {
                "group_id": group_id,
                "character": character,
                "text": text,
            },
        )

    async def get_ai_record(
        self,
        group_id: Union[int, str],
        character: str,
        text: str,
    ) -> Any:
        """获取AI语音
        Args:
            group_id: 群号
            character: AI语音人物,即character_id
            text: 文本
        Returns:
            API响应数据
        """
        return (
            "get_ai_record",
            {
                "group_id": group_id,
                "character": character,
                "text": text,
            },
        )

    async def forward_group_single_msg(
        self,
        message_id: str,
        group_id: Union[int, str],
    ) -> Any:
        """转发群聊消息
        Args:
            message_id: 消息ID
            group_id: 群号
        Returns:
            API响应数据
        """
        return (
            "forward_group_single_msg",
            {
                "group_id": group_id,
                "message_id": message_id,
            },
        )

    async def send_group_forward_msg(
        self,
        group_id: Union[int, str],
        messages: str,
    ) -> Any:
        """合并转发的群聊消息
        Args:
            group_id: 群号
            messages: 消息列表
        Returns:
            API响应数据
        """
        if len(messages) == 0:
            return None

        return (
            "send_private_forward_msg",
            {
                "messages": "这里应当放个消息段",
                "group_id": group_id,
            },
        )

    async def get_group_shut_list(
        self,
        group_id: Union[int, str],
    ) -> Any:
        """获取群禁言列表
        Args:
            group_id: 群号
        Returns:
            API响应数据
        """
        return (
            "get_group_shut_list",
            {
                "group_id": group_id,
            },
        )

    async def del_group_notice(
        self,
        group_id: Union[int, str],
        notice_id: str,
    ) -> Any:
        """删除群公告
        Args:
            group_id: 群号
            notice_id: 通知 ID
        Returns:
            API响应数据
        """
        return (
            "_del_group_notice",
            {
                "group_id": group_id,
                "notice_id": notice_id,
            },
        )

    async def mark_group_msg_as_read(
        self,
        group_id: Union[int, str],
    ) -> Any:
        """设置群聊已读
        Args:
            group_id: 群号
        Returns:
            API响应数据
        """
        return (
            "mark_group_msg_as_read",
            {
                "group_id": group_id,
            },
        )

    async def get_group_msg_history(
        self,
        group_id: Union[int, str],
        message_seq: Union[int, str],
        count: int,
        reverse_order: bool,
    ) -> Any:
        """获取群消息历史记录
        Args:
            group_id: 群号
            message_seq: 消息序号
            count: 数量
            reverse_order: 是否倒序
        Returns:
            API响应数据
        """
        return (
            "get_group_msg_history",
            {
                "group_id": group_id,
                "message_seq": message_seq,
                "count": count,
                "reverseOrder": reverse_order,
            },
        )

    async def set_group_remark(
        self,
        group_id: Union[int, str],
        remark: str,
    ) -> Any:
        """设置群备注
        Args:
            group_id: 群号
            remark: 备注
        Returns:
            API响应数据
        """
        return (
            "set_group_remark",
            {
                "group_id": group_id,
                "remark": remark,
            },
        )
