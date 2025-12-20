from __future__ import annotations

import base64
import os
import struct
import time
from dataclasses import dataclass
from typing import Final, Self


class MsgId:
    """
    256-bit 定长二进制 ID，内部结构可配置：
        [flag:1b][scope_hash:63b] | time_ms:64b | real_id:(64+Δ)b | random:(56-Δ)b | checksum:8b
    其中 Δ = 7 - RANDOM_BYTES，Δ∈[0,7]
    """

    __slots__ = ("_buf",)

    # -------------------- 可伸缩参数 --------------------
    RANDOM_BYTES: Final[int] = 7  # 0~7，调小后 random 缩短，real_id 自动变长
    # ---------------------------------------------------

    def __init__(self, buf: bytes) -> None:
        if len(buf) != 32:
            raise ValueError("MsgId must be 32 bytes")
        self._buf = buf

    # ==================== dataclass 描述 ====================
    @dataclass(frozen=True)
    class _Decoded:
        flag: bool
        scope_hash: int
        time_ms: int
        real_id: int
        random_val: int

    # -------------------- 范围检查工具 --------------------
    @staticmethod
    def _check_range(name: str, val: int, low: int, high: int) -> None:
        if not (low <= val <= high):
            raise ValueError(f"{name}={val} out of range [{low:#x}, {high:#x}]")

    # =======================================================
    @classmethod
    def new(
        cls,
        scope: str,
        server_msg_id: int | None = None,
        time_ms: int | None = None,
    ) -> Self:
        # 时间范围：1970-01-01 00:00:00 ～ 2106-02-07 06:28:15 (64bit ms)
        time_ms = int((time_ms or time.time()) * 1000)
        cls._check_range("time_ms", time_ms, 0, 0xFFFF_FFFF_FFFF_FFFF)

        flag = 0 if server_msg_id is not None else 1
        scope_hash = cls._stable_hash(scope)

        # server_msg_id / real_id 范围
        real_id_len = 8 + (7 - cls.RANDOM_BYTES)  # 8~15 字节
        max_real_id = (1 << (real_id_len * 8)) - 1
        real_id = server_msg_id if server_msg_id is not None else 0
        cls._check_range("real_id/server_msg_id", real_id, 0, max_real_id)

        # 随机数范围
        rand_len = cls.RANDOM_BYTES  # 0~7 字节
        rand = int.from_bytes(os.urandom(rand_len), "big")
        if rand_len:  # 0 字节时 rand 恒为 0
            cls._check_range("random", rand, 0, (1 << (rand_len * 8)) - 1)

        # 拼 payload
        header = (flag << 63) | scope_hash
        payload = (
            struct.pack(">QQ", header, time_ms)
            + real_id.to_bytes(real_id_len, "big")
            + rand.to_bytes(rand_len, "big")
        )
        checksum = sum(payload) & 0xFF
        return cls(payload + bytes([checksum]))

    # -------------------- 序列化 --------------------
    def __bytes__(self) -> bytes:
        return self._buf

    @property
    def base64(self) -> str:
        return base64.b64encode(self._buf, altchars=b"-_").decode().rstrip("=")

    @classmethod
    def from_base64(cls, s: str) -> Self:
        s += "=" * (-len(s) % 4)
        return cls(base64.b64decode(s, altchars=b"-_"))

    # -------------------- 解析 --------------------
    def parse(self) -> _Decoded:
        b = self._buf
        if sum(b[:31]) & 0xFF != b[31]:
            raise ValueError("checksum failed")

        header = int.from_bytes(b[:8], "big")
        time_ms = int.from_bytes(b[8:16], "big")
        rand_len = self.RANDOM_BYTES
        real_id_len = 8 + (7 - rand_len)

        real_id = int.from_bytes(b[16 : 16 + real_id_len], "big")
        random_val = int.from_bytes(b[16 + real_id_len : 31], "big")
        flag = (header >> 63) & 1
        scope_hash = header & 0x7FFF_FFFF_FFFF_FFFF

        # 二次校验
        self._check_range("time_ms", time_ms, 0, 0xFFFF_FFFF_FFFF_FFFF)
        self._check_range("real_id", real_id, 0, (1 << (real_id_len * 8)) - 1)
        if rand_len:
            self._check_range("random_val", random_val, 0, (1 << (rand_len * 8)) - 1)

        return self._Decoded(bool(flag), scope_hash, time_ms, real_id, random_val)

    # -------------------- 内部工具 --------------------
    @staticmethod
    def _stable_hash(s: str) -> int:
        import hashlib

        return (
            int.from_bytes(hashlib.blake2b(s.encode(), digest_size=8).digest(), "big")
            & 0x7FFFFFFFFFFFFFFF
        )

    # -------------------- 调试 --------------------
    def __repr__(self) -> str:
        return f"MsgId({self.base64})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, MsgId) and self._buf == other._buf

    def __hash__(self) -> int:
        return hash(self._buf)
