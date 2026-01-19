from logging import getLogger

from src.utils.color import Color

logger = getLogger("fcatbot")


class LogFormats:
    """日志格式系统 - 提供多种实用风格"""

    # ================ 简洁实用风格 ================

    @staticmethod
    def simple(group_id, nick, uid, msg, group_name=None):
        """极简风格 - 最高效"""
        if group_id:
            return (
                f"{Color.GREEN}{group_name or f'G{group_id}'}{Color.RESET} | "
                f"{Color.YELLOW}{nick}{Color.GRAY}({uid}){Color.RESET}: {msg}"
            )
        return (
            f"{Color.MAGENTA}PM{Color.RESET} | "
            f"{Color.YELLOW}{nick}{Color.GRAY}({uid}){Color.RESET}: {Color.CYAN}{msg}{Color.RESET}"
        )

    @staticmethod
    def tag(group_id, nick, uid, msg, group_name=None):
        """标签风格 - 清晰明确"""
        if group_id:
            return (
                f"{Color.GRAY}[{Color.GREEN}GROUP{Color.GRAY}] "
                f"{Color.BLUE}{group_name}{Color.GRAY}: "
                f"{Color.YELLOW}{nick}{Color.GRAY}[{uid}]{Color.RESET} » {msg}"
            )
        return (
            f"{Color.GRAY}[{Color.MAGENTA}PRIVATE{Color.GRAY}] "
            f"{Color.YELLOW}{nick}{Color.GRAY}[{uid}]{Color.RESET} » {Color.CYAN}{msg}{Color.RESET}"
        )

    # ================ 专业风格 ================

    @staticmethod
    def professional(group_id, nick, uid, msg, group_name=None):
        """专业风格 - 适合监控"""
        from datetime import datetime

        timestamp = datetime.now().strftime("%H:%M:%S")

        if group_id:
            return (
                f"{Color.GRAY}{timestamp} {Color.GREEN}[GRP]{Color.RESET} "
                f"{Color.WHITE}{group_name:<15} {Color.YELLOW}{nick:<10} "
                f"{Color.GRAY}({uid}){Color.RESET} : {msg}"
            )
        return (
            f"{Color.GRAY}{timestamp} {Color.MAGENTA}[PVT]{Color.RESET} "
            f"{Color.YELLOW}{nick:<10} {Color.GRAY}({uid}){Color.RESET} : {Color.CYAN}{msg}{Color.RESET}"
        )

    @staticmethod
    def network(group_id, nick, uid, msg, group_name=None):
        """网络风格 - 类似网络包格式"""
        if group_id:
            return (
                f"{Color.CYAN}GROUP:{Color.GREEN}{group_name} "
                f"{Color.GRAY}[ID:{group_id}] {Color.YELLOW}{nick} "
                f"{Color.GRAY}<{uid}>{Color.WHITE} > {msg}{Color.RESET}"
            )
        return (
            f"{Color.MAGENTA}PRIVATE {Color.YELLOW}{nick} "
            f"{Color.GRAY}<{uid}>{Color.WHITE} >> {Color.CYAN}{msg}{Color.RESET}"
        )

    # ================ 开发调试风格 ================

    @staticmethod
    def debug(group_id, nick, uid, msg, group_name=None):
        """调试风格 - 详细信息"""
        from datetime import datetime

        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        if group_id:
            return (
                f"{Color.GRAY}{timestamp} | "
                f"{Color.BLUE}Type:Group{Color.RESET} | "
                f"{Color.GREEN}Name:{group_name}{Color.RESET} | "
                f"{Color.YELLOW}User:{nick}{Color.RESET} | "
                f"{Color.CYAN}UID:{uid}{Color.RESET} | "
                f"{Color.WHITE}Msg:{msg}{Color.RESET}"
            )
        return (
            f"{Color.GRAY}{timestamp} | "
            f"{Color.MAGENTA}Type:Private{Color.RESET} | "
            f"{Color.YELLOW}User:{nick}{Color.RESET} | "
            f"{Color.CYAN}UID:{uid}{Color.RESET} | "
            f"{Color.GREEN}Msg:{msg}{Color.RESET}"
        )

    @staticmethod
    def minimal(group_id, nick, uid, msg, group_name=None):
        """最小化风格 - 最少字符"""
        if group_id:
            return f"{Color.GREEN}G{Color.RESET} {nick}: {msg}"
        return f"{Color.MAGENTA}P{Color.RESET} {nick}: {msg}"

    # ================ 层次结构风格 ================

    @staticmethod
    def hierarchical(group_id, nick, uid, msg, group_name=None):
        """层次结构风格 - 适合大量消息"""
        if group_id:
            return (
                f"{Color.CYAN}└─ {Color.GREEN}{group_name}{Color.RESET}\n"
                f"    {Color.YELLOW}├─ {nick}{Color.GRAY} ({uid}){Color.RESET}\n"
                f"    {Color.WHITE}└─ {msg}{Color.RESET}"
            )
        return (
            f"{Color.MAGENTA}├─ {Color.YELLOW}{nick}{Color.GRAY} ({uid}){Color.RESET}\n"
            f"{Color.MAGENTA}└─ {Color.CYAN}{msg}{Color.RESET}"
        )

    @staticmethod
    def segment(group_id, nick, uid, msg, group_name=None):
        """分段风格 - 视觉分隔"""
        if group_id:
            return (
                f"{Color.CYAN}╞ {Color.GREEN}{group_name} {Color.GRAY}[{group_id}]{Color.RESET}\n"
                f"{Color.CYAN}╞ {Color.YELLOW}{nick} {Color.GRAY}<{uid}>{Color.RESET}\n"
                f"{Color.CYAN}╰─ {Color.WHITE}{msg}{Color.RESET}"
            )
        return (
            f"{Color.MAGENTA}╞ {Color.YELLOW}{nick} {Color.GRAY}<{uid}>{Color.RESET}\n"
            f"{Color.MAGENTA}╰─ {Color.CYAN}{msg}{Color.RESET}"
        )

    # ================ 数据表格风格 ================

    @staticmethod
    def table(group_id, nick, uid, msg, group_name=None):
        """表格风格 - 对齐美观"""
        if group_id:
            return (
                f"{Color.CYAN}│ {Color.GREEN}{str(group_name)[:20]:<20} "
                f"{Color.YELLOW}│ {nick[:12]:<12} "
                f"{Color.BLUE}│ {uid:<10} "
                f"{Color.WHITE}│ {msg[:40]}{Color.RESET}"
            )
        return (
            f"{Color.MAGENTA}│ {Color.YELLOW}{'Private':<20} "
            f"{Color.YELLOW}│ {nick[:12]:<12} "
            f"{Color.CYAN}│ {uid:<10} "
            f"{Color.GREEN}│ {msg[:40]}{Color.RESET}"
        )

    @staticmethod
    def table_header():
        """表格标题"""
        return (
            f"{Color.CYAN}├{'─'*80}┤{Color.RESET}\n"
            f"{Color.CYAN}│ {Color.WHITE}{'Source':<20} {'User':<12} {'ID':<10} {'Message':<38}{Color.CYAN} │{Color.RESET}\n"
            f"{Color.CYAN}├{'─'*80}┤{Color.RESET}"
        )

    # ================ 状态机风格 ================

    @staticmethod
    def state_machine(group_id, nick, uid, msg, group_name=None):
        """状态机风格 - 显示处理流程"""
        if group_id:
            return (
                f"{Color.GRAY}[RECV] {Color.GREEN}[GROUP] "
                f"{Color.WHITE}← {Color.YELLOW}{nick} "
                f"{Color.GRAY}({uid}) {Color.WHITE}@ {Color.CYAN}{group_name}"
                f"{Color.GRAY} → {Color.WHITE}{msg[:50]}...{Color.RESET}"
            )
        return (
            f"{Color.GRAY}[RECV] {Color.MAGENTA}[PRIVATE] "
            f"{Color.WHITE}← {Color.YELLOW}{nick} "
            f"{Color.GRAY}({uid}){Color.GRAY} → {Color.CYAN}{msg[:50]}...{Color.RESET}"
        )

    # ================ 通信协议风格 ================

    @staticmethod
    def protocol(group_id, nick, uid, msg, group_name=None):
        """协议风格 - 类似网络协议格式"""
        msg_len = len(str(msg))
        if group_id:
            return (
                f"{Color.GRAY}[MESSAGE]{Color.RESET}\n"
                f"{Color.BLUE}  TYPE:   GROUP{Color.RESET}\n"
                f"{Color.GREEN}  FROM:   {nick}{Color.RESET}\n"
                f"{Color.CYAN}  UID:    {uid}{Color.RESET}\n"
                f"{Color.YELLOW}  GROUP:  {group_name}{Color.RESET}\n"
                f"{Color.WHITE}  LENGTH: {msg_len}{Color.RESET}\n"
                f"{Color.MAGENTA}  DATA:   {msg[:60]}{Color.RESET}"
            )
        return (
            f"{Color.GRAY}[MESSAGE]{Color.RESET}\n"
            f"{Color.BLUE}  TYPE:   PRIVATE{Color.RESET}\n"
            f"{Color.GREEN}  FROM:   {nick}{Color.RESET}\n"
            f"{Color.CYAN}  UID:    {uid}{Color.RESET}\n"
            f"{Color.WHITE}  LENGTH: {msg_len}{Color.RESET}\n"
            f"{Color.MAGENTA}  DATA:   {msg[:60]}{Color.RESET}"
        )

    # ================ 现代化风格 ================

    @staticmethod
    def modern(group_id, nick, uid, msg, group_name=None):
        """现代风格 - 简洁美观"""
        if group_id:
            return (
                f"{Color.RESET}{Color.GREEN}{group_name} "
                f"{Color.GRAY}• {Color.YELLOW}{nick} "
                f"{Color.GRAY}({uid}){Color.CYAN} ▸ {Color.RESET}{msg}{Color.RESET}"
            )
        return (
            f"{Color.RESET}{Color.YELLOW}{nick} "
            f"{Color.GRAY}({uid}){Color.MAGENTA} ▸ {Color.RESET}{msg}{Color.RESET}"
        )

    @staticmethod
    def compact(group_id, nick, uid, msg, group_name=None):
        """紧凑风格 - 节省空间"""
        if group_id:
            return f"{Color.GREEN}G{Color.RESET}:{Color.YELLOW}{nick[:6]}{Color.RESET}:{msg[:40]}"
        return f"{Color.MAGENTA}P{Color.RESET}:{Color.YELLOW}{nick[:6]}{Color.RESET}:{msg[:40]}"

    # ================ 特殊场景风格 ================

    @staticmethod
    def highlight(group_id, nick, uid, msg, group_name=None, highlight_words=None):
        """高亮风格 - 关键词高亮"""
        if highlight_words is None:
            highlight_words = []

        highlighted_msg = str(msg)
        for word in highlight_words:
            if word in highlighted_msg:
                highlighted_msg = highlighted_msg.replace(
                    word, f"{Color.RED}{word}{Color.RESET}"
                )

        if group_id:
            return (
                f"{Color.GREEN}⚠ {group_name}{Color.RESET} | "
                f"{Color.YELLOW}{nick}{Color.RESET} | {highlighted_msg}"
            )
        return (
            f"{Color.MAGENTA}⚠ PRIVATE{Color.RESET} | "
            f"{Color.YELLOW}{nick}{Color.RESET} | {highlighted_msg}"
        )

    @staticmethod
    def priority(group_id, nick, uid, msg, group_name=None, priority="NORMAL"):
        """优先级风格 - 根据重要性显示"""
        priority_colors = {
            "HIGH": Color.RED,
            "MEDIUM": Color.YELLOW,
            "NORMAL": Color.GREEN,
            "LOW": Color.BLUE,
        }
        color = priority_colors.get(priority, Color.WHITE)

        if group_id:
            return (
                f"{color}[{priority}] {Color.GREEN}{group_name}{Color.RESET} | "
                f"{Color.YELLOW}{nick}{Color.RESET}: {msg}"
            )
        return (
            f"{color}[{priority}] {Color.MAGENTA}PRIVATE{Color.RESET} | "
            f"{Color.YELLOW}{nick}{Color.RESET}: {msg}"
        )


