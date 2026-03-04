"""
Core constants for the Push project.
"""

# PushPlus 单条消息最大安全长度（字符数）。
# 说明：
# - 来源于对 PushPlus 接口的实际压测与线上运行经验；
# - 超过该长度的内容在部分情况下会发送失败或被强制分页；
# - 所有与 PushPlus 消息体积相关的逻辑（分页、裁剪等）应统一参考此常量。
PUSHPLUS_MAX_CONTENT_LENGTH = 19800

