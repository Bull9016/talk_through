
# Tale_through Desktop (Windows, Python + Whisper) — v2

Small floating dot on your screen that lets you dictate text anywhere using a local Whisper model.

## New in this version

- ✅ **Settings window** (right-click the dot):
  - Change Whisper model size (`tiny`, `base`, `small`, `medium`, `large-v2`)
  - Change language (or set to **Auto detect**)
  - Change hotkeys:
    - Hold-to-talk (default: `Ctrl + Space`)
    - Toggle recording (default: `Ctrl + Shift + Space`)
  - Enable/disable **light auto-punctuation**
- ✅ Basic **auto-punctuation**
- ✅ Config saved to `config.json`
- ✅ Ready for **PyInstaller single-file EXE**

---

## 1. Install Python

Install **Python 3.10+** for Windows from the official Python website.  
During install, make sure to check:

- ✅ "Add Python to PATH"

---

## 2. Install required packages

Open **Command Prompt** in this folder and run:

```bash
pip install -r requirements.txt
```

---

## 3. Run the app

```bash
python main.py
```

You should see a **small blue dot** appear on the left middle edge of your primary screen.

---

## 4. Usage

### Modes

- **Hold-to-talk**:
  - Hold the configured hotkey (default: `Ctrl + Space`)
  - Speak
  - Release → audio stops, Whisper transcribes, text is typed into the active window

- **Toggle mode**:
  - Press the toggle hotkey (default: `Ctrl + Shift + Space`) **once**, or left-click the dot
  - Dot turns **red** → recording
  - Press the toggle hotkey again or left-click the dot again
  - Recording stops, text is typed into the active window

### Settings window

Right-click the dot to open **Voicy Settings**:
- Whisper model size (speed vs quality)
- Language or Auto detect
- Hold hotkey preset
- Toggle hotkey preset
- Auto-punctuation on/off

> Note: model + hotkey changes are applied the **next time you start** the app.  
> Language and auto-punctuation apply to **new recordings** immediately.

---

## 5. Make a single-file EXE (no Python needed for running)

Once it's working, you can build a self-contained `.exe` with **PyInstaller**.

1. Install PyInstaller:

```bash
pip install pyinstaller
```

2. From this folder, run:

```bash
pyinstaller --onefile --noconsole main.py
```

3. After it finishes, you'll get:

- `dist/main.exe`

You can rename it, for example, to `VoicyDot.exe` and put it anywhere.  
Double-click to launch — **no Python required** on that machine.

> If you see issues with missing DLLs when running the EXE, run the Command Prompt as Administrator and rebuild once.

---

## 6. Tips & Troubleshooting

- If nothing is typed:
  - Make sure the cursor is in a text box in some app
  - Check that your microphone is the default input in Windows
  - Watch the console for errors (audio / transcription)
- If CPU is slow:
  - In settings, switch model to **`tiny`** or **`base`**
- If global hotkeys don't work:
  - Try running the app / EXE as **Administrator** (the `keyboard` library sometimes needs this)

Enjoy your system-wide, private Tale_through ✨
