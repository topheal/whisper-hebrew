"""
ממשק גרפי לתמלול קבצי אודיו/וידאו לעברית
הרץ: python transcribe_gui.py
"""

import sys
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import threading
import subprocess
from pathlib import Path

SUPPORTED = [
    ("קבצי אודיו/וידאו", "*.mp3 *.mp4 *.wav *.m4a *.ogg *.flac *.webm *.mkv *.aac *.wma"),
    ("כל הקבצים", "*.*"),
]

SCRIPT = Path(__file__).parent / "transcribe.py"


def run_transcription(file_path, output_widget, btn):
    btn.config(state="disabled", text="מתמלל...")
    output_widget.delete("1.0", tk.END)
    output_widget.insert(tk.END, f"מתמלל: {file_path}\n")
    output_widget.insert(tk.END, "בפעם הראשונה: מוריד מודל (~1.5GB)...\n\n")
    output_widget.see(tk.END)

    process = subprocess.Popen(
        [sys.executable, str(SCRIPT), file_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    for line in process.stdout:
        output_widget.insert(tk.END, line)
        output_widget.see(tk.END)
        output_widget.update()

    process.wait()
    btn.config(state="normal", text="בחר קובץ לתמלול")

    if process.returncode == 0:
        messagebox.showinfo("סיום", "התמלול הושלם!\nהקובץ נשמר ליד קובץ המקור.")
    else:
        messagebox.showerror("שגיאה", "התמלול נכשל. ראה פרטים בחלון הפלט.")


def pick_and_transcribe(output_widget, btn):
    file_path = filedialog.askopenfilename(
        title="בחר קובץ לתמלול",
        filetypes=SUPPORTED,
    )
    if not file_path:
        return
    threading.Thread(
        target=run_transcription,
        args=(file_path, output_widget, btn),
        daemon=True,
    ).start()


def main():
    root = tk.Tk()
    root.title("תמלול עברית - Whisper")
    root.geometry("700x500")
    root.resizable(True, True)

    frame = tk.Frame(root, padx=10, pady=10)
    frame.pack(fill=tk.BOTH, expand=True)

    btn = tk.Button(
        frame,
        text="בחר קובץ לתמלול",
        font=("Arial", 14),
        bg="#4CAF50",
        fg="white",
        padx=20,
        pady=10,
        cursor="hand2",
    )
    btn.pack(pady=(0, 10))

    output = scrolledtext.ScrolledText(
        frame,
        wrap=tk.WORD,
        font=("Consolas", 10),
        bg="#1e1e1e",
        fg="#d4d4d4",
        height=20,
    )
    output.pack(fill=tk.BOTH, expand=True)

    btn.config(command=lambda: pick_and_transcribe(output, btn))
    root.mainloop()


if __name__ == "__main__":
    main()
