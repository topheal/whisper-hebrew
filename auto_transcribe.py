"""
תמלול אוטומטי לתיקיות מוגדרות (SRT) + סיכום אופציונלי עם Claude Code (headless, ללא מפתח API)
ברירת המחדל לכל תיקייה: רק SRT (מנוע מקומי). סיכום מופעל לפי הדגל summarize בקובץ ההגדרות.
שימוש: python auto_transcribe.py            (סריקה חד-פעמית, מכבד עדיפות תיקיות)
       python auto_transcribe.py --loop      (סריקה חוזרת לפי scan_interval_minutes)
"""

import sys
import os
import re
import time
import subprocess
import yaml
from pathlib import Path
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from faster_whisper import WhisperModel

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CONFIG_PATH = Path(__file__).parent / "config.yaml"

AUDIO_EXT_PRIORITY = ["mp3", "wav", "m4a", "ogg", "flac", "aac", "wma", "mp4", "webm", "mkv"]
RAW_TAG_RE = re.compile(r"(?i)\braw\b")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def is_stable(path: Path, wait=3.0) -> bool:
    """בודק שהקובץ לא משתנה (שלא באמצע סנכרון מ-Google Drive)"""
    try:
        size1 = path.stat().st_size
        time.sleep(wait)
        size2 = path.stat().st_size
        return size1 == size2 and size1 > 0
    except FileNotFoundError:
        return False


def find_media_groups(folder: Path, recursive: bool, extensions: list[str], maxdays: float | None = None) -> list[Path]:
    """מאתר קבצי מדיה בתיקייה, מאחד audio+video עם אותו שם לקובץ אחד"""
    pattern = "**/*" if recursive else "*"
    candidates = [p for p in folder.glob(pattern) if p.is_file() and p.suffix.lower().lstrip(".") in extensions]
    candidates = [p for p in candidates if not RAW_TAG_RE.search(p.stem)]

    if maxdays is not None:
        cutoff = time.time() - maxdays * 86400
        candidates = [p for p in candidates if p.stat().st_mtime >= cutoff]

    groups: dict[str, list[Path]] = {}
    for p in candidates:
        key = str(p.with_suffix(""))
        groups.setdefault(key, []).append(p)

    chosen = []
    for key, files in groups.items():
        files.sort(key=lambda p: AUDIO_EXT_PRIORITY.index(p.suffix.lower().lstrip("."))
                    if p.suffix.lower().lstrip(".") in AUDIO_EXT_PRIORITY else 99)
        chosen.append(files[0])
    return chosen


def outputs_for(media_path: Path) -> tuple[Path, Path]:
    srt_path = media_path.with_suffix(".srt")
    summary_path = media_path.parent / f"{media_path.stem}_summary.txt"
    return srt_path, summary_path


def needs_processing(media_path: Path, summarize: bool) -> bool:
    srt_path, summary_path = outputs_for(media_path)
    media_mtime = media_path.stat().st_mtime

    if not srt_path.exists() or srt_path.stat().st_mtime < media_mtime:
        return True
    if summarize and (not summary_path.exists() or summary_path.stat().st_mtime < media_mtime):
        return True
    return False


def format_srt_timestamp(seconds: float) -> str:
    td = timedelta(seconds=seconds)
    total_ms = int(td.total_seconds() * 1000)
    hours, rem = divmod(total_ms, 3600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def transcribe_to_srt(model: WhisperModel, media_path: Path) -> tuple[Path, str]:
    segments, info = model.transcribe(
        str(media_path),
        language="he",
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )

    srt_lines = []
    full_text_lines = []
    for i, seg in enumerate(segments, start=1):
        start = format_srt_timestamp(seg.start)
        end = format_srt_timestamp(seg.end)
        text = seg.text.strip()
        srt_lines.append(f"{i}\n{start} --> {end}\n{text}\n")
        full_text_lines.append(text)

    srt_path, _ = outputs_for(media_path)
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
    return srt_path, "\n".join(full_text_lines)


def summarize_with_claude(text: str) -> str:
    """מפעיל את Claude Code במצב headless (claude -p) - דרך המנוי הקיים, בלי מפתח API נפרד"""
    prompt = (
        "להלן תמלול שיחה בעברית. סכם אותה בקצרה: נושא השיחה, נקודות מרכזיות, "
        "החלטות שהתקבלו ומשימות להמשך (אם יש). כתוב בעברית, בפורמט נקודות, בלי הקדמות.\n\n"
        f"תמלול:\n{text}"
    )

    result = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    if result.returncode != 0:
        return f"(סיכום נכשל: {result.stderr.strip()})"
    return result.stdout.strip()


def process_file(media_path: Path, model_size: str, summarize: bool):
    print(f"[{media_path.name}] טוען מודל ומתמלל...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    srt_path, full_text = transcribe_to_srt(model, media_path)
    print(f"[{media_path.name}] תמלול נשמר: {srt_path.name}")

    if not summarize:
        return

    print(f"[{media_path.name}] מסכם עם Claude Code...")
    summary = summarize_with_claude(full_text)
    _, summary_path = outputs_for(media_path)
    summary_path.write_text(summary, encoding="utf-8")
    print(f"[{media_path.name}] סיכום נשמר: {summary_path.name}")


def run_scan():
    config = load_config()
    extensions = config.get("extensions", [])
    max_parallel = config.get("max_parallel", 1)
    model_size = config.get("model_size", "medium")

    queue: list[tuple[Path, bool]] = []
    for folder_cfg in config.get("folders") or []:
        folder = Path(folder_cfg["path"])
        recursive = folder_cfg.get("recursive", True)
        summarize = folder_cfg.get("summarize", False)
        maxdays = folder_cfg.get("maxdays")
        if not folder.exists():
            print(f"אזהרה: התיקייה לא נמצאה: {folder}")
            continue

        folder_files = [
            media_path
            for media_path in find_media_groups(folder, recursive, extensions, maxdays)
            if needs_processing(media_path, summarize) and is_stable(media_path)
        ]
        folder_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        queue.extend((media_path, summarize) for media_path in folder_files)

    if not queue:
        print("אין קבצים חדשים לתמלל.")
        return

    print(f"נמצאו {len(queue)} קבצים לתמלול (לפי סדר עדיפות התיקיות, ובתוך כל תיקייה - החדשים ביותר ראשון).")

    with ThreadPoolExecutor(max_workers=max_parallel) as executor:
        futures = [executor.submit(process_file, p, model_size, summarize) for p, summarize in queue]
        for f in futures:
            f.result()

    print("הסריקה הושלמה.")


def main():
    if "--loop" in sys.argv:
        config = load_config()
        interval = config.get("scan_interval_minutes", 60) * 60
        while True:
            run_scan()
            print(f"מחכה {interval // 60} דקות לסריקה הבאה...")
            time.sleep(interval)
    else:
        run_scan()


if __name__ == "__main__":
    main()
