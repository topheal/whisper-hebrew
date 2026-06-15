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

העתק את תיקיית `.claude/skills/transcribe` לתוך `~/.claude/skills/` שלך.

אחר כך פשוט כתוב לקלוד: **"תמלל לי את הקובץ..."**
