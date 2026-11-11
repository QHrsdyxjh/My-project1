"""工具内部异常。"""


class ToolError(Exception):
    """工具可预期错误（参数错误、无法利用等）。"""


class TargetUnreachable(ToolError):
    """目标地址不可达。"""


class NotExploitable(ToolError):
    """已确认注入，但当前通道无法提取数据。"""
