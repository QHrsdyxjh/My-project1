"""通用工具函数：输出、相似度、SQL 字面量、表格打印。"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Iterable, Sequence

_ANSI_ENABLED = True

_COLORS = {
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "grey": "90",
    "bold": "1",
}


def set_ansi(enabled: bool) -> None:
    global _ANSI_ENABLED
    _ANSI_ENABLED = enabled


def color(text: str, name: str) -> str:
    if not _ANSI_ENABLED:
        return text
    return f"\033[{_COLORS.get(name, '0')}m{text}\033[0m"


def info(msg: str) -> None:
    print(color("[*] ", "cyan") + msg)


def success(msg: str) -> None:
    print(color("[+] ", "green") + msg)


def warn(msg: str) -> None:
    print(color("[!] ", "yellow") + msg)


def error(msg: str) -> None:
    print(color("[-] ", "red") + msg)


def debug(msg: str) -> None:
    print(color("[.] ", "grey") + msg)


def similarity(a: str, b: str, limit: int = 20000) -> float:
    """归一化空白后计算页面相似度，结果范围 0.0 ~ 1.0。"""
    a = " ".join(a.split())[:limit]
    b = " ".join(b.split())[:limit]
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def hex_literal(value: str) -> str:
    """把字符串转成 MySQL 十六进制字面量，避免引号/转义问题。"""
    if not value:
        return "''"
    return "0x" + value.encode("utf-8").hex()


def print_table(headers: Sequence[str], rows: Iterable[Sequence[object]], max_width: int = 60) -> None:
    rows = [["" if cell is None else str(cell) for cell in row] for row in rows]
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], min(len(cell), max_width))

    def fmt(cells: Sequence[str]) -> str:
        out = []
        for i, cell in enumerate(cells):
            cell = cell.replace("\n", " ")
            if len(cell) > max_width:
                cell = cell[: max_width - 3] + "..."
            out.append(cell.ljust(widths[i]))
        return " | ".join(out).rstrip()

    print(fmt(headers))
    print("-+-".join("-" * w for w in widths))
    for row in rows:
        print(fmt(row))
