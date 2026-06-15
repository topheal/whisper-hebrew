"""
תמלול קבצי אודיו/וידאו לעברית עם Whisper מקומי
שימוש: python transcribe.py <קובץ>
"""

import sys
from pathlib import Path
from faster_whisper import WhisperModel

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MODEL_SIZE = "medium"  # אפשרויות: tiny, base, small, medium, large-v3


def transcribe(audio_path: str):
    path = Path(audio_path)
    if not path.exists():
        print(f"שגיאה: הקובץ '{audio_path}' לא נמצא")
        sys.exit(1)

    print(f"טוען מודל {MODEL_SIZE}... (בפעם הראשונה יורד מהאינטרנט ~1.5GB)")
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

    print(f"מתמלל: {path.name}")
    segments, info = model.transcribe(
        audio_path,
        language="he",
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )

    print(f"שפה זוהתה: {info.language} (ודאות: {info.language_probability:.0%})\n")
    print("=" * 60)

    full_text = []
    for segment in segments:
        timestamp = f"[{int(segment.start//60):02d}:{segment.start%60:05.2f}]"
        line = f"{timestamp} {segment.text.strip()}"
        print(line)
        full_text.append(segment.text.strip())

    print("=" * 60)

    output_path = path.with_suffix(".txt")
    output_path.write_text("\n".join(full_text), encoding="utf-8")
    print(f"\nתמלול נשמר: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("שימוש: python transcribe.py <קובץ>")
        print("פורמטים נתמכים: mp3, mp4, wav, m4a, ogg, flac, webm, mkv")
        sys.exit(1)
    transcribe(sys.argv[1])
