@echo off
rem dsh-ctl wrapper: bypasses execution policy, forwards all args.
rem Usage: ctl.cmd -Action windows
rem        ctl.cmd -Action type -Title "Notepad" -Text "hello"
setlocal
chcp 65001 >nul
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%~dp0dsh-ctl.ps1" %*
endlocal
