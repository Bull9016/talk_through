import os
import sys
import threading
import queue
import time
import json

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from PySide6.QtCore import Qt, QRect, Signal, QObject
from PySide6.QtGui import QPainter, QColor, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QDialog,
    QLabel,
    QComboBox,
    QCheckBox,
    QPushButton,
    QVBoxLayout,
    QFormLayout,
    QHBoxLayout,
    QMessageBox,
)

import keyboard  # global hotkeys
import pyautogui  # to type into active window

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.json")

DEFAULT_CONFIG = {
    "model_size": "small",
    "language": "auto",
    "hold_hotkey": "ctrl+space",
    "toggle_hotkey": "ctrl+shift+space",
    "auto_punct": True,
}


def load_config():
    cfg = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                cfg.update(data)
        except Exception:
            pass
    return cfg


def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print("Failed to save config:", e, file=sys.stderr)


def auto_punctuate(text: str) -> str:
    # very simple auto punctuation
    t = text.strip()
    if not t:
        return t
    t = t[0].upper() + t[1:]
    if not any(ch in t for ch in ".?!"):
        t += "."
    else:
        if t[-1] not in ".?!":
            t += "."
    return t


class TranscriptionEvents(QObject):
    recording_changed = Signal(bool)
    text_ready = Signal(str)


class AudioRecorder:
    def __init__(self, samplerate=16000, channels=1):
        self.samplerate = samplerate
        self.channels = channels
        self._queue = queue.Queue()
        self._stream = None
        self._lock = threading.Lock()

    def _callback(self, indata, frames, time_info, status):
        if status:
            pass
        self._queue.put(indata.copy())

    def start(self):
        with self._lock:
            if self._stream is not None:
                return
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
            self._stream = sd.InputStream(
                samplerate=self.samplerate,
                channels=self.channels,
                callback=self._callback,
            )
            self._stream.start()

    def stop_and_get_audio(self):
        with self._lock:
            if self._stream is None:
                return None
            self._stream.stop()
            self._stream.close()
            self._stream = None

        frames = []
        while not self._queue.empty():
            try:
                frames.append(self._queue.get_nowait())
            except queue.Empty:
                break

        if not frames:
            return None

        audio = np.concatenate(frames, axis=0)
        if self.channels > 1:
            audio = np.mean(audio, axis=1)
        else:
            audio = audio[:, 0]
        return audio.astype(np.float32)


class VoicyController:
    def __init__(self, events: TranscriptionEvents, config: dict):
        self.events = events
        self.config = config
        self.recorder = AudioRecorder()
        print(f"Loading Whisper model: {self.config['model_size']}")
        self.model = WhisperModel(
            self.config["model_size"], device="cpu", compute_type="int8"
        )
        self._recording = False
        self._lock = threading.Lock()

    @property
    def recording(self):
        with self._lock:
            return self._recording

    def _set_recording(self, value: bool):
        with self._lock:
            self._recording = value
        self.events.recording_changed.emit(value)

    def hold_to_talk_down(self):
        if self.recording:
            return
        self._start_recording()

    def hold_to_talk_up(self):
        if not self.recording:
            return
        self._stop_and_transcribe()

    def toggle_recording(self):
        if self.recording:
            self._stop_and_transcribe()
        else:
            self._start_recording()

    def _start_recording(self):
        try:
            self.recorder.start()
            self._set_recording(True)
        except Exception as e:
            print("Error starting recording:", e, file=sys.stderr)

    def _stop_and_transcribe(self):
        self._set_recording(False)
        try:
            audio = self.recorder.stop_and_get_audio()
        except Exception as e:
            print("Error stopping recording:", e, file=sys.stderr)
            audio = None

        if audio is None or len(audio) == 0:
            return

        threading.Thread(
            target=self._transcribe_and_emit, args=(audio,), daemon=True
        ).start()

    def _transcribe_and_emit(self, audio):
        try:
            lang_cfg = self.config.get("language", "auto")
            if lang_cfg == "auto":
                lang_arg = None
            else:
                lang_arg = lang_cfg
            segments, info = self.model.transcribe(audio, language=lang_arg, beam_size=5)
            text_parts = [seg.text for seg in segments]
            text = " ".join(text_parts).strip()
            if not text:
                return
            if self.config.get("auto_punct", True):
                text = auto_punctuate(text)
            self.events.text_ready.emit(text)
        except Exception as e:
            print("Transcription error:", e, file=sys.stderr)


