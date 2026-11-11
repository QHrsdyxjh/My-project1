"""全局默认配置。

默认目标为本地 DVWA（Damn Vulnerable Web Application）的 SQL 注入页面，
仅用于学习与本地授权测试。
"""

DEFAULT_TARGET_URL = "http://127.0.0.1/vulnerabilities/sqli/?id=1&Submit=Submit#"

# 默认 Cookie：DVWA 登录后的会话 + 安全等级 low
DEFAULT_COOKIE = ""

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT = 15.0          # 单个请求超时（秒）
DEFAULT_DELAY = 3.0             # 时间盲注 SLEEP 秒数
MAX_COLUMNS = 10                # UNION 探测最大列数
MAX_EXTRACT_LENGTH = 128        # 盲注提取字符串的最大长度
DUMP_LIMIT = 100                # 默认导出行数

# 与目标参数无关的表单字段，自动挑选注入参数时跳过
PARAM_SKIP_KEYS = {
    "submit",
    "submit.x",
    "submit.y",
    "btnsubmit",
    "login",
    "action",
}
