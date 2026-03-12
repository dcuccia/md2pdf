@echo off
REM Markdown to PDF Converter
REM Converts .md files to styled PDF via HTML intermediate.
REM Never overwrites — auto-increments filename suffix (_1, _2, ...).
REM
REM Usage:
REM   md2pdf.bat "path\to\file.md"           Convert a specific file
REM   md2pdf.bat                              Convert all .md files in parent directory
REM   md2pdf.bat -ImageScale 400              Use larger header images
REM   md2pdf.bat -Theme themes\academic.css   Use a different theme
REM
REM First run installs dependencies (Python markdown, Playwright) if missing.

PowerShell -ExecutionPolicy Bypass -File "%~dp0md2pdf.ps1" %*
