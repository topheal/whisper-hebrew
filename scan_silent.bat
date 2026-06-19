@echo off
cd /d "%~dp0"
"C:\Users\admin\AppData\Local\Programs\Python\Python312\pythonw.exe" auto_transcribe.py >> scan_log.txt 2>&1
