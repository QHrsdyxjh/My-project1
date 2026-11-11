# sqli_tool — GET 参数 SQL 注入检测与利用工具

面向 **授权测试** 的 Python 命令行工具：对目标 URL 的 GET 参数做标准 SQL 注入检测，确认存在漏洞后再进入利用阶段。

默认目标为本地 DVWA 靶场：`http://127.0.0.1/vulnerabilities/sqli/?id=1&Submit=Submit#`

> ⚠️ 仅限在你自己拥有或已获得书面授权的系统上使用。对未授权系统进行测试可能违法。

## 快速开始

```bash
# 1. 创建虚拟环境（项目内 venv 已就绪时可跳过）
python -m venv venv

# 2. 安装依赖
venv\Scripts\python.exe -m pip install -r requirements.txt

# 3. 直接用默认目标与默认 Cookie 运行
venv\Scripts\python.exe main.py
```

Linux / macOS 把 `venv\Scripts\python.exe` 换成 `venv/bin/python`。

## 默认配置

| 项 | 默认值 | 位置 |
| --- | --- | --- |
| 目标 | `http://127.0.0.1/vulnerabilities/sqli/?id=1&Submit=Submit#` | `sqli_tool/config.py` |
| Cookie | `PHPSESSID=ttfhpn64pfi1ou645iq05jaf42; security=low` | `sqli_tool/config.py` |
| 时间盲注 SLEEP | 3 秒 | `sqli_tool/config.py` |
| 报告目录 | `reports/` | 命令行 `--outdir` |

Cookie 也可以在命令行覆盖，且无需手动 urldecode：

```bash
venv\Scripts\python.exe main.py -c "PHPSESSID=新的会话; security=low"
```

## Web 控制台

除命令行外，项目还提供了一个部署在 phpStudy（Apache + PHP 5.6）下的网页控制台：

```
http://127.0.0.1/PROJECT/sqlinjector.php
```

界面为深空 / 赛博风格：canvas 星空与代码雨、星云与轨道行星背景、扫描线与暗角叠加，
中间是任务终端与情报面板。功能与命令行完全等价，可在页面上选择四种模式：

| 模式 | 对应参数 | 说明 |
| --- | --- | --- |
| 检测 | 默认 | 只做注入检测，未确认漏洞不会进入利用阶段 |
| 枚举 | `--enumerate` | 读取库名、表名、列名与完整字段元数据（类型/主键/可空/默认值） |
| 导出 | `--dump` | 导出指定表数据，生成 CSV 供页面下载 |
| 查询 | `--query` | 直接读取一个 SQL 表达式 |

工作方式：

1. 页面 POST 到 `sqlinjector.php?action=start`，PHP 把任务参数写入 `sqli_jobs/<任务ID>/job.json`；
2. 通过 `proc_open` 拉起 `run.bat`，由 `venv` 中的 Python 执行 `web_runner.py <job.json>`，
   后者把任务翻译成 `main.py` 的命令行参数，输出重定向到 `output.log`；
3. 前端每 900ms 轮询 `?action=poll&job=<任务ID>`，拉取日志增量与运行状态
   （`done` / `clean` / `stopped` / `error` / `lost`），并可随时 `?action=stop` 终止；
4. 结束后 `?action=report` 读取 JSON 报告，页面渲染结构化情报面板，
   `?action=download` 下载 CSV。

其他接口：`?action=ping` 用于页面自检（Python 是否存在、运行器是否就绪）。

### 安全限制

- **默认只允许本机访问**：`sqlinjector.php` 顶部 `ALLOW_REMOTE = false` 时，
  仅接受来自 `127.0.0.1` / `::1` 的请求，其余返回 403。局域网内使用需改为 `true`，
  并自行确认访问控制。
- 任务 ID 走白名单正则校验，下载文件名同样校验，防止路径穿越。
- 存放在 `sqli_jobs/` 下的任务目录会在 2 天后自动清理。
- 该页面能调用 Python 工具，**不要**部署到公网或不可信环境。

### 目录说明

```
sqlinjector.php             # 单文件：页面渲染 + JSON API
web_runner.py               # job.json → main.py 命令行参数的桥接
webui/app.css               # 视觉样式（星云、轨道、扫描线、终端）
webui/app.js                # 星空/代码雨 canvas、终端、轮询与情报渲染
sqli_jobs/<任务ID>/         # 每次运行的 job.json / meta.json / status.json /
                            # run.bat / output.log / reports/
```

## 工作流程

1. **连通性检查** — 带 Cookie 请求目标，提示 HTTP 状态与是否疑似登录页。
2. **注入检测**（`sqli_tool/detector.py`）
   - 报错型：闭合引号后匹配数据库报错特征；
   - 布尔型：`AND 1=1` / `AND 1=2` 与基线页面做相似度比较；
   - 时间型：`AND SLEEP(n)` 观察响应耗时。
