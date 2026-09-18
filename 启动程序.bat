@echo off
chcp 65001 >nul 2>nul
cd /d "%~dp0"
title Component Inventory

rem ============================================================
rem  Locate a Python interpreter that can run tkinter.
rem  Priority: known-good path -> PATH -> common install dirs
rem ============================================================
set "PYW="

call :try "D:\python\pythonw.exe"

if not defined PYW (
  for /f "delims=" %%i in ('where pythonw.exe 2^>nul') do (
    if not defined PYW call :try "%%i"
  )
)

for %%D in (
  "%LOCALAPPDATA%\Programs\Python\Python313"
  "%LOCALAPPDATA%\Programs\Python\Python312"
  "%LOCALAPPDATA%\Programs\Python\Python311"
  "%LOCALAPPDATA%\Programs\Python\Python310"
  "%LOCALAPPDATA%\Programs\Python\Python39"
  "C:\Python313"
  "C:\Python312"
  "C:\Python311"
  "C:\Python310"
  "C:\Python39"
) do (
  if not defined PYW call :try "%%~D\pythonw.exe"
)

if not defined PYW (
  echo.
  echo   [ERROR] No suitable Python found.
  echo.
  echo   This program needs Python 3.7+ with tkinter.
  echo   Install Python from https://www.python.org/downloads/
  echo   and tick "tcl/tk and IDLE" during setup.
  echo.
  pause
  exit /b 1
)

start "" "%PYW%" "%~dp0main.py"
exit /b 0

rem ---- helper: accept candidate only if its python.exe can import tkinter
:try
if defined PYW goto :eof
if not exist %1 goto :eof
set "CAND=%~1"
set "CAND_EXE=%CAND:pythonw.exe=python.exe%"
if not exist "%CAND_EXE%" set "CAND_EXE=%CAND%"
"%CAND_EXE%" -c "import tkinter" >nul 2>nul
if errorlevel 1 goto :eof
set "PYW=%CAND%"
goto :eof
