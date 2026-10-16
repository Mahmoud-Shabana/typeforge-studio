# TypeForge Studio — v1.0

A Windows-first **local-only desktop typing workstation**. Designed independently and informed by the workflow of [walter-pitcher/auto-typer](https://github.com/walter-pitcher/auto-typer). No source code from that repository is included.

> **Supported:** Windows 10/11, Python 3.10+, standard Python distribution with Tkinter. No third-party packages at runtime. No network calls or telemetry. **Build not executed on Windows in this environment.**

## Main features

- Unicode typing (Arabic, accents, emoji) with Windows `SendInput` UTF-16 events
- 5 profiles (Balanced, Precision, Natural, Fast, Presentation)
- Speed, rhythm variance, optional automatically corrected QWERTY typos, punctuation/paragraph pauses
- Realtime progress, word and character counts, rough time-to-completion forecast
- Start countdown: click into any destination text field before typing begins
- Focus-bound session: pauses if you change the destination window or click within it
- F8 pause/resume and F9 emergency stop (when Windows allows shortcut polling)
- Manual pause and stop controls; returning to the **same** target is required to resume
- Local snippet library, edit load/save, import/export JSON
- Batch queue using saved snippets, reorder and remove
- Custom `{{variable}}` templates, `{{date}}`, `{{time}}`, `{{datetime}}`, `{{clipboard}}`
- Shift+Enter newlines for chat interfaces, on by default
- `.txt`, `.md`, `.csv`, `.log` input; exact-output preview
- Local preferences and anonymous run history (outcome and character count only); input text **not** autosaved

## How to run it

1. Install Python 3.10+ for Windows from python.org. Select **Add Python to PATH** during installation.
2. Extract the ZIP.
3. Double-click `start.bat` or run `python app.py`.
4. Paste your text; use **Preview** to verify what will be typed.
5. Click **START TYPING**. Switch to the intended text box before the countdown ends.
6. Use **F8** to pause/resume (on resume, focus the original destination); use **F9** to stop.

To build a single Windows `.exe`: run `build.bat` on your Windows PC. This will download **PyInstaller** during the build (the running app itself needs no internet). Output: `dist\TypeForgeStudio.exe`. Note: antivirus may flag newly packaged, unsigned executables; code-signing is recommended for distribution.

## Basic architecture

| File | Role |
| --- | --- |
| `app.py` | Dark Tkinter UI, local library, queue, worker state machine |
| `core.py` | Pure text processing, presets, timing, template validation |
| `windows_input.py` | Explicit window selection, key injection via Win32 `SendInput` |
| `storage.py` | Local-only JSON preferences, snippet library, minimal run history |
| `tests/test_core.py` | Pure engine unit tests |

Run tests on any OS: `python -m unittest discover -s tests -v`.

## Important limitations

- This v1 uses Unicode `SendInput` events: some games, terminals, specialized editors, or Remote Desktop applications may not interpret them correctly. The reference repository has **stronger remote-desktop/code-editor handling** than this initial implementation. We have **not** implemented parity for those edge cases yet.
- It does not read back or verify the text that appears in another app. Avoid unattended use.
- Clicking/focusing the original window is always required on start and resume. This is intentionally safer than forcing window focus.
- Pressing **Enter** might send a message. **Shift+Enter** is on by default, but behavior depends on the target application. Preview and test using a harmless local document first.
- Template `{{clipboard}}` accesses local clipboard data **only when explicitly used** in text.
- Scripts are typing assistants, **not a means to evade platform rules, originality checks, or monitoring**. Use only where automated input is permitted.
- No claim is made about defeating bot or AI-detection systems.
- Switching focus while a typo is being corrected can very rarely leave part of the correction in the destination; inspect your final text.

## Privacy

Preferences: `%APPDATA%\TypeForgeStudio\preferences.json`  
Saved snippets: `%APPDATA%\TypeForgeStudio\snippets.json`  
Run metadata: `%APPDATA%\TypeForgeStudio\history.json`

The editor contents are **not** saved automatically. A snippet is saved only when you click **Save to Library**. To remove local data delete the entire `%APPDATA%\TypeForgeStudio` folder.

## Next roadmap

- Native C#/.NET 8 Windows app and signed installer
- Target-aware code editor mode, smart indentation handling
- Reliable RDP/remote mode with layout translation and Alt-key fallbacks
- Optional queue step confirmation and per-app newline profiles
- CLI, macro export, and accessibility review

## GitHub development

- CI workflow (`.github/workflows/ci.yml`) runs the 7 engine tests on Windows and Linux, and packages an **unsigned** Windows executable as a build artifact. A successful run is not equivalent to manual Windows functional testing.
- Git ignores Python cache, build outputs, local preferences and other generated files.
- No software license has been selected yet. Choose one before inviting outside contributions or publishing derivative works under an open-source license.