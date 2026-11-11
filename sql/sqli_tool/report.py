"""报告输出：终端打印 + JSON / Markdown 落盘。"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from .utils import info, print_table, success

# 这些键在终端/报告中用结构化渲染，而不是直接打印整个字典
SCHEMA_KEYS = ("表结构",)


class Report:
    def __init__(self, target_url: str, cookie: str) -> None:
        self.data: dict[str, Any] = {
            "tool": "sqli_tool",
            "target": target_url,
            "cookie": cookie,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "vulnerable": False,
            "steps": [],
            "findings": {},
        }

    def add_step(self, name: str, detail: Any) -> None:
        self.data["steps"].append({"name": name, "detail": detail})

    def set_finding(self, key: str, value: Any) -> None:
        self.data["findings"][key] = value

    def mark_vulnerable(self) -> None:
        self.data["vulnerable"] = True

    # ---------- 落盘 ----------
    def save_json(self, folder: str) -> str:
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"sqli_report_{datetime.now():%Y%m%d_%H%M%S}.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.data, handle, ensure_ascii=False, indent=2)
        success(f"JSON 报告已保存：{path}")
        return path

    def save_markdown(self, folder: str) -> str:
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"sqli_report_{datetime.now():%Y%m%d_%H%M%S}.md")
        findings = self.data["findings"]
        lines = [
            "# SQL 注入测试报告",
            "",
            f"- 目标：`{self.data['target']}`",
            f"- 时间：{self.data['timestamp']}",
            f"- 结论：{'**存在 SQL 注入**' if self.data['vulnerable'] else '未发现注入'}",
            "",
            "## 发现",
            "",
        ]
        schema = findings.get("表结构")
        for key, value in findings.items():
            if key in SCHEMA_KEYS:
                continue
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False)
            lines.append(f"- **{key}**：`{value}`")
        if not findings:
            lines.append("- 无")

        if schema:
            lines += ["", "## 表结构", ""]
            lines += self._markdown_schema(schema)

        lines += ["", "## 测试步骤", ""]
        for step in self.data["steps"]:
            detail = step["detail"]
            if not isinstance(detail, str):
                detail = json.dumps(detail, ensure_ascii=False)
            lines.append(f"- **{step['name']}** — {detail}")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
        success(f"Markdown 报告已保存：{path}")
        return path

    @staticmethod
    def _markdown_schema(schema: dict) -> list[str]:
        """把嵌套的表结构渲染成按库/表分节的 Markdown 表格。"""
        lines: list[str] = []
        for db, tables in schema.items():
            lines.append(f"### 数据库 `{db}`")
            lines.append("")
            if not tables:
                lines += ["（无表或无权限）", ""]
                continue
            for table_name, table in tables.items():
                meta = []
                if isinstance(table, dict):
                    if table.get("engine"):
                        meta.append(f"引擎 {table['engine']}")
                    if table.get("rows"):
                        meta.append(f"约 {table['rows']} 行")
                header = f"#### `{db}.{table_name}`"
                if meta:
                    header += f"（{'，'.join(meta)}）"
                lines += [header, ""]
                columns = table.get("columns", []) if isinstance(table, dict) else []
                if not columns:
                    lines += ["（未取得字段信息）", ""]
                    continue
                lines.append("| 列名 | 类型 | 可空 | 键 | 默认值 | 额外 | 备注 |")
                lines.append("| --- | --- | --- | --- | --- | --- | --- |")
                for col in columns:
                    lines.append(
                        "| {name} | {type} | {nullable} | {key} | {default} | {extra} | {comment} |".format(
                            name=col.get("name", ""),
                            type=col.get("type", ""),
                            nullable=col.get("nullable", ""),
                            key=col.get("key", ""),
                            default=col.get("default", ""),
                            extra=col.get("extra", ""),
                            comment=col.get("comment", ""),
                        )
                    )
                lines.append("")
        return lines

    # ---------- 终端 ----------
    def show_findings(self) -> None:
        findings = self.data["findings"]
        if not findings:
            info("无额外发现")
            return
        rows = []
        for key, value in findings.items():
            if key in SCHEMA_KEYS and isinstance(value, dict):
                tables = sum(len(t) for t in value.values())
                rows.append((key, f"{len(value)} 个库，{tables} 张表（详见报告）"))
            elif isinstance(value, (dict, list)):
                rows.append((key, json.dumps(value, ensure_ascii=False)))
            else:
                rows.append((key, value))
        print_table(["项目", "值"], rows, max_width=70)
