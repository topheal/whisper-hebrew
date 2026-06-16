"""
שרת תמלול מקומי — פותח בדפדפן על http://localhost:5050
הרץ: python server.py
"""

import sys
import os
import threading
import webbrowser
from pathlib import Path
from flask import Flask, request, jsonify, render_template_string

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

app = Flask(__name__)
UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

HTML = """
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
  <meta charset="UTF-8">
  <title>תמלול עברית - Whisper</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: Arial, sans-serif; background: #0f0f0f; color: #e0e0e0; min-height: 100vh; display: flex; flex-direction: column; align-items: center; padding: 40px 20px; }
    h1 { font-size: 1.8rem; margin-bottom: 8px; color: #fff; }
    p.sub { color: #888; margin-bottom: 32px; font-size: 0.95rem; }
    .drop-zone {
      width: 100%; max-width: 640px; border: 2px dashed #444; border-radius: 12px;
      padding: 48px 24px; text-align: center; cursor: pointer; transition: border-color 0.2s, background 0.2s;
    }
    .drop-zone:hover, .drop-zone.drag-over { border-color: #4CAF50; background: #1a2a1a; }
    .drop-zone input { display: none; }
    .drop-zone .icon { font-size: 3rem; margin-bottom: 12px; }
    .drop-zone p { color: #aaa; }
    .drop-zone p span { color: #4CAF50; text-decoration: underline; cursor: pointer; }
    #filename { margin-top: 10px; color: #4CAF50; font-size: 0.9rem; min-height: 20px; }
    button#transcribe-btn {
      margin-top: 24px; padding: 14px 40px; font-size: 1.1rem;
      background: #4CAF50; color: white; border: none; border-radius: 8px;
      cursor: pointer; transition: background 0.2s; display: none;
    }
    button#transcribe-btn:hover { background: #43a047; }
    button#transcribe-btn:disabled { background: #555; cursor: not-allowed; }
    #status { margin-top: 16px; color: #aaa; font-size: 0.9rem; min-height: 20px; }
    #output-box {
      width: 100%; max-width: 640px; margin-top: 24px;
      background: #1e1e1e; border-radius: 10px; padding: 20px;
      display: none;
    }
    #output-box h2 { font-size: 1rem; color: #888; margin-bottom: 12px; }
    #output { white-space: pre-wrap; line-height: 1.7; font-size: 0.95rem; color: #d4d4d4; }
    #copy-btn {
      margin-top: 14px; padding: 8px 20px; background: #333; color: #ccc;
      border: 1px solid #555; border-radius: 6px; cursor: pointer; font-size: 0.9rem;
    }
    #copy-btn:hover { background: #444; }
  </style>
</head>
<body>
  <h1>תמלול עברית מקומי</h1>
  <p class="sub">Whisper — חינמי, מקומי, ללא אינטרנט</p>

  <div class="drop-zone" id="drop-zone">
    <input type="file" id="file-input" accept=".mp3,.mp4,.wav,.m4a,.ogg,.flac,.webm,.mkv,.aac,.wma">
    <div class="icon">🎙️</div>
    <p>גרור לכאן קובץ אודיו או וידאו<br>או <span onclick="document.getElementById('file-input').click()">בחר קובץ</span></p>
    <div id="filename"></div>
  </div>

  <button id="transcribe-btn" onclick="startTranscription()">תמלל</button>
  <div id="status"></div>

  <div id="output-box">
    <h2>תמלול:</h2>
    <div id="output"></div>
    <button id="copy-btn" onclick="copyText()">העתק טקסט</button>
  </div>

  <script>
    let selectedFile = null;

    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
    dropZone.addEventListener('drop', e => {
      e.preventDefault();
      dropZone.classList.remove('drag-over');
      if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener('change', () => { if (fileInput.files[0]) setFile(fileInput.files[0]); });

    function setFile(file) {
      selectedFile = file;
      document.getElementById('filename').textContent = file.name;
      document.getElementById('transcribe-btn').style.display = 'inline-block';
      document.getElementById('output-box').style.display = 'none';
      document.getElementById('status').textContent = '';
    }

    async function startTranscription() {
      if (!selectedFile) return;
      const btn = document.getElementById('transcribe-btn');
      btn.disabled = true;
      btn.textContent = 'מתמלל...';
      document.getElementById('status').textContent = 'מעלה קובץ...';
      document.getElementById('output-box').style.display = 'none';

      const formData = new FormData();
      formData.append('file', selectedFile);

      try {
        document.getElementById('status').textContent = 'מתמלל — זה עשוי לקחת כמה דקות...';
        const res = await fetch('/transcribe', { method: 'POST', body: formData });
        const data = await res.json();

        if (data.error) {
          document.getElementById('status').textContent = 'שגיאה: ' + data.error;
        } else {
          document.getElementById('status').textContent = '✓ הושלם';
          document.getElementById('output').textContent = data.text;
          document.getElementById('output-box').style.display = 'block';
        }
      } catch (e) {
        document.getElementById('status').textContent = 'שגיאת חיבור לשרת';
      }

      btn.disabled = false;
      btn.textContent = 'תמלל';
    }

    function copyText() {
      const text = document.getElementById('output').textContent;
      navigator.clipboard.writeText(text);
      document.getElementById('copy-btn').textContent = 'הועתק!';
      setTimeout(() => document.getElementById('copy-btn').textContent = 'העתק טקסט', 2000);
    }
  </script>
</body>
</html>
"""


model = None

def get_model():
    global model
    if model is None:
        from faster_whisper import WhisperModel
        print("טוען מודל...")
        model = WhisperModel("medium", device="cpu", compute_type="int8")
        print("מודל מוכן.")
    return model


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/transcribe", methods=["POST"])
def transcribe():
    if "file" not in request.files:
        return jsonify({"error": "לא נשלח קובץ"})

    f = request.files["file"]
    save_path = UPLOAD_DIR / f.filename
    f.save(save_path)

    try:
        whisper = get_model()
        segments, info = whisper.transcribe(
            str(save_path),
            language="he",
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
        )
        text = "\n".join(seg.text.strip() for seg in segments)
        return jsonify({"text": text, "language": info.language})
    except Exception as e:
        return jsonify({"error": str(e)})
    finally:
        save_path.unlink(missing_ok=True)


def open_browser():
    webbrowser.open("http://localhost:5050")


if __name__ == "__main__":
    print("פותח דפדפן על http://localhost:5050")
    threading.Timer(1.5, open_browser).start()
    app.run(host="127.0.0.1", port=5050, debug=False)
