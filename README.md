# תמלול עברית מקומי עם Whisper

תמלול קבצי אודיו ווידאו לעברית — **מקומי, חינמי, ללא אינטרנט בשימוש**.

מבוסס על [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — גרסה מהירה פי 4 מ-Whisper המקורי.

---

## דרישות

- Python 3.8+
- ffmpeg

### התקנת ffmpeg (Windows)
1. הורד מ-[gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) — בחר `ffmpeg-release-essentials.zip`
2. חלץ לתיקייה כגון `C:\ffmpeg`
3. הוסף `C:\ffmpeg\bin` ל-PATH של Windows

---

## התקנה

```bash
git clone https://github.com/topheal/whisper-hebrew.git
cd whisper-hebrew
pip install -r requirements.txt
```

או הרץ את `setup.bat` (Windows בלבד).

---

## שימוש

### ממשק גרפי (מומלץ)
```bash
python transcribe_gui.py
```
לחץ על הכפתור הירוק, בחר קובץ — וזהו.

### שורת פקודה
```bash
python transcribe.py "נתיב/לקובץ.mp3"
```

הפלט נשמר אוטומטית כקובץ `.txt` באותה תיקייה של הקובץ המקורי.

---

## פורמטים נתמכים

`mp3` `mp4` `wav` `m4a` `ogg` `flac` `webm` `mkv` `aac` `wma`

---

## מודלים

| מודל | גודל | דיוק בעברית | מהירות |
|------|------|------------|--------|
| `small` | 500MB | סביר | מהיר מאוד |
| `medium` | 1.5GB | **טוב (ברירת מחדל)** | מהיר |
| `large-v3` | 3GB | מצוין | איטי יותר |

לשינוי מודל — ערוך את `MODEL_SIZE` בתחילת `transcribe.py`.

---

## שימוש עם Claude Code

העתק את תיקיות `.claude/skills/transcribe` ו-`.claude/skills/auto-transcribe` לתוך `~/.claude/skills/` שלך.

אחר כך פשוט כתוב לקלוד: **"תמלל לי את הקובץ..."** או **"סרוק את התיקיות"**

---

## תמלול אוטומטי לתיקיות (Google Drive ועוד)

מערכת שסורקת תיקיות מוגדרות ומתמללת קבצים חדשים אוטומטית. לכל תיקייה אפשר לבחור בנפרד:
- `<שם>.srt` — תמלול מלא עם תזמונים מדויקים (**ברירת מחדל** - מנוע מקומי, Whisper, בלי Claude)
- `<שם>_summary.txt` — בנוסף, סיכום שמופק ע"י Claude Code (headless, דרך המנוי הקיים - בלי מפתח API נפרד ובלי עלות נוספת) - רק אם הופעל לתיקייה הזו

### הגדרה

ערוך את `config.yaml`:
```yaml
folders:
  # תיקייה רגילה - רק SRT (ברירת מחדל, אין צורך לכתוב summarize בכלל), עד 30 יום אחורה
  - path: 'G:\האחסון שלי\שיחות מוקלטות'
    recursive: true
    maxdays: 30

  # תיקייה עם סיכום אוטומטי בנוסף ל-SRT, בלי הגבלת גיל קבצים
  - path: 'C:\Users\you\Downloads\שיחות חשובות'
    recursive: false
    summarize: true

scan_interval_minutes: 60   # תדירות סריקה ברקע
max_parallel: 1              # כמה קבצים לתמלל במקביל
model_size: medium
```
שימוש בגרשיים יחידים `'...'` מאפשר להעתיק נתיב ישירות ממנהל הקבצים של Windows בלי לשנות אותו (גרשיים כפולים `"..."` דורשים הכפלת כל `\`).

סדר התיקיות ברשימה = סדר עדיפות (הראשונה מטופלת ראשונה).

`summarize: true` מפעיל סיכום אוטומטי לתיקייה הזו, דרך `claude -p` (Claude Code headless) - דורש שה-CLI מותקן ומחובר (`claude --version` עובד תקין). בלי הדגל - רק SRT, מהיר יותר וללא תלות ב-Claude.

`maxdays: N` מגביל את התיקייה הזו לקבצים שהשתנו ב-N הימים האחרונים בלבד (לפי תאריך שינוי הקובץ). בלי הדגל - כל הקבצים בתיקייה נסרקים, בלי הגבלת גיל.

### הרצה

**חד-פעמית, על פי דרישה:**
```bash
python auto_transcribe.py
```
או הרץ `scan_now.bat`.

**ברקע, אוטומטית כל שעה (Windows Task Scheduler):**
```bash
register_task.bat
```
להסרה: `schtasks /delete /tn "WhisperHebrewAutoTranscribe" /f`

### התנהגות
- קובץ אודיו וקובץ וידאו עם אותו שם — מתומלל פעם אחת בלבד (מועדף אודיו, מהיר יותר)
- קבצים שכבר תומללו (יש להם `.srt` עדכני, ו-`_summary.txt` עדכני אם `summarize: true`) מדולגים
- קבצים שבתהליך סנכרון (Google Drive) מדולגים ויטופלו בסריקה הבאה
