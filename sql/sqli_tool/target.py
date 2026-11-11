"""目标 URL 解析与参数替换。"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .config import PARAM_SKIP_KEYS


@dataclass
class Target:
    base_url: str                       # 去掉 query 和 fragment 的地址
    params: list[tuple[str, str]]       # 原始参数顺序

    @classmethod
    def parse(cls, raw_url: str) -> "Target":
        parts = urlsplit(raw_url.strip())
        params = parse_qsl(parts.query, keep_blank_values=True)
        base = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        return cls(base_url=base, params=params)

    def build(self, param: str, value: str) -> str:
        """把指定参数替换成 payload，其余参数保持原样。"""
        pairs = [(k, value if k == param else v) for k, v in self.params]
        return f"{self.base_url}?{urlencode(pairs, safe='')}"

    def original_url(self) -> str:
        return f"{self.base_url}?{urlencode(self.params, safe='')}"

    def candidate_params(self) -> list[str]:
        """猜测可注入的参数，跳过 Submit 之类的动作字段。"""
        names = [name for name, _ in self.params]
        likely = [n for n in names if n.lower() not in PARAM_SKIP_KEYS and not n.lower().startswith("submit")]
        return likely or names

    def get_value(self, param: str) -> str:
        for name, value in self.params:
            if name == param:
                return value
        return ""
