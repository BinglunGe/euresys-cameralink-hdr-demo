@echo off
setlocal

rem ============================================================
rem  VC-71MC-M4 camera toolkit launcher
rem    run.bat                  -> GUI
rem    run.bat hdr              -> HDR merge
rem    run.bat snap             -> single frame
rem    run.bat control --temp   -> read temperature
rem    run.bat smoke            -> GUI smoke test
rem  (.bat must use CRLF; kept ASCII for cmd parser safety)
rem ============================================================

set "ROOT=%~dp0"
set "PY=%ROOT%.venv\Scripts\python.exe"

rem isolate the venv from any inherited PYTHONPATH
set "PYTHONPATH="

if not exist "%PY%" (
    echo [ERROR] venv not found: %PY%
    echo Create it first:
    echo     py -3.12 -m venv .venv
    echo     .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

rem first arg = command alias (default gui); remaining args forwarded
set "CMD=%~1"
if "%CMD%"=="" set "CMD=gui"
shift

set "SCRIPT="
if /i "%CMD%"=="gui"      set "SCRIPT=vc71_gui.py"
if /i "%CMD%"=="hdr"      set "SCRIPT=vc71_hdr.py"
if /i "%CMD%"=="snap"     set "SCRIPT=vc71_snapshot.py"
if /i "%CMD%"=="snapshot" set "SCRIPT=vc71_snapshot.py"
if /i "%CMD%"=="control"  set "SCRIPT=vc71_control.py"
if /i "%CMD%"=="smoke"    set "SCRIPT=..\tests\smoke_gui.py"
if "%SCRIPT%"=="" set "SCRIPT=%CMD%"

cd /d "%ROOT%src"
echo [run.bat] python %SCRIPT% %1 %2 %3 %4 %5 %6 %7 %8 %9
"%PY%" "%SCRIPT%" %1 %2 %3 %4 %5 %6 %7 %8 %9
set "RC=%ERRORLEVEL%"

if /i "%CMD%"=="gui" (
    if not "%RC%"=="0" ( echo. & echo [run.bat] exit code %RC% & pause )
) else (
    echo.
    pause
)
endlocal
