import time
import threading
import ctypes
import math
import tkinter as tk

import numpy as np
import sounddevice as sd
import keyboard
from faster_whisper import WhisperModel

SAMPLERATE = 16000
MIN_DURATION = 0.2


# ---------------------------------------------------------------------------
# Floating icon
# ---------------------------------------------------------------------------

class _FloatingIcon:
    SIZE = 88

    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-transparentcolor', 'black')
        self.root.configure(bg='black')
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = sw - self.SIZE - 24
        y = sh - self.SIZE - 72
        self.root.geometry(f'{self.SIZE}x{self.SIZE}+{x}+{y}')
        self.canvas = tk.Canvas(
            self.root, width=self.SIZE, height=self.SIZE,
            bg='black', highlightthickness=0,
        )
        self.canvas.pack()
        self._angle = 0.0
        self._visible = False
        self.root.withdraw()

    def show(self):
        self.root.after(0, self._show)

    def hide(self):
        self.root.after(0, self._hide)

    def _show(self):
        self._visible = True
        self.root.deiconify()
        self._tick()

    def _hide(self):
        self._visible = False
        self.root.withdraw()

    def _tick(self):
        if not self._visible:
            return
        self._angle += 0.20
        self._draw(0.84 + 0.16 * math.sin(self._angle))
        self.root.after(48, self._tick)

    def _draw(self, pulse):
        c = self.canvas
        c.delete('all')
        cx = cy = self.SIZE // 2
        r = int(27 * pulse)

        for i, color in enumerate(('#5C1A1A', '#7A2222', '#A03030')):
            gr = r + (3 - i) * 5
            c.create_oval(cx-gr, cy-gr, cx+gr, cy+gr, fill=color, outline='')

        c.create_oval(cx-r, cy-r, cx+r, cy+r,
                      fill='#FF6B6B', outline='#FF9E9E', width=2)

        for side in (-1, 1):
            bx, by = cx + side * 9, cy - r + 3
            tx, ty = cx + side * 16, cy - r - 11
            c.create_line(bx, by, tx, ty, fill='#FF9E9E', width=2, capstyle='round')
            c.create_oval(tx-5, ty-5, tx+5, ty+5, fill='#FFD93D', outline='#FFC300', width=1)

        er = max(4, r // 5)
        ey = cy - r // 6
        for side in (-1, 1):
            ex = cx + side * (r // 3)
            c.create_oval(ex-er, ey-er, ex+er, ey+er, fill='white', outline='')
            pr = max(2, er // 2)
            c.create_oval(ex-pr+1, ey-pr, ex+pr+1, ey+pr, fill='#1A1A2E', outline='')
            c.create_oval(ex+pr-1, ey-pr, ex+pr+2, ey-pr+3, fill='white', outline='')

        mw = r // 2
        c.create_arc(cx-mw, cy + r//8, cx+mw, cy + r//2 + 4,
                     start=205, extent=130, style='arc', outline='white', width=2)

    def run(self):
        def _poll():
            self.root.after(200, _poll)
        self.root.after(200, _poll)
        self.root.mainloop()


# ---------------------------------------------------------------------------
# Whisper model
# ---------------------------------------------------------------------------

print("Loading Whisper model...")
model = WhisperModel("base", device="cpu", compute_type="int8")
print("Model loaded.")

_icon = _FloatingIcon()

_lock = threading.Lock()
_recording = False
_delivering = False
_frames = []
_stream = None
_press_time = None
_target_hwnd = None


# ---------------------------------------------------------------------------
# Paste
# ---------------------------------------------------------------------------

def _force_foreground(hwnd):
    if not hwnd:
        return
    target_tid = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, None)
    current_tid = ctypes.windll.kernel32.GetCurrentThreadId()
    ctypes.windll.user32.AttachThreadInput(current_tid, target_tid, True)
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    ctypes.windll.user32.BringWindowToTop(hwnd)
    ctypes.windll.user32.AttachThreadInput(current_tid, target_tid, False)


def _deliver(text, target_hwnd):
    global _delivering
    if not text:
        return
    _delivering = True
    try:
        keyboard.release('ctrl')
        keyboard.release('shift')
        time.sleep(0.03)
        _force_foreground(target_hwnd)
        time.sleep(0.03)
        keyboard.write(text, delay=0)
    finally:
        _delivering = False


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------

def _transcribe_and_deliver(frames, target_hwnd):
    try:
        audio = np.concatenate(frames, axis=0).squeeze().astype(np.float32) / 32768.0
        segments, _ = model.transcribe(audio, beam_size=1, language='en',
            initial_prompt=(
                "Python, JavaScript, TypeScript, React, Next.js, Node.js, FastAPI, Flask, Django, "
                "pandas, NumPy, matplotlib, Jupyter, SQL, PostgreSQL, SQLite, REST API, GraphQL, "
                "JSON, HTML, CSS, Tailwind, Vite, webpack, npm, pip, conda, virtualenv, "
                "Claude, Cline, Ollama, LM Studio, LLM, prompt, token, context, embedding, RAG, "
                "MCP, API key, async, await, function, variable, class, import, export, "
                "git, GitHub, pull request, branch, commit, refactor, debug, linter, type hints, "
                "dataframe, array, vector, model, inference, fine-tune, dataset"
            ))
        result = ' '.join(s.text.strip() for s in segments).strip()
        if result:
            print(f'Transcribed: {result}')
            _deliver(result, target_hwnd)
        else:
            print('(empty — nothing pasted)')
    except Exception as e:
        print(f'Error: {e}')


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------

def _on_press():
    global _recording, _frames, _stream, _press_time, _target_hwnd
    if not _lock.acquire(blocking=False):
        return
    _target_hwnd = ctypes.windll.user32.GetForegroundWindow()
    _press_time = time.time()
    _recording = True
    _frames = []
    _icon.show()

    def _callback(indata, frames, t, status):
        if _recording:
            _frames.append(indata.copy())

    _stream = sd.InputStream(
        samplerate=SAMPLERATE, channels=1, dtype='int16', callback=_callback,
    )
    _stream.start()


def _on_release():
    global _recording, _stream
    duration = time.time() - (_press_time or 0)
    _recording = False
    _icon.hide()

    if _stream:
        _stream.stop()
        _stream.close()
        _stream = None

    frames = list(_frames)
    hwnd = _target_hwnd
    _lock.release()

    if duration < MIN_DURATION or not frames:
        return

    threading.Thread(target=_transcribe_and_deliver, args=(frames, hwnd), daemon=True).start()


# ---------------------------------------------------------------------------
# Hotkey
# ---------------------------------------------------------------------------

def _hotkey_press():
    if not _recording and not _delivering:
        _on_press()

keyboard.add_hotkey('ctrl+shift+space', _hotkey_press, suppress=True, trigger_on_release=False)
keyboard.on_release_key('space', lambda e: _on_release() if _recording else None)

print("Ready — hold Ctrl+Shift+Space to transcribe. Ctrl+C to quit.")
_icon.run()
