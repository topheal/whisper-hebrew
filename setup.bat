@echo off
chcp 65001 >nul
echo.
echo ================================
echo  התקנת מערכת תמלול עברית
echo ================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo שגיאה: Python לא מותקן.
    echo הורד מ: https://www.python.org/downloads/
    echo חשוב: סמן "Add Python to PATH" בהתקנה
    pause
    exit /b 1
)

ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo אזהרה: ffmpeg לא נמצא ב-PATH.
    echo הורד מ: https://www.gyan.dev/ffmpeg/builds/
    echo חלץ והוסף את תיקיית bin ל-PATH של Windows
    echo.
    echo ניתן להמשיך, אך ייתכן שקבצי וידאו לא יעבדו.
    pause
)

echo מתקין faster-whisper...
pip install -r requirements.txt

echo.
echo ההתקנה הושלמה!
echo להפעלה: לחץ פעמיים על transcribe_gui.py
echo.
pause
