"""Reversible Windows desktop parenting for the application's own window."""
import ctypes
import os
from ctypes import wintypes

GWL_STYLE, GWL_EXSTYLE = -16, -20
WS_CHILD, WS_POPUP = 0x40000000, 0x80000000
WS_CAPTION, WS_THICKFRAME = 0x00C00000, 0x00040000
WS_SYSMENU, WS_MINIMIZEBOX, WS_MAXIMIZEBOX = 0x00080000, 0x00020000, 0x00010000
WS_EX_APPWINDOW, WS_EX_TOOLWINDOW, WS_EX_TOPMOST = 0x00040000, 0x80, 0x8
SWP_FRAMECHANGED, SWP_SHOWWINDOW, SWP_NOACTIVATE = 0x20, 0x40, 0x10

class DesktopAttachment:
    def __init__(self, window):
        if os.name != 'nt':
            raise RuntimeError('桌面嵌入仅支持 Windows')
        self.window = window
        self.enabled = False
        self.saved = None
        self.host = None
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        ptr = ctypes.c_ssize_t
        signatures = {
            'FindWindowW': ([wintypes.LPCWSTR, wintypes.LPCWSTR], wintypes.HWND),
            'FindWindowExW': ([wintypes.HWND, wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR], wintypes.HWND),
            'GetShellWindow': ([], wintypes.HWND),
            'GetParent': ([wintypes.HWND], wintypes.HWND),
            'SetParent': ([wintypes.HWND, wintypes.HWND], wintypes.HWND),
            'GetWindowRect': ([wintypes.HWND, ctypes.POINTER(wintypes.RECT)], wintypes.BOOL),
            'MapWindowPoints': ([wintypes.HWND, wintypes.HWND, ctypes.POINTER(wintypes.POINT), wintypes.UINT], ctypes.c_int),
            'SetWindowPos': ([wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT], wintypes.BOOL),
            'GetClassNameW': ([wintypes.HWND, wintypes.LPWSTR, ctypes.c_int], ctypes.c_int),
            'IsWindow': ([wintypes.HWND], wintypes.BOOL),
            'IsWindowVisible': ([wintypes.HWND], wintypes.BOOL),
        }
        self.get_long = self.user32.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else self.user32.GetWindowLongW
        self.set_long = self.user32.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else self.user32.SetWindowLongW
        self.get_long.argtypes = [wintypes.HWND, ctypes.c_int]
        self.get_long.restype = ptr
        self.set_long.argtypes = [wintypes.HWND, ctypes.c_int, ptr]
        self.set_long.restype = ptr
        for name, (args, result) in signatures.items():
            fn = getattr(self.user32, name)
            fn.argtypes, fn.restype = args, result

    def _invoke(self, action):
        from System import Action
        native = self.window.native
        if native is None:
            raise RuntimeError('桌面窗口尚未准备好')
        result, errors = [], []
        def execute():
            try:
                result.append(action())
            except Exception as error:
                errors.append(error)
        if native.InvokeRequired:
            native.Invoke(Action(execute))
        else:
            execute()
        if errors:
            raise errors[0]
        return result[0] if result else None

    def _hwnd(self):
        return self.window.native.Handle.ToInt64()

    def _class_name(self, hwnd):
        value = ctypes.create_unicode_buffer(256)
        self.user32.GetClassNameW(hwnd, value, len(value))
        return value.value

    def _find_host(self):
        # Explorer places its desktop icon view under Progman or WorkerW.
        # Attach alongside that view, so the widget remains interactive.
        candidates = []
        shell = self.user32.GetShellWindow()
        if shell:
            candidates.append(shell)
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def collect(hwnd, _):
            if self._class_name(hwnd) in ('Progman', 'WorkerW'):
                candidates.append(hwnd)
            return True
        callback = callback_type(collect)
        self.user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
        self.user32.EnumWindows.restype = wintypes.BOOL
        self.user32.EnumWindows(callback, 0)
        for hwnd in dict.fromkeys(candidates):
            if self.user32.FindWindowExW(hwnd, None, 'SHELLDLL_DefView', None):
                return hwnd
        raise RuntimeError('未找到 Windows 桌面，已保持普通窗口。请稍后重试。')

    def _write_long(self, hwnd, index, value):
        ctypes.set_last_error(0)
        previous = self.set_long(hwnd, index, value)
        if previous == 0 and ctypes.get_last_error():
            raise ctypes.WinError(ctypes.get_last_error())

    def _parent(self, hwnd, parent):
        ctypes.set_last_error(0)
        previous = self.user32.SetParent(hwnd, parent)
        if not previous and ctypes.get_last_error():
            raise ctypes.WinError(ctypes.get_last_error())

    def _position(self, hwnd, parent, rect, topmost=False):
        point = wintypes.POINT(rect.left, rect.top)
        if parent:
            self.user32.MapWindowPoints(None, parent, ctypes.byref(point), 1)
        after = 0 if parent else (-1 if topmost else -2)
        if not self.user32.SetWindowPos(hwnd, after, point.x, point.y, rect.right-rect.left, rect.bottom-rect.top,
                                        SWP_FRAMECHANGED | SWP_SHOWWINDOW | SWP_NOACTIVATE):
            raise ctypes.WinError(ctypes.get_last_error())

    def set_enabled(self, enabled):
        def change():
            if enabled == self.enabled:
                return self.enabled
            hwnd = self._hwnd()
            if enabled:
                host = self._find_host()
                rect = wintypes.RECT()
                if not self.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                    raise ctypes.WinError(ctypes.get_last_error())
                self.saved = (self.get_long(hwnd, GWL_STYLE) & 0xffffffff,
                              self.get_long(hwnd, GWL_EXSTYLE) & 0xffffffff,
                              self.user32.GetParent(hwnd), rect, bool(self.window.native.TopMost))
                try:
                    self.window.native.TopMost = False
                    style = (self.saved[0] | WS_CHILD) & ~(WS_POPUP | WS_CAPTION | WS_THICKFRAME | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)
                    extra = (self.saved[1] | WS_EX_TOOLWINDOW) & ~(WS_EX_APPWINDOW | WS_EX_TOPMOST)
                    self._write_long(hwnd, GWL_STYLE, style)
                    self._write_long(hwnd, GWL_EXSTYLE, extra)
                    self._parent(hwnd, host)
                    self._position(hwnd, host, rect)
                    self.host, self.enabled = host, True
                except Exception:
                    self._restore(hwnd)
                    raise RuntimeError('无法嵌入当前 Windows 桌面，已恢复普通窗口。') from None
            else:
                self._restore(hwnd)
            return self.enabled
        return self._invoke(change)

    def _restore(self, hwnd):
        if not self.saved:
            return
        style, extra, parent, rect, topmost = self.saved
        self._parent(hwnd, parent)
        self._write_long(hwnd, GWL_STYLE, style)
        self._write_long(hwnd, GWL_EXSTYLE, extra)
        self.window.native.TopMost = topmost
        self._position(hwnd, parent, rect, topmost)
        self.enabled, self.host = False, None
        self.saved = None

    def inspect(self):
        def read():
            hwnd = self._hwnd()
            style = self.get_long(hwnd, GWL_STYLE) & 0xffffffff
            return dict(embedded=self.enabled, parent_class=self._class_name(self.user32.GetParent(hwnd)),
                        child=bool(style & WS_CHILD), caption=bool(style & WS_CAPTION),
                        resizable=bool(style & WS_THICKFRAME), system_menu=bool(style & WS_SYSMENU),
                        visible=bool(self.user32.IsWindowVisible(hwnd)))
        return self._invoke(read)
