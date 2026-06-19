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

מערכת שסורקת תיקיות מוגדרות, מתמללת קבצים חדשים אוטומטית, ומפיקה לכל קובץ:
- `<שם>.srt` — תמלול מלא עם תזמונים מדויקים
- `<שם>_summary.txt` — סיכום שמופק ע"י Claude Code (headless, דרך המנוי הקיים - בלי מפתח API נפרד ובלי עלות נוספת)

### הגדרה

ערוך את `config.yaml`:
```yaml
folders:
  - path: 'G:\האחסון שלי\שיחות מוקלטות'
    recursive: true
  - path: 'C:\Users\you\Downloads'
    recursive: false

scan_interval_minutes: 60   # תדירות סריקה ברקע
max_parallel: 1              # כמה קבצים לתמלל במקביל
model_size: medium
```
שימוש בגרשיים יחידים `'...'` מאפשר להעתיק נתיב ישירות ממנהל הקבצים של Windows בלי לשנות אותו (גרשיים כפולים `"..."` דורשים הכפלת כל `\`).

סדר התיקיות ברשימה = סדר עדיפות (הראשונה מטופלת ראשונה).

הסיכום האוטומטי מופק ע"י הפעלת `claude -p` (Claude Code headless) - דורש שה-CLI מותקן ומחובר (`claude --version` עובד תקין).

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
- קבצים שכבר תומללו (יש להם `.srt` + `_summary.txt` עדכניים) מדולגים
- קבצים שבתהליך סנכרון (Google Drive) מדולגים ויטופלו בסריקה הבאה
