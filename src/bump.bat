@echo off
:: Delphi 版本号升级工具快捷启动器
:: 用法: bump <项目目录> [版本号]
:: 示例: bump 10_2503_6        (自动+1)
::       bump 10_2503_6 10     (设置为10)
::       bump 10_2503_6 -n     (预览模式)

setlocal
cd /d "%~dp0"

if "%~1"=="" (
    echo.
    echo   Delphi 版本号升级工具
    echo   =====================
    echo.
    echo   用法: bump ^<项目目录^> [选项]
    echo.
    echo   选项:
    echo     ^<数字^>    指定新的 Build 号
    echo     -n        预览模式，不实际修改
    echo     --help    显示详细帮助
    echo.
    echo   示例:
    echo     bump 10_2503_6           自动将 Build +1
    echo     bump 10_2503_6 10        将 Build 设置为 10
    echo     bump 10_2503_6 -n        预览模式
    echo     bump .\MyProject         处理当前目录下的项目
    echo.
    exit /b 0
)

:: 检查是否是帮助请求
if "%~1"=="--help" (
    python "%~dp0version_bumper.py" --help
    exit /b 0
)
if "%~1"=="-h" (
    python "%~dp0version_bumper.py" --help
    exit /b 0
)

:: 解析参数
set "PROJECT=%~1"
set "OPTION=%~2"

:: 检查第二个参数
if "%OPTION%"=="" (
    :: 只有项目路径，自动+1
    python "%~dp0version_bumper.py" "%PROJECT%"
) else if "%OPTION%"=="-n" (
    :: 预览模式
    python "%~dp0version_bumper.py" "%PROJECT%" --dry-run
) else if "%OPTION%"=="--dry-run" (
    :: 预览模式
    python "%~dp0version_bumper.py" "%PROJECT%" --dry-run
) else (
    :: 假设是版本号
    python "%~dp0version_bumper.py" "%PROJECT%" --build %OPTION%
)

endlocal
