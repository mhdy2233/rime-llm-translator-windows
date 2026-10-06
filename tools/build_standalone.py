import os
import sys
import shutil
import zipfile
import urllib.request
import io
if sys.stdout and hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "buffer"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(REPO_ROOT, "dist", "standalone")
OUTPUT_ZIP = os.path.join(REPO_ROOT, "rime-llm-translator-windows-standalone.zip")

EMBED_URLS = [
    "https://npmmirror.com/mirrors/python/3.10.11/python-3.10.11-embed-amd64.zip",
    "https://www.python.org/ftp/python/3.10.11/python-3.10.11-embed-amd64.zip"
]

def download_embed_python(cache_path):
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 5000000:
        print(f"[OK] 使用缓存的 Python 运行环境: {cache_path}")
        return True

    print("[*] 正在下载精简版 Python 运行环境 (约 8MB)...")
    for url in EMBED_URLS:
        try:
            print(f" -> 尝试源: {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp, open(cache_path, "wb") as f:
                shutil.copyfileobj(resp, f)
            if os.path.exists(cache_path) and os.path.getsize(cache_path) > 5000000:
                print(f"[OK] 下载成功 ({os.path.getsize(cache_path)} bytes)")
                return True
        except Exception as e:
            print(f" -> 源连接失败: {e}")
    return False

def build():
    print(f"[*] 项目根目录: {REPO_ROOT}")
    if os.path.exists(DIST_DIR):
        shutil.rmtree(DIST_DIR)
    os.makedirs(DIST_DIR, exist_ok=True)

    cache_dir = os.path.join(REPO_ROOT, "dist", "cache")
    os.makedirs(cache_dir, exist_ok=True)
    embed_zip = os.path.join(cache_dir, "python-3.10.11-embed-amd64.zip")

    if not download_embed_python(embed_zip):
        print("[错误] 无法下载 Python 运行环境包，构建中止！")
        sys.exit(1)

    print("[*] 正在复制项目核心文件...")
    for f in ["LICENSE", "README.md", "uninstall.bat"]:
        src = os.path.join(REPO_ROOT, f)
        if os.path.exists(src):
            shutil.copy(src, DIST_DIR)

    # 复制 rime-files
    rime_target = os.path.join(DIST_DIR, "rime-files")
    os.makedirs(rime_target, exist_ok=True)
    shutil.copy(os.path.join(REPO_ROOT, "rime-files", "rime_llm.lua"), rime_target)

    # 复制 daemon
    daemon_target = os.path.join(DIST_DIR, "daemon")
    os.makedirs(daemon_target, exist_ok=True)
    for df in ["config.json", "daemon.py", "stop_daemon.bat", "silent_start.vbs", "start_daemon.bat"]:
        src = os.path.join(REPO_ROOT, "daemon", df)
        if os.path.exists(src):
            shutil.copy(src, daemon_target)

    # 解压 Python 运行环境至 daemon/python
    print("[*] 正在解包内置 Python 运行环境至 daemon/python ...")
    py_dir = os.path.join(daemon_target, "python")
    os.makedirs(py_dir, exist_ok=True)
    with zipfile.ZipFile(embed_zip, "r") as z:
        z.extractall(py_dir)

    # 生成免安装独立版的 install.bat
    print("[*] 正在生成免安装版 install.bat ...")
    with open(os.path.join(REPO_ROOT, "install.bat"), "r", encoding="utf-8") as f:
        inst_content = f.read()

    standalone_inst = inst_content.replace(
        "python --version >nul 2>&1",
        "rem [独立版已内置免配置 Python 运行环境]"
    ).replace(
        'if %errorlevel% neq 0 (\n    echo [错误] 未检测到 Python 3 环境！\n    echo 本插件后台轻量服务依赖 Python 3，请先安装 Python 3 (https://www.python.org/)\n    echo 安装时请务必勾选 "Add python.exe to PATH"，安装后重试。\n    pause\n    exit /b 1\n)',
        "rem 已内置免配置 Python 运行环境"
    ).replace(
        'if not exist "%TARGET_DAEMON%\\config.json" (\n    copy /y daemon\\config.json "%TARGET_DAEMON%\\" >nul\n)',
        'if not exist "%TARGET_DAEMON%\\config.json" (\n    copy /y daemon\\config.json "%TARGET_DAEMON%\\" >nul\n)\nif exist "daemon\\python" (\n    if not exist "%TARGET_DAEMON%\\python" mkdir "%TARGET_DAEMON%\\python"\n    xcopy /e /y /q "daemon\\python\\*" "%TARGET_DAEMON%\\python\\" >nul\n)'
    ).replace(
        'python -c "',
        '"%TARGET_DAEMON%\\python\\python.exe" -c "'
    )

    with open(os.path.join(DIST_DIR, "install.bat"), "w", encoding="utf-8") as f:
        f.write(standalone_inst)

    # 打包为发布 ZIP
    print(f"[*] 正在生成独立发布压缩包: {OUTPUT_ZIP} ...")
    if os.path.exists(OUTPUT_ZIP):
        os.remove(OUTPUT_ZIP)

    with zipfile.ZipFile(OUTPUT_ZIP, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for root, dirs, files in os.walk(DIST_DIR):
            for file in files:
                full = os.path.join(root, file)
                rel = os.path.relpath(full, DIST_DIR)
                z.write(full, arcname=rel)

    print(f"[SUCCESS] 独立免安装包打包完成！文件大小: {os.path.getsize(OUTPUT_ZIP)} 字节")

if __name__ == "__main__":
    build()
