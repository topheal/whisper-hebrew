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
import shutil
import subprocess
import tempfile
import wave
import winreg
import yaml
import numpy as np
import torch
from pathlib import Path
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from faster_whisper import WhisperModel

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Windows: מונע פתיחת חלון קונסולה שחור לכל תהליך-בן
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

CONFIG_PATH = Path(__file__).parent / "config.yaml"
CONFIG_DEFAULT_PATH = Path(__file__).parent / "config-default.yaml"
LOCK_PATH = Path(__file__).parent / "scan.lock"
STALE_LOCK_HOURS = 6  # אם סריקה קודמת "תקועה" יותר מזה - מתעלמים מהנעילה ומתחילים בכל זאת

AUDIO_EXT_PRIORITY = ["mp3", "wav", "m4a", "ogg", "flac", "aac", "wma", "mp4", "webm", "mkv"]
VIDEO_EXTENSIONS = {"mp4", "webm", "mkv"}
RAW_TAG_RE = re.compile(r"(?i)\braw\b")


def acquire_lock() -> bool:
    """מונע סריקה כפולה במקביל (לדוגמה: scan_now.bat הופעל בזמן שסריקה מתוזמנת עדיין רצה)"""
    if LOCK_PATH.exists():
        age_hours = (time.time() - LOCK_PATH.stat().st_mtime) / 3600
        if age_hours < STALE_LOCK_HOURS:
            return False
        print(f"נמצא קובץ נעילה ישן ({age_hours:.1f} שעות) - מתעלם ומתחיל סריקה חדשה")
    LOCK_PATH.write_text(str(os.getpid()), encoding="utf-8")
    return True


def release_lock():
    try:
        LOCK_PATH.unlink()
    except FileNotFoundError:
        pass


def load_config():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(CONFIG_DEFAULT_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"נוצר {CONFIG_PATH.name} מהתבנית - ערוך אותו והגדר את התיקיות שלך לפני הרצה נוספת.")
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

    if maxdays is not None and maxdays != "all":
        cutoff = time.time() - float(maxdays) * 86400
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
    summary_path = media_path.parent / f"{media_path.stem}_summary.md"
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


def format_minsec(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}:{secs:02d}"


def transcribe_to_srt(
    model: WhisperModel, media_path: Path, speaker_turns: list[tuple[float, float, str]] | None = None
) -> tuple[Path, str]:
    segments, info = model.transcribe(
        str(media_path),
        language="he",
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )

    unique_speakers = {label for _, _, label in speaker_turns} if speaker_turns else set()
    active_turns = speaker_turns if len(unique_speakers) >= 2 else None
    prev_speaker: str | None = None

    srt_lines = []
    timestamped_lines = []
    for i, seg in enumerate(segments, start=1):
        start = format_srt_timestamp(seg.start)
        end = format_srt_timestamp(seg.end)
        text = seg.text.strip()
        if active_turns:
            speaker = speaker_for_segment(active_turns, seg.start, seg.end)
            if speaker and speaker != prev_speaker:
                text = f"{speaker}: {text}"
                prev_speaker = speaker
        srt_lines.append(f"{i}\n{start} --> {end}\n{text}\n")
        timestamped_lines.append(f"[{format_minsec(seg.start)}] {text}")

    srt_path, _ = outputs_for(media_path)
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")
    return srt_path, "\n".join(timestamped_lines)


def extract_audio_file(video_path: Path) -> Path:
    """מחלץ פס קול מקובץ וידאו ל-mp3 לצידו, באמצעות ffmpeg (לא לצורך התמלול - לנוחות האזנה)"""
    audio_path = video_path.with_suffix(".mp3")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(video_path), "-vn", "-acodec", "libmp3lame", "-q:a", "4", str(audio_path)],
        capture_output=True,
        check=True,
        creationflags=_NO_WINDOW,
    )
    return audio_path


def get_hf_token() -> str | None:
    """מאחזר HF_TOKEN ממשתני סביבה, ואם לא נמצא - מהרישום (סשנים ישנים לא תמיד רואים משתנה שנוסף אחרי שנפתחו)"""
    token = os.environ.get("HF_TOKEN")
    if token:
        return token
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            return winreg.QueryValueEx(key, "HF_TOKEN")[0]
    except (FileNotFoundError, OSError):
        return None


