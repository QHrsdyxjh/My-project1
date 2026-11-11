<?php
/**
 * sqlinjector.php — SQL INJECTOR 深空注入终端（Web 控制台）
 *
 * 仅用于本地授权测试：默认只允许 127.0.0.1 / ::1 访问。
 * 后端把任务写成 JSON，交给 web_runner.py 在后台执行，
 * 前端通过轮询读取 output.log 与 reports/*.json。
 *
 * 环境要求：phpStudy 的 Apache + PHP 5.6+，已安装 Python 虚拟环境 venv。
 */

error_reporting(E_ALL);
ini_set('display_errors', '0');

define('ROOT_DIR', __DIR__);
define('JOBS_DIR', ROOT_DIR . DIRECTORY_SEPARATOR . 'sqli_jobs');
define('PYTHON_BIN', ROOT_DIR . DIRECTORY_SEPARATOR . 'venv' . DIRECTORY_SEPARATOR . 'Scripts' . DIRECTORY_SEPARATOR . 'python.exe');
define('RUNNER', ROOT_DIR . DIRECTORY_SEPARATOR . 'web_runner.py');
define('ALLOW_REMOTE', false);   // 改为 true 可允许局域网访问（风险自负）

header('X-Content-Type-Options: nosniff');

/* ------------------------------------------------------------------ */
/* 基础工具                                                            */
/* ------------------------------------------------------------------ */

function client_ip()
{
    return isset($_SERVER['REMOTE_ADDR']) ? $_SERVER['REMOTE_ADDR'] : '';
}

function is_local()
{
    return in_array(client_ip(), array('127.0.0.1', '::1', '::ffff:127.0.0.1'), true);
}

