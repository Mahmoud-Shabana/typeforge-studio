"""Explicit-target Windows SendInput adapter. No hooks, network, or clipboard injection."""
from __future__ import annotations
import ctypes
import os
from ctypes import wintypes

if os.name != 'nt':
    class WindowsInput:
        def __init__(self):
            raise OSError('TypeForge keyboard injection is Windows-only.')
else:
    ULONG_PTR = ctypes.c_ulonglong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_ulong

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [('wVk', wintypes.WORD), ('wScan', wintypes.WORD),
                    ('dwFlags', wintypes.DWORD), ('time', wintypes.DWORD),
                    ('dwExtraInfo', ULONG_PTR)]

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [('dx', wintypes.LONG), ('dy', wintypes.LONG),
                    ('mouseData', wintypes.DWORD), ('dwFlags', wintypes.DWORD),
                    ('time', wintypes.DWORD), ('dwExtraInfo', ULONG_PTR)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [('uMsg', wintypes.DWORD), ('wParamL', wintypes.WORD),
                    ('wParamH', wintypes.WORD)]

    class INPUT_UNION(ctypes.Union):
        _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT), ('hi', HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [('type', wintypes.DWORD), ('u', INPUT_UNION)]

    VK_RETURN, VK_BACK, VK_SHIFT, VK_F8, VK_F9 = 0x0D, 0x08, 0x10, 0x77, 0x78
    KEYUP, UNICODE = 0x0002, 0x0004
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
    user32.SendInput.restype = wintypes.UINT
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.IsWindow.argtypes = (wintypes.HWND,)
    user32.IsWindow.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
    user32.GetAsyncKeyState.restype = wintypes.SHORT
    user32.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetClassNameW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user32.GetClassNameW.restype = ctypes.c_int
    user32.IsWindowVisible.argtypes = (wintypes.HWND,)
    user32.IsWindowVisible.restype = wintypes.BOOL

    class WindowsInput:
        def foreground(self) -> int:
            return int(user32.GetForegroundWindow() or 0)

        def is_window(self, hwnd: int) -> bool:
            return bool(hwnd and user32.IsWindow(hwnd))

        def valid_target(self, hwnd: int) -> bool:
            if not self.is_window(hwnd) or not user32.IsWindowVisible(hwnd):
                return False
            pid = wintypes.DWORD(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == os.getpid():
                return False  # never type into TypeForge itself
            klass = ctypes.create_unicode_buffer(128)
            user32.GetClassNameW(hwnd, klass, len(klass))
            if klass.value in {'Progman', 'WorkerW', 'Shell_TrayWnd',
                               'Shell_SecondaryTrayWnd', 'NotifyIconOverflowWindow',
                               'MultitaskingViewFrame'}:
                return False  # avoid desktop/taskbar/system UI
            return True

        def title(self, hwnd: int) -> str:
            if not self.is_window(hwnd):
                return '(closed window)'
            n = min(512, user32.GetWindowTextLengthW(hwnd) + 1)
            buf = ctypes.create_unicode_buffer(max(2, n))
            user32.GetWindowTextW(hwnd, buf, len(buf))
            return buf.value or '(untitled window)'

        def held(self, vk: int) -> bool:
            return bool(user32.GetAsyncKeyState(vk) & 0x8000)

        def modifiers_pressed(self) -> bool:
            # Avoid accidentally invoking target shortcuts when the person is
            # holding Ctrl, Alt or Windows during a typing session.
            return any(self.held(v) for v in (0x11, 0x12, 0x5B, 0x5C))

        def _send(self, vk: int = 0, scan: int = 0, flags: int = 0) -> None:
            inp = INPUT(type=1, u=INPUT_UNION(ki=KEYBDINPUT(vk, scan, flags, 0, 0)))
            count = user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
            if count != 1:
                raise OSError('Windows rejected simulated keyboard input. Check app permissions.')

        def _tap_vk(self, vk: int) -> None:
            self._send(vk)
            self._send(vk, flags=KEYUP)

        def backspace(self) -> None:
            self._tap_vk(VK_BACK)

        def type_char(self, ch: str, shift_enter: bool = False) -> None:
            if ch == '\n':
                if shift_enter:
                    self._send(VK_SHIFT)
                    try:
                        self._tap_vk(VK_RETURN)
                    finally:
                        self._send(VK_SHIFT, flags=KEYUP)
                else:
                    self._tap_vk(VK_RETURN)
                return
            # Send one UTF-16 unit at a time, supporting supplementary characters/emoji.
            raw = ch.encode('utf-16-le', errors='surrogatepass')
            for i in range(0, len(raw), 2):
                unit = int.from_bytes(raw[i:i+2], 'little')
                self._send(scan=unit, flags=UNICODE)
                self._send(scan=unit, flags=UNICODE | KEYUP)