3. **确认后才继续**：未检出注入即退出，不做后续动作。
4. **利用阶段**（`sqli_tool/exploiter.py`）
   - `ORDER BY` 推断列数 → 定位可回显列 → 数据库指纹（类型/版本/用户/当前库）；
   - 系统表列与应用列 collation 不一致时自动降级为 `COLLATE utf8_general_ci` / `CAST AS BINARY` 等写法。
5. **盲注回退**（`sqli_tool/blind.py`）— UNION 不可回显时，用布尔或时间盲注做二分提取。
6. **枚举与导出**（`enumerator.py` / `dumper.py`）— 读 `information_schema` 拿库/表/列，逐行导出目标表。
7. **报告**（`report.py`）— 终端汇总 + `reports/` 下 JSON / Markdown 报告，导出数据同时写 CSV。

## 常用命令

```bash
# 只做检测
venv\Scripts\python.exe main.py

# 指定目标与注入参数
venv\Scripts\python.exe main.py -u "http://target/item.php?cat=1&page=2" -p cat

# 枚举当前库的表结构与字段详情
venv\Scripts\python.exe main.py --enumerate

# 枚举所有用户库（含系统库列表）
venv\Scripts\python.exe main.py --enumerate --all-databases --include-system

# 导出指定表（不出 --columns 时自动枚举全部列）
venv\Scripts\python.exe main.py --dump --db dvwa --table users --limit 20

# 读取任意表达式
venv\Scripts\python.exe main.py --query "@@version"
venv\Scripts\python.exe main.py --query "SELECT password FROM dvwa.users WHERE user=0x61646d696e"

# 走代理 / 忽略 TLS
venv\Scripts\python.exe main.py --proxy http://127.0.0.1:8080 --insecure
```

## 参数一览

| 参数 | 说明 |
| --- | --- |
| `-u, --url` | 目标 URL，可含多个 GET 参数 |
| `-p, --param` | 指定注入参数；省略时自动跳过 `Submit` 之类动作字段 |
| `-c, --cookie` | Cookie 字符串 |
| `--timeout` | 单请求超时（秒） |
| `--delay` | 时间盲注 SLEEP 秒数 |
| `--proxy` / `--insecure` | HTTP 代理 / 跳过证书校验 |
| `--no-color` | 关闭彩色输出 |
| `--enumerate` | 枚举数据库、表、列、字段详细信息 |
| `--all-databases` | 枚举所有非系统库（默认只枚举当前库） |
| `--include-system` | 库列表中包含 `information_schema` 等系统库 |
| `--deep-system` | 连系统库的表也展开字段详情（很慢） |
| `--db` / `--table` / `--columns` | 导出目标与列 |
| `--dump` / `--limit` | 导出数据 / 行数上限 |
| `--query` | 直接读取一个 SQL 表达式 |
| `--outdir` / `--no-report` | 报告目录 / 不生成报告 |

## 项目结构

```
PROJECT/
├── main.py                  # CLI 入口、流程编排
├── requirements.txt
├── sqlinjector.php          # Web 控制台（页面 + JSON API）
├── web_runner.py            # Web 任务 → CLI 参数桥接
├── webui/
│   ├── app.css              # 深空 / 赛博视觉样式
│   └── app.js               # 星空、代码雨、终端、轮询、情报渲染
├── sqli_tool/
│   ├── config.py            # 默认目标、Cookie、阈值
│   ├── http_client.py       # 统一 Session（Cookie/UA/超时/代理）
│   ├── target.py            # URL 解析与参数替换
│   ├── detector.py          # 报错/布尔/时间检测
│   ├── exploiter.py         # UNION 通道：列数、回显列、指纹、表达式读取
│   ├── blind.py             # 布尔/时间盲注 + 通道自适应
│   ├── enumerator.py        # information_schema 枚举
│   ├── dumper.py            # 逐行数据导出
│   ├── report.py            # JSON / Markdown 报告
│   ├── utils.py             # 输出、相似度、表格
│   └── errors.py            # 异常类型
├── venv/                    # 虚拟环境
└── reports/                 # 运行后生成
```

## 退出码

| 码 | 含义 |
| --- | --- |
| `0` | 检测到注入（利用可能成功也可能受权限限制） |
| `1` | 未检测到注入 / 无法利用 |
| `2` | 参数错误或目标不可达 |
| `130` | 用户中断 |

## 注意事项

- DVWA 的 `PHPSESSID` 会过期，出现“疑似登录页”提示时请重新登录后替换 Cookie。
- `--from-columns` 略去时导出的列来自 `information_schema`，若当前用户无权限读取系统表，请用 `--columns` 手工指定。
- 工具会优先使用 UNION 回显通道，失败自动降级为盲注；盲注模式下读取速度显著变慢，属正常现象。
- 导出使用逐行 `LIMIT n,1` 读取，避免 `GROUP_CONCAT` 受 `group_concat_max_len` 截断。