class SettingsDialog(QDialog):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Voicy Settings")
        self.config = config.copy()

        form = QFormLayout()

        self.model_combo = QComboBox()
        self.model_combo.addItems(["tiny", "base", "small", "medium", "large-v2"])
        cur_model = self.config.get("model_size", "small")
        idx = self.model_combo.findText(cur_model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)

        self.lang_combo = QComboBox()
        self.lang_combo.addItem("Auto detect", "auto")
        langs = [
            ("English", "en"),
            ("French", "fr"),
            ("German", "de"),
            ("Spanish", "es"),
            ("Italian", "it"),
            ("Portuguese", "pt"),
            ("Hindi", "hi"),
        ]
        for label, code in langs:
            self.lang_combo.addItem(f"{label} ({code})", code)
        cur_lang = self.config.get("language", "auto")
        idx = self.lang_combo.findData(cur_lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)

        self.hold_combo = QComboBox()
        hold_opts = ["ctrl+space", "alt+space", "ctrl+alt+space"]
        self.hold_combo.addItems(hold_opts)
        cur_hold = self.config.get("hold_hotkey", "ctrl+space")
        idx = self.hold_combo.findText(cur_hold)
        if idx >= 0:
            self.hold_combo.setCurrentIndex(idx)

        self.toggle_combo = QComboBox()
        toggle_opts = ["ctrl+shift+space", "alt+shift+space", "ctrl+alt+shift+space"]
        self.toggle_combo.addItems(toggle_opts)
        cur_toggle = self.config.get("toggle_hotkey", "ctrl+shift+space")
        idx = self.toggle_combo.findText(cur_toggle)
        if idx >= 0:
            self.toggle_combo.setCurrentIndex(idx)

        self.auto_punct_check = QCheckBox("Enable light auto-punctuation")
        self.auto_punct_check.setChecked(self.config.get("auto_punct", True))

        form.addRow(QLabel("Whisper model size:"), self.model_combo)
        form.addRow(QLabel("Language:"), self.lang_combo)
        form.addRow(QLabel("Hold-to-talk hotkey:"), self.hold_combo)
        form.addRow(QLabel("Toggle hotkey:"), self.toggle_combo)
        form.addRow(self.auto_punct_check)

        btn_box = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        btn_box.addWidget(save_btn)
        btn_box.addWidget(cancel_btn)
        save_btn.clicked.connect(self.on_save)
        cancel_btn.clicked.connect(self.reject)

        info = QLabel(
            "Model + hotkeys apply on next start.\n"
            "Language and punctuation apply to new recordings."
        )
        info.setStyleSheet("color:#555;font-size:11px;")

        layout = QVBoxLayout()
        layout.addLayout(form)
        layout.addLayout(btn_box)
        layout.addWidget(info)
        self.setLayout(layout)

    def on_save(self):
        self.config["model_size"] = self.model_combo.currentText()
        self.config["language"] = self.lang_combo.currentData()
        self.config["hold_hotkey"] = self.hold_combo.currentText()
        self.config["toggle_hotkey"] = self.toggle_combo.currentText()
        self.config["auto_punct"] = self.auto_punct_check.isChecked()
        save_config(self.config)
        QMessageBox.information(
            self,
            "Voicy Settings",
            "Settings saved.\n\n"
            "Restart app to apply model/hotkey changes.",
        )
        self.accept()


class DotWindow(QWidget):
    def __init__(self, events: TranscriptionEvents, controller: VoicyController, config: dict):
        super().__init__()
        self.events = events
        self.controller = controller
        self.config = config
        self._recording = False

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self.radius = 9
        self.resize(self.radius * 2 + 4, self.radius * 2 + 4)

        screen = QGuiApplication.primaryScreen().geometry()
        x = 16
        y = screen.height() // 2 - self.height() // 2
        self.move(x, y)

        self.events.recording_changed.connect(self.on_recording_changed)
        self.events.text_ready.connect(self.on_text_ready)

    def on_recording_changed(self, is_rec):
        self._recording = is_rec
        self.update()

    def on_text_ready(self, text: str):
        try:
            time.sleep(0.05)
            pyautogui.typewrite(text)
        except Exception as e:
            print("Typing error:", e, file=sys.stderr)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        if self._recording:
            color = QColor(255, 59, 59)
        else:
            color = QColor(76, 111, 255)
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        rect = QRect(2, 2, self.radius * 2, self.radius * 2)
        painter.drawEllipse(rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.controller.toggle_recording()
        elif event.button() == Qt.RightButton:
            dlg = SettingsDialog(load_config(), self)
            dlg.exec()
        event.accept()


def parse_hold_hotkey(hotkey_str: str):
    parts = [p.strip().lower() for p in hotkey_str.split("+") if p.strip()]
    if not parts:
        return "space", {"ctrl"}
    base = parts[-1]
    mods = set(parts[:-1])
    return base, mods


def setup_hotkeys(controller: VoicyController, config: dict):
    hold_base, hold_mods = parse_hold_hotkey(config.get("hold_hotkey", "ctrl+space"))

    def on_key_down(event):
        if event.name == hold_base:
            if all(keyboard.is_pressed(m) for m in hold_mods):
                controller.hold_to_talk_down()

    def on_key_up(event):
        if event.name == hold_base:
            controller.hold_to_talk_up()

    keyboard.on_press(on_key_down, suppress=False)
    keyboard.on_release(on_key_up, suppress=False)

    toggle_combo = config.get("toggle_hotkey", "ctrl+shift+space")
    keyboard.add_hotkey(toggle_combo, controller.toggle_recording)


def main():
    config = load_config()
    app = QApplication(sys.argv)

    events = TranscriptionEvents()
    controller = VoicyController(events, config)
    dot = DotWindow(events, controller, config)
    dot.show()

    threading.Thread(target=setup_hotkeys, args=(controller, config), daemon=True).start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()