# ================ 风格预览函数 ================
def preview_all_styles():
    """预览所有日志风格"""
    print(f"{Color.WHITE}{Color.BOLD}=== 日志风格预览 ==={Color.RESET}\n")

    test_cases = [
        ("群聊消息示例", "User123", 10001, "这是一个测试消息", "测试群组"),
        ("私聊消息示例", "Friend456", 20002, "你好，这是一个私聊测试", None),
    ]

    styles = [
        ("simple", "极简风格"),
        ("tag", "标签风格"),
        ("professional", "专业风格"),
        ("network", "网络风格"),
        ("debug", "调试风格"),
        ("minimal", "最小化风格"),
        ("hierarchical", "层次结构风格"),
        ("segment", "分段风格"),
        ("table", "表格风格"),
        ("state_machine", "状态机风格"),
        ("protocol", "协议风格"),
        ("modern", "现代风格"),
        ("compact", "紧凑风格"),
    ]

    for style_name, style_desc in styles:
        print(f"{Color.CYAN}{style_desc} ({style_name}):{Color.RESET}")

        for case_name, nick, uid, msg, group_name in test_cases:
            if group_name:
                log_text = getattr(LogFormats, style_name)(
                    123, nick, uid, msg, group_name
                )
            else:
                log_text = getattr(LogFormats, style_name)(None, nick, uid, msg)

            print(f"  {log_text}")

        print()


# 可以运行预览
# preview_all_styles()