def setup_device() -> tuple[str, str]:
    """בודק אם יש GPU עם מספיק VRAM. מתקין PyTorch+CUDA אוטומטית אם צריך ומאתחל מחדש.
    מחזיר (device, compute_type) — 'cuda'/'float16' אם GPU זמין, 'cpu'/'int8' אחרת."""
    try:
        smi = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
            creationflags=_NO_WINDOW,
        )
        if smi.returncode != 0:
            return "cpu", "int8"
        name, vram_str = smi.stdout.strip().split("\n")[0].rsplit(",", 1)
        gpu_name, vram_mb = name.strip(), int(vram_str.strip())
    except Exception:
        return "cpu", "int8"

    if vram_mb < 2000:
        print(f"GPU {gpu_name} ({vram_mb}MB VRAM) — VRAM לא מספיק, עובד עם CPU")
        return "cpu", "int8"

    if not torch.cuda.is_available():
        print(f"GPU {gpu_name} ({vram_mb // 1024}GB VRAM) — מתקין PyTorch+CUDA (כ-2GB, פעם אחת בלבד)...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--quiet", "--upgrade",
             "torch", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cu124"],
            check=True,
            creationflags=_NO_WINDOW,
        )
        print("התקנה הושלמה — מאתחל מחדש...")
        subprocess.Popen([sys.executable] + sys.argv, creationflags=_NO_WINDOW)
        sys.exit(0)

    print(f"GPU: {gpu_name} ({vram_mb // 1024}GB VRAM) — CUDA פעיל")
    return "cuda", "float16"


_diarization_pipeline = None


def get_diarization_pipeline(device: str = "cpu"):
    """טוען את צינור זיהוי הדוברים פעם אחת בלבד (טעינה איטית), ומשתמש בו חזרה לכל הקבצים בסריקה"""
    global _diarization_pipeline
    if _diarization_pipeline is None:
        token = get_hf_token()
        if not token:
            raise RuntimeError(
                "לא נמצא HF_TOKEN - נדרש לזיהוי דוברים. ראה הוראות התקנה ב-README."
            )
        from pyannote.audio import Pipeline
        _diarization_pipeline = Pipeline.from_pretrained(
            "ivrit-ai/pyannote-speaker-diarization-3.1", token=token
        )
        if device == "cuda":
            _diarization_pipeline = _diarization_pipeline.to(torch.device("cuda"))
    return _diarization_pipeline


def decode_to_waveform(media_path: Path) -> tuple["torch.Tensor", int]:
    """מפענח קובץ מדיה ל-waveform בזיכרון דרך ffmpeg, בלי תלות ב-torchcodec (שבור על Windows)"""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = Path(tmp.name)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(media_path), "-ar", "16000", "-ac", "1", "-f", "wav", str(wav_path)],
            capture_output=True,
            check=True,
            creationflags=_NO_WINDOW,
        )
        with wave.open(str(wav_path), "rb") as wf:
            sample_rate = wf.getframerate()
            raw = wf.readframes(wf.getnframes())
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        waveform = torch.from_numpy(data).unsqueeze(0)
        return waveform, sample_rate
    finally:
        wav_path.unlink(missing_ok=True)


def diarize_audio(media_path: Path, device: str = "cpu") -> list[tuple[float, float, str]]:
    """מחזיר רשימת טווחי זמן לפי דובר: [(start, end, 'דובר א'), ...], מסודר כרונולוגית"""
    pipeline = get_diarization_pipeline(device)
    waveform, sample_rate = decode_to_waveform(media_path)
    result = pipeline({"waveform": waveform, "sample_rate": sample_rate})

    raw_turns = sorted(
        result.speaker_diarization.itertracks(yield_label=True),
        key=lambda item: item[0].start,
    )
    label_names = {}
    hebrew_letters = "אבגדהוזחטיכלמנסעפצקרשת"
    turns = []
    for turn, _, speaker in raw_turns:
        if speaker not in label_names:
            label_names[speaker] = f"דובר {hebrew_letters[len(label_names) % len(hebrew_letters)]}'"
        turns.append((turn.start, turn.end, label_names[speaker]))
    return turns


def speaker_for_segment(turns: list[tuple[float, float, str]], seg_start: float, seg_end: float) -> str | None:
    """מוצא את הדובר עם החפיפה הגדולה ביותר לטווח הזמן של קטע התמלול"""
    best_label, best_overlap = None, 0.0
    for t_start, t_end, label in turns:
        overlap = min(seg_end, t_end) - max(seg_start, t_start)
        if overlap > best_overlap:
            best_overlap, best_label = overlap, label
    return best_label


SUMMARY_FORMAT_EXAMPLE = """0:01 גיוס קשב, התמדה, אנרגייה וזמן ליישום התכנית.
1:18 מדיטציה קצרה
8:04 שיעור קצר - איך מגייסים קשב כדי להקשיב לתכנית, להקשיב לעצמנו.
28:17 *שאלות ותשובות*
28:20 מה עושים כשאין לי כסף
30:36 איך מעוררים מוטיבציה לשינוי הרגלים
34:30 תאורה"""

