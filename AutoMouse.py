import ctypes
import time
import math
import random
from typing import Tuple, List, Optional

# Win32 常量
MOUSEEVENTF_LEFTDOWN   = 0x0002
MOUSEEVENTF_LEFTUP     = 0x0004
MOUSEEVENTF_RIGHTDOWN  = 0x0008
MOUSEEVENTF_RIGHTUP    = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP   = 0x0040
MOUSEEVENTF_WHEEL      = 0x0800
MOUSEEVENTF_MOVE       = 0x0001


class AutoMouse:
    """
    AutoMouse v2
    零依赖的 Windows 自动鼠标控制类
    支持：平滑移动、拟人轨迹、单击、双击、拖拽、滚轮、中键、侧键
    """

    def __init__(self):
        self.user32 = ctypes.windll.user32
        self._stop_flag = False

    # ---------- 基础工具 ----------
    def _get_pos(self) -> Tuple[int, int]:
        """获取当前鼠标坐标"""
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        pt = POINT()
        self.user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    def _set_pos(self, x: int, y: int):
        """设置鼠标坐标（带边界保护）"""
        x, y = self._clamp(x, y)
        self.user32.SetCursorPos(x, y)

    def _clamp(self, x: int, y: int) -> Tuple[int, int]:
        """限制坐标在屏幕范围内"""
        w = self.user32.GetSystemMetrics(0)
        h = self.user32.GetSystemMetrics(1)
        return max(0, min(x, w - 1)), max(0, min(y, h - 1))

    def _send_input(self, flags: int, dx: int = 0, dy: int = 0, data: int = 0):
        """发送鼠标事件"""
        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [
                ("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
            ]
        class INPUT(ctypes.Structure):
            _fields_ = [("type", ctypes.c_ulong), ("mi", MOUSEINPUT)]
        inp = INPUT()
        inp.type = 0  # INPUT_MOUSE
        inp.mi.dx = dx
        inp.mi.dy = dy
        inp.mi.mouseData = data
        inp.mi.dwFlags = flags
        inp.mi.time = 0
        inp.mi.dwExtraInfo = None
        self.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))

    # ---------- 轨迹生成 ----------
    def _bezier(self, p0, p1, p2, p3, t):
        """三次贝塞尔插值"""
        return (
            (1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t ** 2 * p2[0] + t ** 3 * p3[0],
            (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t ** 2 * p2[1] + t ** 3 * p3[1]
        )

    def _perlin(self, x: float) -> float:
        """简易 1D Perlin 噪声"""
        return (math.sin(x * 12.9898) * 43758.5453) % 1

    def _human_path(self, start: Tuple[int, int], end: Tuple[int, int], steps: int) -> List[Tuple[int, int]]:
        """生成拟人轨迹"""
        # 控制点：起点、中间随机偏移、终点
        mid = ((start[0] + end[0]) // 2, (start[1] + end[1]) // 2)
        offset = random.randint(-30, 30)
        cp1 = (mid[0] + offset, mid[1] + offset)
        cp2 = (mid[0] - offset, mid[1] - offset)

        path = []
        for i in range(steps + 1):
            t = i / steps
            x, y = self._bezier(start, cp1, cp2, end, t)
            # 添加微抖动
            jitter = self._perlin(t * 100) * 2 - 1
            x += jitter * 2
            y += jitter * 2
            path.append((int(x), int(y)))
        return path

    # ---------- 平滑移动 ----------
    def move_to(self, x: int, y: int, duration: float = 0.5, human: bool = True, fps: int = 60):
        """平滑移动到目标坐标"""
        start = self._get_pos()
        end = (x, y)
        steps = max(1, int(duration * fps))
        interval = duration / steps

        if human:
            path = self._human_path(start, end, steps)
        else:
            path = [
                (
                    int(start[0] + (end[0] - start[0]) * i / steps),
                    int(start[1] + (end[1] - start[1]) * i / steps)
                )
                for i in range(steps + 1)
            ]

        for px, py in path:
            if self._stop_flag:
                break
            self._set_pos(px, py)
            time.sleep(interval)

    # ---------- 点击 ----------
    def click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left"):
        """单击"""
        if x is not None and y is not None:
            self.move_to(x, y)
        btn_down, btn_up = {
            "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
            "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
            "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP)
        }[button]
        self._send_input(btn_down)
        time.sleep(random.uniform(0.01, 0.05))
        self._send_input(btn_up)
    # ---------- 双击 ----------
    def double_click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left"):
        """双击"""
        self.click(x, y, button)
        time.sleep(random.uniform(0.05, 0.15))
        self.click(button=button)

    # ---------- 拖拽 ----------
    def drag(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.5, button: str = "left"):
        """拖拽"""
        self.move_to(x1, y1)
        btn_down, _ = {
            "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
            "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
            "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP)
        }[button]
        self._send_input(btn_down)
        time.sleep(0.05)
        self.move_to(x2, y2, duration)
        self._send_input(MOUSEEVENTF_LEFTUP)

    # ---------- 滚轮 ----------
    def scroll(self, clicks: int = 1):
        """滚轮滚动（正数向上，负数向下）"""
        data = clicks * 120
        self._send_input(MOUSEEVENTF_WHEEL, data=data)

    # ---------- 中断 ----------
    def stop(self):
        """中断当前操作"""
        self._stop_flag = True

    def reset(self):
        """重置中断标志"""
        self._stop_flag = False
    # ---------- 按下左键 -------
    def left_down(self) -> None:
        """按住左键不松开"""
        self.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    # ---------- 按下右键 -------
    def left_up(self) -> None:
        """松开左键"""
        self.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)



am = AutoMouse()