function json_out($data, $code = 200)
{
    http_response_code($code);
    header('Content-Type: application/json; charset=utf-8');
    header('Cache-Control: no-store');
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function text($value, $max = 2000)
{
    $value = is_string($value) ? $value : '';
    $value = trim($value);
    if (function_exists('mb_substr')) {
        return mb_substr($value, 0, $max, 'UTF-8');
    }
    return substr($value, 0, $max);
}

function valid_job_id($id)
{
    return is_string($id) && preg_match('/^[0-9]{8}_[0-9]{6}_[a-f0-9]{8}$/', $id) === 1;
}

/** 表单编码下布尔值会变成 "true"/"false" 字符串，统一按真值语义判断。 */
function flag($value)
{
    if (is_bool($value)) {
        return $value;
    }
    if (is_int($value)) {
        return $value !== 0;
    }
    return in_array(strtolower(trim((string) $value)), array('1', 'true', 'on', 'yes'), true);
}

function job_dir($id)
{
    return JOBS_DIR . DIRECTORY_SEPARATOR . $id;
}

function rm_rf($path)
{
    if (is_file($path)) {
        @unlink($path);
        return;
    }
    if (!is_dir($path)) {
        return;
    }
    foreach (scandir($path) as $item) {
        if ($item === '.' || $item === '..') {
            continue;
        }
        rm_rf($path . DIRECTORY_SEPARATOR . $item);
    }
    @rmdir($path);
}

function cleanup_old_jobs($days = 2)
{
    if (!is_dir(JOBS_DIR)) {
        return;
    }
    $limit = time() - $days * 86400;
    foreach (scandir(JOBS_DIR) as $item) {
        if ($item === '.' || $item === '..') {
            continue;
        }
        $path = JOBS_DIR . DIRECTORY_SEPARATOR . $item;
        if (is_dir($path) && filemtime($path) < $limit) {
            rm_rf($path);
        }
    }
}

function read_json_file($path, $assoc = true)
{
    if (!is_file($path)) {
        return null;
    }
    $raw = @file_get_contents($path);
    if ($raw === false || $raw === '') {
        return null;
    }
    $data = json_decode($raw, $assoc);
    return $data === null ? null : $data;
}

function pid_alive($pid)
{
    $pid = (int) $pid;
    if ($pid <= 0) {
        return false;
    }
    $out = array();
    $code = 0;
    @exec('tasklist /FI "PID eq ' . $pid . '" /NH 2>&1', $out, $code);
    $joined = implode(' ', $out);
    return strpos($joined, (string) $pid) !== false;
}

/* ------------------------------------------------------------------ */
/* 路由                                                                */
/* ------------------------------------------------------------------ */

$action = isset($_GET['action']) ? $_GET['action'] : '';

if ($action === '') {
    if (!ALLOW_REMOTE && !is_local()) {
        http_response_code(403);
        header('Content-Type: text/html; charset=utf-8');
        echo '<!doctype html><meta charset="utf-8"><body style="background:#04060d;color:#ff5f7e;font-family:monospace;padding:60px">'
           . '<h1>ACCESS DENIED</h1><p>仅允许本机访问该控制台。</p></body>';
        exit;
    }
    render_page();
    exit;
}

if (!ALLOW_REMOTE && !is_local()) {
    json_out(array('error' => '仅允许本机访问'), 403);
}

switch ($action) {
    case 'ping':
        $out = array();
        $code = 0;
        @exec('"' . PYTHON_BIN . '" --version 2>&1', $out, $code);
        json_out(array(
            'ok' => is_file(PYTHON_BIN) && is_file(RUNNER),
            'python' => trim(implode(' ', $out)),
            'runner' => is_file(RUNNER),
            'jobs' => is_dir(JOBS_DIR),
        ));
        break;

    case 'start':
        handle_start();
        break;

    case 'poll':
        handle_poll();
        break;

    case 'stop':
        handle_stop();
        break;

    case 'report':
        handle_report();
        break;

    case 'download':
        handle_download();
        break;

    default:
        json_out(array('error' => '未知操作'), 400);
}

/* ------------------------------------------------------------------ */
/* API 处理                                                            */
/* ------------------------------------------------------------------ */

function handle_start()
{
    if (!is_file(PYTHON_BIN)) {
        json_out(array('error' => '未找到 venv/Scripts/python.exe，请先创建虚拟环境'), 500);
    }

    // 优先使用表单编码（PHP 5.6 下 application/json 会触发
    // $HTTP_RAW_POST_DATA 弃用警告，污染 JSON 响应）
    $spec = $_POST;
    if (!$spec) {
        $raw = file_get_contents('php://input');
        $decoded = json_decode($raw, true);
        $spec = is_array($decoded) ? $decoded : array();
    }
    if (!$spec) {
        json_out(array('error' => '请求体为空或格式错误'), 400);
    }

    $url = isset($spec['url']) ? text($spec['url'], 1500) : '';
    $parts = parse_url($url);
    if (!$url || !$parts || empty($parts['host']) || !in_array(strtolower(isset($parts['scheme']) ? $parts['scheme'] : ''), array('http', 'https'), true)) {
        json_out(array('error' => '目标地址无效，需为 http/https URL'), 400);
    }

    $mode = isset($spec['mode']) ? text($spec['mode'], 20) : 'detect';
    if (!in_array($mode, array('detect', 'enumerate', 'dump', 'query'), true)) {
        $mode = 'detect';
    }

    $table = isset($spec['table']) ? text($spec['table'], 64) : '';
    $query = isset($spec['query']) ? text($spec['query'], 1000) : '';
    if ($mode === 'dump' && $table === '') {
        json_out(array('error' => '导出模式必须填写数据表名'), 400);
    }
    if ($mode === 'query' && $query === '') {
        json_out(array('error' => '查询模式必须填写 SQL 表达式'), 400);
    }

    cleanup_old_jobs();
    if (!is_dir(JOBS_DIR) && !@mkdir(JOBS_DIR, 0777, true)) {
        json_out(array('error' => '无法创建任务目录'), 500);
    }

    $id = date('Ymd_His') . '_' . substr(md5(uniqid('', true)), 0, 8);
    $dir = job_dir($id);
    $reports = $dir . DIRECTORY_SEPARATOR . 'reports';
    if (!@mkdir($reports, 0777, true)) {
        json_out(array('error' => '无法创建任务目录'), 500);
    }

    $limit = isset($spec['limit']) ? (int) $spec['limit'] : 20;
    $limit = max(1, min(1000, $limit));
    $delay = isset($spec['delay']) ? (float) $spec['delay'] : 3.0;
    $delay = max(1.0, min(10.0, $delay));

    $job = array(
        'url' => $url,
        'cookie' => isset($spec['cookie']) ? text($spec['cookie'], 1200) : '',
        'param' => isset($spec['param']) ? text($spec['param'], 64) : '',
        'mode' => $mode,
        'db' => isset($spec['db']) ? text($spec['db'], 64) : '',
        'table' => $table,
        'columns' => isset($spec['columns']) ? text($spec['columns'], 500) : '',
        'limit' => $limit,
        'query' => $query,
        'delay' => $delay,
        'timeout' => 20,
        'force_blind' => flag(isset($spec['force_blind']) ? $spec['force_blind'] : false),
        'all_databases' => flag(isset($spec['all_databases']) ? $spec['all_databases'] : false),
        'include_system' => flag(isset($spec['include_system']) ? $spec['include_system'] : false),
        'outdir' => $reports,
    );

    $specPath = $dir . DIRECTORY_SEPARATOR . 'job.json';
    file_put_contents($specPath, json_encode($job, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));

    // 批处理把 python 输出重定向到 output.log，避免 PHP 管道阻塞
    $logPath = $dir . DIRECTORY_SEPARATOR . 'output.log';
    $batPath = $dir . DIRECTORY_SEPARATOR . 'run.bat';
    $python = '"' . PYTHON_BIN . '"';
    $runner = '"' . RUNNER . '"';
    $specArg = '"' . $specPath . '"';
    $bat = "@echo off\r\n"
         . "chcp 65001 >nul 2>&1\r\n"
         . "cd /d \"" . ROOT_DIR . "\"\r\n"
         . "set PYTHONIOENCODING=utf-8\r\n"
         . "set PYTHONUNBUFFERED=1\r\n"
         . $python . " -u " . $runner . " " . $specArg . "\r\n";
    file_put_contents($batPath, $bat);

    $descriptors = array(
        0 => array('file', 'NUL', 'r'),
        1 => array('file', $logPath, 'a'),
        2 => array('file', $logPath, 'a'),
    );
    $cwd = ROOT_DIR;
    $env = null;
    $proc = @proc_open('cmd.exe /C ' . escapeshellarg($batPath), $descriptors, $pipes, $cwd, $env);
    if (!is_resource($proc)) {
        json_out(array('error' => '无法启动 Python 进程'), 500);
    }
    $status = proc_get_status($proc);
    $pid = isset($status['pid']) ? (int) $status['pid'] : 0;

    $meta = array(
        'id' => $id,
        'pid' => $pid,
        'started' => time(),
        'url' => $job['url'],
        'mode' => $job['mode'],
    );
    file_put_contents($dir . DIRECTORY_SEPARATOR . 'meta.json', json_encode($meta, JSON_UNESCAPED_UNICODE));

    json_out(array('job' => $id, 'pid' => $pid, 'mode' => $job['mode']));
}

function handle_poll()
{
    $id = isset($_GET['job']) ? $_GET['job'] : '';
    if (!valid_job_id($id)) {
        json_out(array('error' => '任务 ID 无效'), 400);
    }
    $dir = job_dir($id);
    if (!is_dir($dir)) {
        json_out(array('error' => '任务不存在或已清理'), 404);
    }

    $meta = read_json_file($dir . DIRECTORY_SEPARATOR . 'meta.json');
    $status = read_json_file($dir . DIRECTORY_SEPARATOR . 'status.json');

    $state = 'running';
    $exit = null;
    if (is_array($status) && isset($status['exit'])) {
        $exit = (int) $status['exit'];
        if ($exit === 0) {
            $state = 'done';
        } elseif ($exit === 1) {
            $state = 'clean';          // 未检测到注入
        } elseif ($exit === 130) {
            $state = 'stopped';        // 被中断
        } else {
            $state = 'error';
        }
    } elseif (is_array($meta) && isset($meta['pid']) && $meta['pid'] > 0 && !pid_alive($meta['pid'])) {
        $state = 'lost';
    }

    $logPath = $dir . DIRECTORY_SEPARATOR . 'output.log';
    $log = '';
    if (is_file($logPath)) {
        $size = filesize($logPath);
        $read = 320000;
        if ($size > $read) {
            $handle = fopen($logPath, 'rb');
            if ($handle) {
                fseek($handle, $size - $read);
                $log = fread($handle, $read);
                fclose($handle);
                $log = "[... 日志过长，仅显示最后 " . round($read / 1024) . " KB ...]\n" . $log;
            }
        } else {
            $log = (string) @file_get_contents($logPath);
        }
    }

    $started = is_array($meta) && isset($meta['started']) ? (int) $meta['started'] : time();
    json_out(array(
        'job' => $id,
        'status' => $state,
        'exit' => $exit,
        'log' => $log,
        'elapsed' => max(0, time() - $started),
        'mode' => is_array($meta) && isset($meta['mode']) ? $meta['mode'] : '',
        'requests' => substr_count($log, '[+]') + substr_count($log, '[*]'),
    ));
}

function handle_stop()
{
    $id = isset($_GET['job']) ? $_GET['job'] : '';
    if (!valid_job_id($id)) {
        json_out(array('error' => '任务 ID 无效'), 400);
    }
    $meta = read_json_file(job_dir($id) . DIRECTORY_SEPARATOR . 'meta.json');
    if (!is_array($meta) || empty($meta['pid'])) {
        json_out(array('error' => '任务未在运行'), 404);
    }
    $out = array();
    $code = 0;
    @exec('taskkill /PID ' . (int) $meta['pid'] . ' /T /F 2>&1', $out, $code);
    json_out(array('ok' => true, 'output' => trim(implode(' ', $out))));
}

function handle_report()
{
    $id = isset($_GET['job']) ? $_GET['job'] : '';
    if (!valid_job_id($id)) {
        json_out(array('error' => '任务 ID 无效'), 400);
    }
    $reports = job_dir($id) . DIRECTORY_SEPARATOR . 'reports';
    if (!is_dir($reports)) {
        json_out(array('report' => null, 'csv' => array()));
    }

    $jsonFiles = glob($reports . DIRECTORY_SEPARATOR . '*.json');
    $csvFiles = glob($reports . DIRECTORY_SEPARATOR . '*.csv');
    $report = null;
    if ($jsonFiles) {
        usort($jsonFiles, function ($a, $b) {
            return filemtime($b) - filemtime($a);
        });
        $report = read_json_file($jsonFiles[0]);
    }

    $csv = array();
    foreach ($csvFiles as $file) {
        $csv[] = basename($file);
    }

    $status = read_json_file(job_dir($id) . DIRECTORY_SEPARATOR . 'status.json');
    json_out(array(
        'report' => $report,
        'csv' => $csv,
        'exit' => is_array($status) && isset($status['exit']) ? (int) $status['exit'] : null,
    ));
}

function handle_download()
{
    $id = isset($_GET['job']) ? $_GET['job'] : '';
    $file = isset($_GET['file']) ? $_GET['file'] : '';
    if (!valid_job_id($id) || !preg_match('/^[A-Za-z0-9_\-\.]+\.csv$/', $file)) {
        http_response_code(400);
        echo '参数无效';
        exit;
    }
    $path = job_dir($id) . DIRECTORY_SEPARATOR . 'reports' . DIRECTORY_SEPARATOR . $file;
    if (!is_file($path)) {
        http_response_code(404);
        echo '文件不存在';
        exit;
    }
    header('Content-Type: text/csv; charset=utf-8');
    header('Content-Disposition: attachment; filename="' . $file . '"');
    header('Content-Length: ' . filesize($path));
    readfile($path);
    exit;
}

/* ------------------------------------------------------------------ */
/* 页面                                                                */
/* ------------------------------------------------------------------ */

function render_page()
{
    header('Content-Type: text/html; charset=utf-8');
    $pythonReady = is_file(PYTHON_BIN) && is_file(RUNNER);
    ?>
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SQL INJECTOR · 深空注入终端</title>
<link rel="stylesheet" href="webui/app.css">
</head>
<body>
<canvas id="stars" aria-hidden="true"></canvas>
<canvas id="rain" aria-hidden="true"></canvas>

<div class="nebula n1" aria-hidden="true"></div>
<div class="nebula n2" aria-hidden="true"></div>
<div class="nebula n3" aria-hidden="true"></div>

<div class="cosmos" aria-hidden="true">
  <div class="orbit o1"></div>
  <div class="orbit o2"></div>
  <div class="orbit o3"></div>
  <div class="planet">
    <div class="planet-glow"></div>
    <div class="planet-body"></div>
  </div>
  <div class="moon m1"></div>
  <div class="moon m2"></div>
</div>

<div class="grid-overlay" aria-hidden="true"></div>
<div class="scanlines" aria-hidden="true"></div>
<div class="vignette" aria-hidden="true"></div>

<div class="shell">
  <header class="topbar">
    <div class="brand">
      <svg class="sigil" viewBox="0 0 48 48" aria-hidden="true">
        <polygon points="24,3 42,13.5 42,34.5 24,45 6,34.5 6,13.5" fill="none" stroke="currentColor" stroke-width="1.4"/>
        <polygon points="24,10 35.5,16.6 35.5,29.4 24,36 12.5,29.4 12.5,16.6" fill="none" stroke="currentColor" stroke-width=".8" opacity=".5"/>
        <circle cx="24" cy="23" r="5.2" fill="none" stroke="currentColor" stroke-width="1.6"/>
        <circle cx="24" cy="23" r="1.6" fill="currentColor"/>
        <path d="M4 23h7M37 23h7" stroke="currentColor" stroke-width="1" opacity=".6"/>
      </svg>
      <div class="titles">
        <h1 class="glitch" data-text="SQL INJECTOR">SQL INJECTOR</h1>
        <p class="sub">深空注入终端 <span>//</span> DEEP-SPACE INJECTION CONSOLE</p>
      </div>
    </div>
    <div class="hud">
      <div class="hud-chip" id="engineChip">
        <i class="led <?php echo $pythonReady ? 'ok' : 'err'; ?>" id="engineLed"></i>
        <span id="engineText">ENGINE <?php echo $pythonReady ? 'ONLINE' : 'OFFLINE'; ?></span>
      </div>
      <div class="hud-chip mono" id="clock">--:--:--</div>
    </div>
  </header>

  <main class="layout">
    <aside class="panel control">
      <div class="panel-head"><span class="tick"></span>目标参数<em>TARGET PARAMETERS</em></div>
      <div class="panel-body">
        <label class="field">
          <span class="label">目标地址<em>URL</em></span>
          <input id="url" spellcheck="false" autocomplete="off"
                 value="http://127.0.0.1/vulnerabilities/sqli/?id=1&amp;Submit=Submit#">
        </label>

        <label class="field">
          <span class="label">Cookie 会话<em>SESSION</em></span>
          <textarea id="cookie" rows="2" spellcheck="false"
                    placeholder="PHPSESSID=...; security=low">PHPSESSID=ttfhpn64pfi1ou645iq05jaf42; security=low</textarea>
        </label>

        <div class="row2">
          <label class="field">
            <span class="label">注入参数<em>PARAM</em></span>
            <input id="param" placeholder="自动识别" spellcheck="false" autocomplete="off">
          </label>
          <label class="field">
            <span class="label">SLEEP 秒<em>DELAY</em></span>
            <input id="delay" type="number" min="1" max="10" step="0.5" value="3">
          </label>
        </div>

        <div class="field">
          <span class="label">任务模式<em>MISSION MODE</em></span>
          <div class="modes" id="modes">
            <button type="button" class="mode active" data-mode="detect">检测</button>
            <button type="button" class="mode" data-mode="enumerate">枚举</button>
            <button type="button" class="mode" data-mode="dump">导出</button>
            <button type="button" class="mode" data-mode="query">查询</button>
          </div>
        </div>

        <div class="mode-fields" data-mode="enumerate" hidden>
          <div class="row2">
            <label class="field">
              <span class="label">数据库<em>DB</em></span>
              <input id="db" placeholder="当前库" spellcheck="false" autocomplete="off">
            </label>
            <label class="switchfield tight">
              <input type="checkbox" id="allDb"><span class="switch"></span>枚举所有库
            </label>
          </div>
        </div>

        <div class="mode-fields" data-mode="dump" hidden>
          <div class="row2">
            <label class="field">
              <span class="label">数据库<em>DB</em></span>
              <input id="dumpDb" placeholder="当前库" spellcheck="false" autocomplete="off">
            </label>
            <label class="field">
              <span class="label">数据表<em>TABLE</em></span>
              <input id="table" placeholder="users" spellcheck="false" autocomplete="off">
            </label>
          </div>
          <div class="row2">
            <label class="field">
              <span class="label">列<em>COLUMNS</em></span>
              <input id="columns" placeholder="留空 = 全部" spellcheck="false" autocomplete="off">
            </label>
            <label class="field">
              <span class="label">行数<em>LIMIT</em></span>
              <input id="limit" type="number" min="1" max="1000" value="20">
            </label>
          </div>
        </div>

        <div class="mode-fields" data-mode="query" hidden>
          <label class="field">
            <span class="label">SQL 表达式<em>EXPRESSION</em></span>
            <input id="query" placeholder="@@version" spellcheck="false" autocomplete="off">
          </label>
        </div>

        <label class="switchfield">
          <input type="checkbox" id="forceBlind"><span class="switch"></span>强制盲注通道 <em class="hint">FORCE BLIND</em>
        </label>

        <div class="actions">
          <button id="runBtn" class="primary" type="button">
            <span class="halo"></span><span class="btn-label">INITIATE 扫描</span>
          </button>
          <button id="stopBtn" class="ghost" type="button" disabled>中断</button>
        </div>
        <p class="notice">仅限已授权目标 · 本地 DVWA 靶场默认配置</p>
      </div>
    </aside>

    <section class="stack">
      <section class="panel terminal">
        <div class="panel-head">
          <span class="tick"></span>实时回传<em>TELEMETRY STREAM</em>
          <span class="spacer"></span>
          <span class="rec" id="rec"><i></i><b>IDLE</b></span>
          <span class="elapsed mono" id="elapsed">00:00</span>
        </div>
        <div class="term" id="term"></div>
      </section>

      <section class="panel intel">
        <div class="panel-head">
          <span class="tick"></span>提取情报<em>EXTRACTED INTELLIGENCE</em>
          <span class="spacer"></span>
          <span class="intel-count" id="intelCount"></span>
        </div>
        <div class="intel-body" id="intel">
          <div class="empty">
            <span class="pulse-dot"></span>等待遥测数据 · AWAITING TELEMETRY
          </div>
        </div>
      </section>
    </section>
  </main>

  <footer class="statusbar">
    <span>LINK <b>SECURE // 127.0.0.1</b></span>
    <span>JOB <b id="jobId">—</b></span>
    <span>MODE <b id="jobMode">—</b></span>
    <span>STATE <b id="jobState">STANDBY</b></span>
    <span class="right">SQL INJECTOR v1.0 · AUTHORIZED TESTING ONLY</span>
  </footer>
</div>

<script src="webui/app.js"></script>
</body>
</html>
    <?php
}