TIMESTAMP_LINE_RE = re.compile(r"^(\d+):(\d{2})\b")


def build_summary_prompt(timestamped_text: str) -> str:
    return (
        "להלן רצף משפטים מתוזמנים (בפורמט [דקות:שניות] טקסט) של שיעור/שיחה בעברית. "
        "הפק ממנו שני חלקים, בדיוק בפורמט הזה (כותרות Markdown מדויקות, בלי שינוי):\n\n"
        "## סיכום\n"
        "סיכום תמציתי בנקודות (בולטים) של הנקודות העיקריות שהדובר העביר - בלי תזמונים, בלי הקדמות ובלי הסברים.\n\n"
        "## תוכן עניינים\n"
        "תוכן עניינים מתוזמן - שורות בפורמט 'דקות:שניות נושא קצר', בסדר כרונולוגי מההתחלה לסוף בלבד "
        "(קח את הזמן מהרצף עצמו, אל תמציא ואל תשנה את הסדר הכרונולוגי). "
        "אם יש קטע שאלות ותשובות, סמן את ההתחלה שלו כ-'*שאלות ותשובות*' ואז כל שאלה בנפרד מתחתיו "
        "באותו אופן. דוגמה לפורמט החלק הזה:\n\n"
        f"{SUMMARY_FORMAT_EXAMPLE}\n\n"
        f"הרצף המתוזמן:\n{timestamped_text}"
    )


def enforce_chronological_order(summary_text: str) -> str:
    """רשת ביטחון: מסדר מחדש את שורות תוכן העניינים לפי הזמן, ללא תלות בסדר שקלוד החזיר"""
    marker = "## תוכן עניינים"
    idx = summary_text.find(marker)
    if idx == -1:
        return summary_text

    head = summary_text[: idx + len(marker)]
    toc_lines = summary_text[idx + len(marker):].split("\n")

    def time_key(ln: str):
        m = TIMESTAMP_LINE_RE.match(ln.strip())
        return int(m.group(1)) * 60 + int(m.group(2)) if m else None

    timed = [ln for ln in toc_lines if time_key(ln) is not None]
    if not timed:
        return summary_text

    timed_sorted = sorted(timed, key=time_key)
    leading = toc_lines[: toc_lines.index(timed[0])]
    return head + "\n".join(leading + timed_sorted) + "\n"


def run_claude_prompt(prompt: str) -> str:
    """מפעיל את Claude Code במצב headless (claude -p) - דרך המנוי הקיים, בלי מפתח API נפרד"""
    claude_path = shutil.which("claude.cmd") or shutil.which("claude") or "claude"
    try:
        result = subprocess.run(
            [claude_path, "-p", "--tools", "", "--disable-slash-commands"],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=900,
            creationflags=_NO_WINDOW,
            cwd=tempfile.gettempdir(),
        )
    except subprocess.TimeoutExpired:
        return "(נכשל: claude -p לא הגיב בזמן)"
    if result.returncode != 0:
        return f"(נכשל: {result.stderr.strip()})"
    return result.stdout.strip()


def summarize_with_claude(timestamped_text: str) -> str:
    """מפיק סיכום בנקודות ותוכן עניינים מתוזמן בקריאה אחת ל-claude -p, ומבטיח סדר כרונולוגי"""
    result = run_claude_prompt(build_summary_prompt(timestamped_text))
    return enforce_chronological_order(result)


def process_file(media_path: Path, model_size: str, summarize: bool, diarize: bool = False,
                 device: str = "cpu", compute_type: str = "int8"):
    if media_path.suffix.lower().lstrip(".") in VIDEO_EXTENSIONS:
        audio_path = media_path.with_suffix(".mp3")
        if not audio_path.exists():
            print(f"[{media_path.name}] מחלץ קובץ אודיו...")
            try:
                extract_audio_file(media_path)
                print(f"[{media_path.name}] קובץ אודיו נשמר: {audio_path.name}")
            except subprocess.CalledProcessError as e:
                print(f"[{media_path.name}] חילוץ אודיו נכשל: {e}")

    speaker_turns = None
    if diarize:
        print(f"[{media_path.name}] מזהה דוברים...")
        try:
            speaker_turns = diarize_audio(media_path, device)
            n_speakers = len({label for _, _, label in speaker_turns})
            print(f"[{media_path.name}] זוהו {n_speakers} דוברים")
        except Exception as e:
            print(f"[{media_path.name}] זיהוי דוברים נכשל, ממשיך בלי תיוג דוברים: {e}")

    print(f"[{media_path.name}] טוען מודל ומתמלל...")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    try:
        srt_path, timestamped_text = transcribe_to_srt(model, media_path, speaker_turns)
    except Exception as e:
        print(f"[{media_path.name}] תמלול נכשל, מדלג: {e}")
        return
    print(f"[{media_path.name}] תמלול נשמר: {srt_path.name}")

    if not summarize:
        return

    print(f"[{media_path.name}] מסכם עם Claude Code...")
    summary = summarize_with_claude(timestamped_text)
    _, summary_path = outputs_for(media_path)
    summary_path.write_text(summary, encoding="utf-8")
    print(f"[{media_path.name}] סיכום נשמר: {summary_path.name}")


