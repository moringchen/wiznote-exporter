@echo off
chcp 65001 >nul
echo ============================================
echo WizNote 为知笔记导出工具
echo ============================================
echo.

WizNote导出工具.exe

if errorlevel 1 (
    echo.
    echo 运行出错，请查看错误信息
    pause
)
