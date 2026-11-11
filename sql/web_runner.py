"""Web 控制台运行器。

读取 JSON 任务描述（由 sqlinjector.php 生成），转成 main.py 的命令行参数，
执行结束后把退出码写入同目录的 status.json，供网页轮询。
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from main import main  # noqa: E402


def build_argv(spec: dict) -> list[str]:
    argv = ["--no-color", "-u", str(spec.get("url", ""))]

    cookie = spec.get("cookie") or ""
    if cookie:
        argv += ["-c", cookie]

    param = spec.get("param") or ""
    if param:
        argv += ["-p", param]

    if spec.get("delay"):
        argv += ["--delay", str(spec["delay"])]
    if spec.get("timeout"):
        argv += ["--timeout", str(spec["timeout"])]
    if spec.get("force_blind"):
        argv.append("--force-blind")
    if spec.get("outdir"):
        argv += ["--outdir", spec["outdir"]]

    mode = spec.get("mode", "detect")
    if mode == "enumerate":
        argv.append("--enumerate")
        if spec.get("db"):
            argv += ["--db", spec["db"]]
        if spec.get("all_databases"):
            argv.append("--all-databases")
        if spec.get("include_system"):
            argv.append("--include-system")
    elif mode == "dump":
        argv.append("--dump")
        if spec.get("db"):
            argv += ["--db", spec["db"]]
        if spec.get("table"):
            argv += ["--table", spec["table"]]
        if spec.get("columns"):
            argv += ["--columns", spec["columns"]]
        if spec.get("limit"):
            argv += ["--limit", str(spec["limit"])]
    elif mode == "query":
        if spec.get("query"):
            argv += ["--query", spec["query"]]

    return argv


def main_entry() -> int:
    if len(sys.argv) < 2:
        print("用法：web_runner.py <job.json>")
        return 2

    spec_path = os.path.abspath(sys.argv[1])
    job_dir = os.path.dirname(spec_path)
    status_path = os.path.join(job_dir, "status.json")

    code = 1
    try:
        with open(spec_path, "r", encoding="utf-8") as handle:
            spec = json.load(handle)
        argv = build_argv(spec)
        print(f"[web] 参数：{' '.join(argv)}", flush=True)
        code = main(argv)
    except SystemExit as exc:
        code = int(exc.code or 0)
    except BaseException:
        traceback.print_exc()
        code = 1
    finally:
        try:
            with open(status_path, "w", encoding="utf-8") as handle:
                json.dump({"exit": code, "ended": time.time()}, handle)
        except OSError:
            pass
        sys.stdout.flush()
    return code


if __name__ == "__main__":
    sys.exit(main_entry())