def build_queue(
    folder_cfgs: list[dict], extensions: list[str], exclude: set[Path] = frozenset()
) -> list[tuple[Path, bool, bool]]:
    """בונה את התור מחדש מהדיסק - כך שקובץ שנוסף בזמן הסריקה יתפוס את מקומו (לפי עדיפות תיקייה, חדש-ביותר ראשון בתוכה)"""
    queue: list[tuple[Path, bool, bool]] = []
    for folder_cfg in folder_cfgs:
        folder = Path(folder_cfg["path"])
        recursive = folder_cfg.get("recursive", True)
        summarize = folder_cfg.get("summarize", False)
        diarize = folder_cfg.get("diarize", False)
        maxdays = folder_cfg.get("maxdays")
        if not folder.exists():
            print(f"אזהרה: התיקייה לא נמצאה: {folder}")
            continue

        folder_files = [
            media_path
            for media_path in find_media_groups(folder, recursive, extensions, maxdays)
            if media_path not in exclude and needs_processing(media_path, summarize) and is_stable(media_path)
        ]
        folder_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        queue.extend((media_path, summarize, diarize) for media_path in folder_files)
    return queue


def ensure_mp3_companions(folder_cfgs: list[dict]) -> None:
    """לכל תיקייה עם extract_audio:true — יוצר MP3 לצד כל וידאו שחסר לו קובץ שמע"""
    for folder_cfg in folder_cfgs:
        if not folder_cfg.get("extract_audio", False):
            continue
        folder = Path(folder_cfg["path"])
        if not folder.exists():
            continue
        recursive = folder_cfg.get("recursive", True)
        pattern = "**/*" if recursive else "*"
        for p in folder.glob(pattern):
            if p.is_file() and p.suffix.lower().lstrip(".") in VIDEO_EXTENSIONS:
                mp3_path = p.with_suffix(".mp3")
                if not mp3_path.exists():
                    print(f"[{p.name}] יוצר MP3 מלווה...")
                    try:
                        extract_audio_file(p)
                        print(f"[{p.name}] MP3 נשמר: {mp3_path.name}")
                    except Exception as e:
                        print(f"[{p.name}] חילוץ MP3 נכשל: {e}")


def run_scan():
    config = load_config()
    extensions = config.get("extensions", [])
    max_parallel = config.get("max_parallel", 1)
    model_size = config.get("model_size", "medium")
    folder_cfgs = config.get("folders") or []

    ensure_mp3_companions(folder_cfgs)
    device, compute_type = setup_device()
    in_flight: set[Path] = set()
    processed = 0

    with ThreadPoolExecutor(max_workers=max_parallel) as executor:
        futures: dict = {}
        while True:
            while len(futures) < max_parallel:
                next_item = next(iter(build_queue(folder_cfgs, extensions, exclude=in_flight)), None)
                if next_item is None:
                    break
                media_path, summarize, diarize = next_item
                in_flight.add(media_path)
                fut = executor.submit(process_file, media_path, model_size, summarize, diarize, device, compute_type)
                futures[fut] = media_path

            if not futures:
                break

            done = next(as_completed(futures))
            done.result()
            in_flight.discard(futures.pop(done))
            processed += 1

    if processed == 0:
        print("אין קבצים חדשים לתמלל.")
    else:
        print(f"הסריקה הושלמה ({processed} קבצים).")


def run_scan_locked():
    if not acquire_lock():
        print("סריקה אחרת כבר רצה ברגע זה - מדלג על הסריקה הנוכחית.")
        return
    try:
        run_scan()
    finally:
        release_lock()


def main():
    if "--loop" in sys.argv:
        config = load_config()
        interval = config.get("scan_interval_minutes", 60) * 60
        while True:
            run_scan_locked()
            print(f"מחכה {interval // 60} דקות לסריקה הבאה...")
            time.sleep(interval)
    else:
        run_scan_locked()


if __name__ == "__main__":
    main()
