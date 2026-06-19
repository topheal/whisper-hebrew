@echo off
chcp 65001 >nul
echo רושם משימה מתוזמנת ב-Windows Task Scheduler...
echo המשימה תרוץ כל שעה, ברקע, ללא חלון.

schtasks /create /tn "WhisperHebrewAutoTranscribe" ^
  /tr "\"%~dp0scan_silent.bat\"" ^
  /sc HOURLY /mo 1 /f

if %errorlevel% == 0 (
    echo.
    echo נרשם בהצלחה! המשימה "WhisperHebrewAutoTranscribe" רצה כל שעה.
    echo להסרה: schtasks /delete /tn "WhisperHebrewAutoTranscribe" /f
    echo לוג ריצות: scan_log.txt בתיקייה הזו
) else (
    echo שגיאה ברישום המשימה.
)
pause
