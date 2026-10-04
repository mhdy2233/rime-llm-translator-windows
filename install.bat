@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo   欢迎安装 Rime LLM Translator (Windows / 小狼毫版本)
echo ============================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python 3 环境！
    echo 本插件后台轻量服务依赖 Python 3，请先安装 Python 3 (https://www.python.org/)
    echo 安装时请务必勾选 "Add python.exe to PATH"，安装后重试。
    pause
    exit /b 1
)

set TARGET_DAEMON=%APPDATA%\rime-llm-daemon
set TARGET_RIME=%APPDATA%\Rime

echo [1/5] 部署守护进程至 %TARGET_DAEMON% ...
if not exist "%TARGET_DAEMON%" mkdir "%TARGET_DAEMON%"
copy /y daemon\daemon.py "%TARGET_DAEMON%\" >nul
copy /y daemon\start_daemon.bat "%TARGET_DAEMON%\" >nul
copy /y daemon\stop_daemon.bat "%TARGET_DAEMON%\" >nul
if not exist "%TARGET_DAEMON%\config.json" (
    copy /y daemon\config.json "%TARGET_DAEMON%\" >nul
)

echo [2/5] 部署 Lua 插件至 %TARGET_RIME%\lua ...
if not exist "%TARGET_RIME%\lua" mkdir "%TARGET_RIME%\lua"
copy /y rime-files\rime_llm.lua "%TARGET_RIME%\lua\" >nul

echo [3/5] 打开配置文件，请在记事本中填入你的 API Key 并保存...
echo (保存并关闭记事本窗口后，安装将自动继续)
notepad "%TARGET_DAEMON%\config.json"

echo [4/5] 自动配置输入法方案补丁 (万象/雾凇/朙月)...
python -c "
import os
rime_dir = os.path.expandvars(r'%APPDATA%\Rime')
schemes = ['wanxiang.custom.yaml', 'rime_ice.custom.yaml', 'luna_pinyin.custom.yaml']
for s in schemes:
    fp = os.path.join(rime_dir, s)
    if os.path.exists(fp):
        with open(fp, 'r', encoding='utf-8') as f:
            content = f.read()
        updates = []
        if 'rime_llm' not in content:
            updates.append('  \"engine/translators/@before 0\": lua_translator@*rime_llm')
        if 'llm_pinyin' not in content:
            updates.append('  \"recognizer/patterns/llm_pinyin\": \"^[a-zA-Z]+:.*$\"')
        if 'speller/alphabet' not in content and 'wanxiang' in s:
            updates.append('  \"speller/alphabet\": \"zyxwvutsrqponmlkjihgfedcbaZYXWVUTSRQPONMLKJIHGFEDCBA1234567890`;/\\\\:\"')
        if updates:
            with open(fp, 'a', encoding='utf-8') as f:
                f.write('\n' + '\n'.join(updates) + '\n')
            print(f'[OK] 已为 {s} 写入补丁配置')
" 2>nul

echo [5/5] 正在重新部署小狼毫输入法...
set DEPLOYER=
for /d %%D in ("%ProgramFiles%\Rime\weasel-*") do (
    if exist "%%D\WeaselDeployer.exe" set DEPLOYER=%%D\WeaselDeployer.exe
)
if not defined DEPLOYER (
    if exist "%ProgramFiles(x86)%\Rime\weasel\WeaselDeployer.exe" set DEPLOYER=%ProgramFiles(x86)%\Rime\weasel\WeaselDeployer.exe
)

if defined DEPLOYER (
    echo 正在执行部署：%DEPLOYER% /deploy ...
    start "" /wait "%DEPLOYER%" /deploy
    echo [OK] 重新部署完成！
) else (
    echo [提示] 未找到 WeaselDeployer.exe，请在系统托盘右键小狼毫图标，点击【重新部署】生效。
)

echo.
echo 启动后台守护服务...
call "%TARGET_DAEMON%\start_daemon.bat"

echo.
echo ============================================================
echo   恭喜！安装已完成。
echo   - 常规输入：打完拼音输入 vv，AI 自动纠错并提供前3个候选！
echo   - 智能问答：输入 call:1+1dengyujivv 直接出答案
echo   - 英语翻译：输入 eng:woshizhongguorenvv
echo   - 日语翻译：输入 jp:woshizhongguorenvv
echo ============================================================
pause
