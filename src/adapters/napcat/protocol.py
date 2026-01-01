import asyncio
import datetime as dt
import json
import logging
from typing import Any, Dict, List, Optional, TypeVar

from ...abc.protocol_abc import ProtocolABC, RawGroup, RawMessage, RawUser
from ...connector import AsyncWebSocketClient, MessageType
from ...core.IM import Group, Message, MessageChain, MessageNodeT, User, UserInfo
from ...plugins_system.core.events import Event
from ...utils.logformat import LogFormats
from ...utils.typec import GroupID, MsgId, UserID
from .api import NCAPI
from .builder import MessageBuilder

logger = logging.getLogger("Protocol.Napcat")


class NapcatProtocol(ProtocolABC):
    """napcat 协议实现"""

    protocol_name = "napcat"
    msg_builder = MessageBuilder

    def __init__(self):
        self._api = NCAPI()
        self._self_id: str = ""

    @property
    def api(self) -> NCAPI:
        """获取API实例"""
        return self._api

    @property
    def self_id(self) -> str:
        """获取Bot账户id"""
        return self._self_id

    # ========== 核心消息发送 ==========

    async def send_group_message(self, gid: GroupID, content: Message) -> RawMessage:
        """发送群消息"""
        # 将 Message 转换为 napcat 的消息格式
        await self._print_message(Event(event="message.group", data=content))
        message_segments = self._content_to_segments(content)

        # 调用 API 发送
        response = await self._api.group.send_group_message(
            group_id=gid, message=message_segments
        )

        return response

    async def send_private_message(self, uid: UserID, content: Message) -> RawMessage:
        """发送私聊消息"""
        await self._print_message(Event(event="message.private", data=content))
        # 将 Message 转换为 napcat 的消息格式
        message_segments = self._content_to_segments(content)

        # 调用 API 发送
        response = await self._api.user.send_private_msg(
            user_id=uid, message=message_segments
        )

        return response

    async def login(self, url: str, token: str, **kwd):
        """登录并建立WebSocket连接

        Args:
            token: 认证token
            ws_url: WebSocket连接地址
            headers: 可选的额外请求头

        Returns:
            登录信息
        """
        # 准备请求头
        headers = {}
        if token:
            headers["Authorization"] = token

        # 创建并启动WebSocket客户端
        client = AsyncWebSocketClient(url, logger=logger, headers=headers)
        self.client = client

        # 将客户端设置到API
        self._api.set_client(client)
        listener = await client.create_listener()
        await client.start()
        try:
            msg = await client.get_message(listener)
            await self._print_meta(self._parse_event(msg))
        finally:
            await client.remove_listener(listener)

        if not self.client.running:
            await self.client.start()
            await asyncio.sleep(0.1)
            while self.client.connection.is_connected():
                await asyncio.sleep(0.1)

        return client

    # ========== 数据获取 ==========

    async def fetch_user(self, uid: UserID) -> RawUser:
        """获取用户信息"""
        response = await self._api.user.get_stranger_info(user_id=uid)
        return response.get("data", response)

    async def fetch_group(self, gid: GroupID) -> RawGroup:
        """获取群信息"""
        response = await self._api.group.get_group_info(group_id=gid)
        return response.get("data", response)

    async def fetch_friends(self) -> List[RawUser]:
        """获取好友列表"""
        response = await self._api.user.get_friend_list()
        return response.get("data", [])

    async def fetch_groups(self) -> List[RawGroup]:
        """获取群组列表"""
        response = await self._api.group.get_group_list()
        return response.get("data", [])

    async def fetch_group_members(self, gid: GroupID) -> List[RawUser]:
        """获取群成员列表"""
        response = await self._api.group.get_group_member_list(group_id=gid)
        return response.get("data", [])

    async def recall_message(self, msg_id: MsgId) -> bool:
        """撤回消息"""
        response = await self._api.message.delete_msg(message_id=msg_id)
        return response.get("status") == "ok"

    async def logout(self) -> bool:
        """登出（napcat 通常不需要显式登出）"""
        # 停止 WebSocket 客户端
        if hasattr(self, "client") and self.client is not None:
            await self.client.stop()

        # napcat 通过关闭 WebSocket 连接来登出
        return True

    async def fetch_message(self, msg_id: MsgId) -> RawMessage:
        """获取消息详情"""
        response = await self._api.message.get_msg(message_id=msg_id)
        return response.get("data", response)

    # ========== 数据解析 ==========

    def _parse_message(self, raw: Dict[str, Any]) -> Message:
        """解析消息"""

        if raw.get("retcode"):
            retcode = raw.get("retcode")
            message = raw.get("message")
            logger.error("[Error %s]: %s|%s", retcode, message, raw)
            raise RuntimeError(raw)

        # 解析消息内容
        content = self._parse_message_content(raw.get("message", []))

        # 解析时间戳
        time = raw.get("time")
        if time:
            try:
                timestamp = dt.datetime.fromisoformat(time)
            except (ValueError, TypeError):
                timestamp = dt.datetime.now()
        else:
            timestamp = dt.datetime.now()

        msg = Message(
            msg_id=MsgId.new("napcat", raw.get("message_id"), time),
            sender_id=str(raw["user_id"]) if raw.get("user_id") else None,
            content=content,
            # TODO 完善 message_type 部分
            message_type=raw.get("message_type", "unknown"),
            timestamp=timestamp,
            group_id=str(raw["group_id"]) if raw.get("group_id") else None,
            raw=raw,
        )
        if "sender" in raw:
            msg._sender_cache = self._parse_user(raw.get("sender"))

        return msg

    def _parse_user(self, raw: Dict[str, Any]) -> User:
        """解析用户"""
        info = UserInfo(
            is_online=True,
            last_active=dt.datetime.now(),
        )
        return User(
            uid=str(raw["user_id"]) if raw.get("user_id") else None,
            nickname=raw.get("nickname"),
            role=raw.get("role"),
            group_name=raw.get("card") or raw.get("nickname"),
            info=info,
        )

    def _parse_group(self, raw: Dict[str, Any]) -> Group:
        """解析群组"""
        return Group(
            gid=str(raw.get("group_id", raw.get("gid", ""))),
            name=raw.get("group_name", raw.get("name", "")),
            description=raw.get("description"),
        )

    def _parse_event(self, raw: tuple[str, MessageType]) -> "Event | None":
        """解析事件

        Args:
            raw: 原始事件数据（消息内容, 消息类型）

        Returns:
            Event对象，如果不需要发布则返回None
        """
        # 只处理文本类型的消息
        if raw[1] != MessageType.Text:
            return None

        # 解析 JSON 数据
        try:
            raw_dict: dict = json.loads(raw[0])
            logger.debug("接收到原始数据: %s", raw_dict)
        except json.JSONDecodeError as e:
            logger.error("JSON 解析失败: %s", e)
            return None

        # 跳过API响应（有echo字段的是响应，没有post_type的也跳过）
        if "echo" in raw_dict or "post_type" not in raw_dict:
            return None

        post_type = raw_dict.get("post_type")

        match post_type:
            case "message":  # message.group / message.private
                event_name = f"message.{raw_dict['message_type']}"

            case "notice":
                event_name = f"notice.{raw_dict['notice_type']}"

            case "request":
                event_name = f"request.{raw_dict['request_type']}"

            case "meta_event":
                meta_event_type = raw_dict["meta_event_type"]
                event_name = f"meta.{meta_event_type}"

            case _:
                logger.warning("未知事件: %s", post_type)
                return

        # 解析消息内容（仅对 message 类型）
        if post_type == "message":
            data = self._parse_message(raw=raw_dict)
        else:
            data = raw_dict

        # 创建事件对象
        return Event(
            event=event_name,
            data=data,
            source="napcat",
            metadata={"post_type": post_type, "raw_event": raw_dict},
        )

    # ========== 辅助方法 ==========

    def _content_to_segments(self, content: Message) -> List[dict]:
        """将 Message 转换为 napcat 消息段"""
        from .nodes.node_base import BaseNode

        segments = []
        nodes: list[MessageNodeT] = content.content

        for node in nodes:
            if isinstance(node, BaseNode):
                # 所有BaseNode子类都支持to_dict，返回符合OneBot协议的格式
                segments.append(node.to_dict())
            elif isinstance(node, str):
                # 字符串直接转为text节点
                segments.append({"type": "text", "data": {"text": node}})

        return segments

    def _parse_message_content(self, segments: List[dict]) -> MessageChain:
        """解析 napcat 消息段为 Message"""
        from . import nodes
        from .nodes import dto
        from .nodes.dto import BaseDto
        from .nodes.node_base import NodeT

        Dto = TypeVar("Dto", bound=BaseDto)

        node = []

        for seg in segments:
            seg_type: str = seg.get("type")
            data: dict = seg.get("data", {})
            node_model: NodeT = getattr(nodes, seg_type.capitalize(), None)
            dto_model: Dto = getattr(dto, f"{seg_type.capitalize()}DTO", None)

            if dto_model and node_model:
                dto_class = dto_model.from_dict(data)
                node.append(node_model.from_dto(dto_class))

        return MessageChain(nodes=node)

    # ========== 好友管理 ==========

    async def add_friend(self, user_id: UserID, remark: Optional[str] = None) -> bool:
        """发起加好友请求（napcat 不支持主动添加好友）"""
        # napcat 协议不支持主动添加好友
        return False

    async def delete_friend(self, user_id: UserID) -> bool:
        """删除好友"""
        response = await self._api.user.delete_friend(
            user_id=user_id,
            friend_id=user_id,
            temp_block=False,
            temp_both_del=True,
        )
        return response.get("status") == "ok"

    async def block_user(self, user_id: UserID) -> bool:
        """拉黑用户（通过删除好友并拉黑实现）"""
        response = await self._api.user.delete_friend(
            user_id=user_id,
            friend_id=user_id,
            temp_block=True,  # 拉黑
            temp_both_del=False,  # 不双向删除
        )
        return response.get("status") == "ok"

    async def unblock_user(self, user_id: UserID) -> bool:
        """解除拉黑（napcat 不支持）"""
        # napcat 协议不支持解除拉黑
        return False

    async def set_friend_remark(self, user_id: UserID, remark: str) -> bool:
        """设置好友备注"""
        response = await self._api.user.set_friend_remark(
            user_id=user_id,
            remark=remark,
        )
        return response.get("status") == "ok"

    async def accept_friend_request(self, request_id: str) -> bool:
        """通过好友请求"""
        response = await self._api.user.set_friend_add_request(
            flag=request_id,
            approve=True,
            remark="",
        )
        return response.get("status") == "ok"

    async def reject_friend_request(self, request_id: str) -> bool:
        """拒绝好友请求"""
        response = await self._api.user.set_friend_add_request(
            flag=request_id,
            approve=False,
            remark="",
        )
        return response.get("status") == "ok"

    # ========== 群管理 ==========

    async def create_group(self, name: str, initial_members: List[UserID]) -> RawGroup:
        """创建群组（napcat 不支持）"""
        # napcat 协议不支持创建群组
        raise NotImplementedError("napcat 协议不支持创建群组")

    async def set_group_admin(
        self, group_id: GroupID, user_id: UserID, is_admin: bool = True
    ) -> bool:
        """设置/取消管理员"""
        response = await self._api.group.set_group_admin(
            group_id=group_id,
            user_id=user_id,
            enable=is_admin,
        )
        return response.get("status") == "ok"

    async def invite_to_group(self, group_id: GroupID, user_id: UserID) -> bool:
        """邀请成员（napcat 不直接支持）"""
        # napcat 协议不直接支持邀请成员
        return False

    async def kick_group_member(
        self, group_id: GroupID, user_id: UserID, reason: Optional[str] = None
    ) -> bool:
        """移除成员

        Args:
            group_id: 群组ID
            user_id: 用户ID
            reason: 踢出原因（napcat 不支持该参数，会被忽略）
        """
        response = await self._api.group.set_group_kick(
            group_id=group_id,
            user_id=user_id,
            reject_add_request=False,
        )
        return response.get("status") == "ok"

    async def set_group_name(self, group_id: GroupID, name: str) -> bool:
        """修改群名称"""
        response = await self._api.group.set_group_name(
            group_id=group_id,
            group_name=name,
        )
        return response.get("status") == "ok"

    async def set_group_avatar(self, group_id: GroupID, avatar_uri: str) -> bool:
        """修改群头像"""
        response = await self._api.group.set_group_portrait(
            group_id=group_id,
            file=avatar_uri,
        )
        return response.get("status") == "ok"

    async def disband_group(self, group_id: GroupID) -> bool:
        """解散群（napcat 不支持）"""
        # napcat 协议不支持解散群，只能退出群
        return False

    async def transfer_group_ownership(
        self, group_id: GroupID, new_owner_id: UserID
    ) -> bool:
        """转让群主（napcat 不支持）"""
        # napcat 协议不支持转让群主
        return False

    async def leave_group(self, group_id: GroupID) -> bool:
        """退出群组"""
        response = await self._api.group.set_group_leave(group_id=group_id)
        return response.get("status") == "ok"

    # ========== 个人资料管理 ==========

    async def set_self_nickname(self, nickname: str) -> bool:
        """设置/修改本人昵称"""
        response = await self._api.user.set_qq_profile(
            nickname=nickname,
            personal_note="",
            sex="",
        )
        return response.get("status") == "ok"

    async def set_self_avatar(self, avatar_uri: str) -> bool:
        """设置/修改本人头像"""
        response = await self._api.user.set_qq_avatar(avatar=avatar_uri)
        return response.get("status") == "ok"

    async def set_self_signature(self, signature: str) -> bool:
        """设置/修改本人签名/状态"""
        response = await self._api.user.set_self_long_nick(longnick=signature)
        return response.get("status") == "ok"

    async def update_self_profile(self, profile_data: Dict[str, Any]) -> bool:
        """批量更新个人资料"""
        # 从 profile_data 中提取支持的字段
        nickname = profile_data.get("nickname", "")
        personal_note = profile_data.get("signature", "")
        sex = profile_data.get("sex", "")

        response = await self._api.user.set_qq_profile(
            nickname=nickname,
            personal_note=personal_note,
            sex=sex,
        )
        return response.get("status") == "ok"

    async def print_event(self, event: Event) -> None:
        """线程安全 / 异常吞噬，保证绝不抛给上游"""
        try:
            await self._do_print(event)
        except Exception as e:
            logger.error("print failed: %s | event=%s", e, event)

    # ------------------------- 内部分发 ------------------------- #
    async def _do_print(self, event: Event) -> None:
        post_type, *_ = event.event.split(".", 1)
        match post_type:
            case "message":
                await self._print_message(event)
            # TODO 完善消息提示
            # case "notice":
            #     await self._print_notice(event)
            # case "request":
            #     await self._print_request(event)
            case "meta":
                await self._print_meta(event)
            case _:
                logger.debug("[UnknownEvent] %s", event.event)

    # ------------------------- message 分支 ------------------------- #
    async def _print_message(self, event: Event[Message]) -> None:
        msg = event.data
        sender = await msg.get_sender()
        group_id = msg.group_id
        nick = await sender.get_nickname()
        if group_id:
            groupi = await msg.get_group()
            name = await groupi.get_name()
            logger.info(LogFormats.modern(group_id, nick, sender.uid, msg, name))
        else:
            logger.info(LogFormats.modern(None, nick, sender.uid, msg))

    # ------------------------- notice 分支 ------------------------- #
    async def _print_notice(self, event: Event) -> None:
        n = event.data
        match event.event:
            case "notice.group_upload":
                filename = n.file.get("name") or "unknown"
                logger.info("[群文件] 群 %s 上传：%s", n.group_id, filename)

            case "notice.group_admin":
                action = "设置" if n.sub_type == "set" else "取消"
                logger.info("[群管理] 群 %s %s管理员 %s", n.group_id, action, n.user_id)

            case "notice.group_decrease":
                logger.info("[群成员] 群 %s 成员减少 %s", n.group_id, n.user_id)

            case "notice.group_increase":
                logger.info("[群成员] 群 %s 成员增加 %s", n.group_id, n.user_id)

            case "notice.group_ban":
                action = "禁言" if n.sub_type == "ban" else "解除禁言"
                logger.info("[群禁言] 群 %s %s %s", n.group_id, action, n.user_id)

            case "notice.friend_add":
                logger.info("[好友] 新好友 %s", n.user_id)

            case "notice.group_recall":
                logger.info("[群撤回] 群 %s 消息 %s 被撤回", n.group_id, n.message_id)

            case "notice.friend_recall":
                logger.info("[私聊撤回] 好友 %s 撤回消息 %s", n.user_id, n.message_id)

            case "notice.notify.poke":
                logger.info(
                    "[戳一戳] 群 %s | %s → %s", n.group_id, n.user_id, n.target_id
                )

            case "notice.notify.lucky_king":
                logger.info("[红包运气王] 群 %s → %s", n.group_id, n.target_id)

            case "notice.notify.honor":
                logger.info("[群荣誉] 群 %s 成员 %s 荣誉变更", n.group_id, n.user_id)

            case _:
                logger.debug("[Notice] 未打印子类型：%s", event.event)

    # ------------------------- request 分支 ------------------------- #
    async def _print_request(self, event: Event) -> None:
        r = event.data
        flag = r.flag
        if len(flag) > 16:
            flag = flag[:16] + "…"
        match event.event:
            case "request.friend":
                logger.info(
                    "[加好友请求] %s 申请：%s（flag=%s）",
                    r.user_id,
                    r.comment or "",
                    flag,
                )
            case "request.group":
                logger.info(
                    "[加群请求] 群 %s | %s 申请：%s（flag=%s）",
                    r.group_id,
                    r.user_id,
                    r.comment or "",
                    flag,
                )
            case _:
                logger.debug("[Request] 未打印子类型：%s", event.event)

    # ------------------------- meta 分支 ------------------------- #
    async def _print_meta(self, event: Event[Message]) -> None:
        m = event.data
        match event.event:
            case "meta.lifecycle":
                self._self_id = m["self_id"]
                logger.info("Bot.%s 启动", m["self_id"])
                logger.name = f"Bot.{m['self_id']}"
            case "meta.heartbeat":
                online = m["status"]["online"]
                good = m["status"]["good"]
                if online and good:
                    # logger.debug("[心跳] t=%s status=%s", m["time"], m["status"])
                    pass
                else:
                    logger.exception("服务异常 online:%s, good:%s", online, good)
            case _:
                logger.debug("[Meta] 未打印子类型：%s", event.event)
