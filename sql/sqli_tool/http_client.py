"""HTTP 客户端封装：统一携带 Cookie、UA、超时，并记录响应耗时。"""

from __future__ import annotations

import time
from dataclasses import dataclass

import requests

from .config import DEFAULT_COOKIE, DEFAULT_TIMEOUT, DEFAULT_USER_AGENT
from .errors import TargetUnreachable


@dataclass
class Response:
    status: int
    text: str
    elapsed: float
    url: str

    @property
    def length(self) -> int:
        return len(self.text)


class HttpClient:
    def __init__(
        self,
        cookie: str = DEFAULT_COOKIE,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = DEFAULT_TIMEOUT,
        verify_tls: bool = True,
        proxy: str | None = None,
    ) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        )
        if cookie:
            # 直接把 Cookie 字符串塞进请求头，保留用户的原始格式
            self.session.headers["Cookie"] = cookie.strip()
        self.session.verify = verify_tls
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}
        self.timeout = timeout
        self.request_count = 0

    def get(self, url: str) -> Response:
        self.request_count += 1
        started = time.perf_counter()
        try:
            resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
        except requests.RequestException as exc:
            raise TargetUnreachable(f"请求失败：{exc}") from exc
        elapsed = time.perf_counter() - started
        return Response(status=resp.status_code, text=resp.text, elapsed=elapsed, url=resp.url)
