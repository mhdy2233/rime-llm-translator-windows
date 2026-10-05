@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo   正在卸载 Rime LLM Translator...
echo ============================================================
echo.

set TARGET_DAEMON=%APPDATA%\rime-llm-daemon
set TARGET_RIME=%APPDATA%\Rime

echo [1/4] 停止后台守护进程...
if exist "%TARGET_DAEMON%\stop_daemon.bat" (
    call "%TARGET_DAEMON%\stop_daemon.bat"
)
taskkill /f /im pythonw.exe >nul 2>&1

echo [2/5] 清理 Windows 开机自启动注册表项...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "RimeLLMTranslatorDaemon" /f >nul 2>&1

echo [2/4] 清理守护进程与缓存目录...
if exist "%TARGET_DAEMON%" rd /s /q "%TARGET_DAEMON%"
if exist "%TEMP%\rime_llm_ipc" rd /s /q "%TEMP%\rime_llm_ipc"

echo [3/4] 移除 Lua 插件文件...
if exist "%TARGET_RIME%\lua\rime_llm.lua" del /f /q "%TARGET_RIME%\lua\rime_llm.lua"

echo [4/4] 正在重新部署小狼毫输入法...
set DEPLOYER=
for /d %%D in ("%ProgramFiles%\Rime\weasel-*") do (
    if exist "%%D\WeaselDeployer.exe" set DEPLOYER=%%D\WeaselDeployer.exe
)
if not defined DEPLOYER (
    if exist "%ProgramFiles(x86)%\Rime\weasel\WeaselDeployer.exe" set DEPLOYER=%ProgramFiles(x86)%\Rime\weasel\WeaselDeployer.exe
)

if defined DEPLOYER (
    start "" /wait "%DEPLOYER%" /deploy
    echo [OK] 重新部署完成！
) else (
    echo [提示] 请手动点击右下角小狼毫托盘图标【重新部署】。
)

echo.
echo ============================================================
echo   卸载完成！输入法已恢复至纯净状态。
echo ============================================================
pause
