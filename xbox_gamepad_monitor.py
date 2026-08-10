"""Xbox 手柄实时状态可视化（Pygame）。

页面包含：
  - 左右摇杆：大圆 + 实心小圆，实时显示摇杆位置（与真实摇杆方向一致）；
  - 左右扳机 LT/RT：垂直滑块；
  - 按键：A/B/X/Y、LB/RB、Back/Start、Guide、LS/RS（摇杆按压）按下变红，释放为绿色；
  - 十字键：无外圈圆，支持按键型与帽子型两种手柄。

首次启动（或映射文件不存在时）会进入交互式键位校准：
按提示实际操作摇杆 / 扳机 / 按键 / 十字键，向导会实时记录你的操作，
完成后按 Enter 确认并进入下一项；映射自动保存到 xbox_gamepad_mapping.json。

操作：ESC 退出，R 重新检测手柄，C 重新校准键位。
命令行参数：--calibrate 强制重新校准。
"""

import json
import math
import os
import platform
import sys

import pygame

# --------------------------------------------------------------------------
# 基础配置
# --------------------------------------------------------------------------
WIDTH, HEIGHT = 1120, 640
FPS = 60

BG = (24, 26, 32)          # 窗口背景
PANEL = (44, 48, 60)       # 控件底板
BORDER = (140, 150, 170)   # 描边
TRACK = (58, 62, 76)       # 滑块轨道
TRIGGER_FILL = (0, 150, 255)
STICK_DOT = (96, 200, 255)
STICK_DOT_EDGE = (210, 240, 255)
GREEN = (76, 175, 80)      # 释放
RED = (244, 67, 54)        # 按下
TEXT = (235, 238, 245)
TEXT_DIM = (150, 158, 172)

STICK_DEADZONE = 0.08          # 摇杆死区
AXIS_DETECT_THRESHOLD = 0.30   # 校准摇杆时的触发阈值
TRIGGER_DETECT_THRESHOLD = 0.10  # 校准扳机时的触发阈值
STICK_BIG_R = 90
STICK_SMALL_R = 28

def app_dir() -> str:
    """返回程序所在目录：源码运行时为脚本目录，打包后为可执行文件所在目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


MAPPING_PATH = os.path.join(app_dir(), "xbox_gamepad_mapping.json")

def app_version() -> str:
    """读取打包时注入的版本号（version.txt）；源码运行返回空字符串。"""
    try:
        base = getattr(sys, "_MEIPASS", app_dir())
        with open(os.path.join(base, "version.txt"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


# 页面布局
LT_RECT = pygame.Rect(80, 120, 24, 160)
RT_RECT = pygame.Rect(1016, 120, 24, 160)
LB_RECT = pygame.Rect(180, 132, 96, 34)
RB_RECT = pygame.Rect(844, 132, 96, 34)
LEFT_STICK = (380, 430)
RIGHT_STICK = (740, 430)
DPAD_CENTER = (190, 430)
ABXY = {"A": (940, 490), "B": (1000, 430), "X": (880, 430), "Y": (940, 370)}
ABXY_R = 26
BACK_RECT = pygame.Rect(478, 360, 78, 30)
START_RECT = pygame.Rect(564, 360, 78, 30)
GUIDE_POS = (560, 108)
GUIDE_R = 15
LS_INDICATOR = (380, 570)
RS_INDICATOR = (740, 570)

BUTTON_ORDER = ("A", "B", "X", "Y", "LB", "RB", "BACK", "START", "GUIDE", "LS", "RS")
DPAD_ORDER = ("up", "down", "left", "right")

# 校准项目：(类型, 键名, 中文提示, 英文提示, 期望归一化方向)
# 摇杆 X：左为 -1、右为 +1；摇杆 Y：上为 +1、下为 -1
CALIBRATION_ITEMS = [
    ("axes", "lx", "请向左推动【左摇杆】，完成后按 Enter 确认", "Push the LEFT stick to the LEFT, then press Enter", -1),
    ("axes", "ly", "请向上推动【左摇杆】，完成后按 Enter 确认", "Push the LEFT stick UP, then press Enter", 1),
    ("axes", "rx", "请向右推动【右摇杆】，完成后按 Enter 确认", "Push the RIGHT stick to the RIGHT, then press Enter", 1),
    ("axes", "ry", "请向上推动【右摇杆】，完成后按 Enter 确认", "Push the RIGHT stick UP, then press Enter", 1),
    ("triggers", "lt", "请按下【左扳机 LT】，完成后按 Enter 确认", "Press the LEFT trigger (LT), then press Enter", None),
    ("triggers", "rt", "请按下【右扳机 RT】，完成后按 Enter 确认", "Press the RIGHT trigger (RT), then press Enter", None),
    ("buttons", "A", "请按下【A 键】，完成后按 Enter 确认", "Press the A button, then press Enter", None),
    ("buttons", "B", "请按下【B 键】，完成后按 Enter 确认", "Press the B button, then press Enter", None),
    ("buttons", "X", "请按下【X 键】，完成后按 Enter 确认", "Press the X button, then press Enter", None),
    ("buttons", "Y", "请按下【Y 键】，完成后按 Enter 确认", "Press the Y button, then press Enter", None),
    ("buttons", "LB", "请按下【LB 肩键】，完成后按 Enter 确认", "Press the LB bumper, then press Enter", None),
    ("buttons", "RB", "请按下【RB 肩键】，完成后按 Enter 确认", "Press the RB bumper, then press Enter", None),
    ("buttons", "BACK", "请按下【Back 键】，完成后按 Enter 确认", "Press the Back button, then press Enter", None),
    ("buttons", "START", "请按下【Start 键】，完成后按 Enter 确认", "Press the Start button, then press Enter", None),
    ("buttons", "GUIDE", "请按下【Guide（Xbox 键）】，完成后按 Enter 确认", "Press the Guide (Xbox) button, then press Enter", None),
    ("buttons", "LS", "请按下【左摇杆】，完成后按 Enter 确认", "Press down the LEFT stick, then press Enter", None),
    ("buttons", "RS", "请按下【右摇杆】，完成后按 Enter 确认", "Press down the RIGHT stick, then press Enter", None),
    ("dpad", "up", "请按下十字键【上】方向，完成后按 Enter 确认", "Press the D-Pad UP, then press Enter", None),
    ("dpad", "down", "请按下十字键【下】方向，完成后按 Enter 确认", "Press the D-Pad DOWN, then press Enter", None),
    ("dpad", "left", "请按下十字键【左】方向，完成后按 Enter 确认", "Press the D-Pad LEFT, then press Enter", None),
    ("dpad", "right", "请按下十字键【右】方向，完成后按 Enter 确认", "Press the D-Pad RIGHT, then press Enter", None),
]


# --------------------------------------------------------------------------
# 映射（默认 / 加载 / 保存）
# --------------------------------------------------------------------------
def default_mapping() -> dict:
    """默认映射。

    非 macOS 默认值已按本机实际手柄的报告调整：LT/RT 轴互换、
    摇杆 Y 方向取反。首次启动校准后会被实际测得的值覆盖。
    """
    if platform.system() == "Darwin":
        axes = {
            "lx": {"axis": 0, "sign": 1}, "ly": {"axis": 1, "sign": -1},
            "rx": {"axis": 3, "sign": 1}, "ry": {"axis": 4, "sign": -1},
        }
        triggers = {"lt": {"axis": 2, "sign": 1}, "rt": {"axis": 5, "sign": 1}}
    else:
        axes = {
            "lx": {"axis": 0, "sign": 1}, "ly": {"axis": 1, "sign": 1},
            "rx": {"axis": 2, "sign": 1}, "ry": {"axis": 3, "sign": 1},
        }
        triggers = {"lt": {"axis": 5, "sign": 1}, "rt": {"axis": 4, "sign": 1}}
    buttons = {
        "A": 0, "B": 1, "X": 2, "Y": 3,
        "LB": 4, "RB": 5, "BACK": 6, "START": 7,
        "GUIDE": 8, "LS": 9, "RS": 10,
    }
    dpad = {
        "up": {"hat": 0, "dir": [0, 1]}, "down": {"hat": 0, "dir": [0, -1]},
        "left": {"hat": 0, "dir": [-1, 0]}, "right": {"hat": 0, "dir": [1, 0]},
    }
    return {"axes": axes, "triggers": triggers, "buttons": buttons, "dpad": dpad}


def merge_mapping(saved) -> dict:
    """用默认值补全缺失项，避免旧版本映射文件导致崩溃。"""
    base = default_mapping()
    if not isinstance(saved, dict):
        return base
    for kind in ("axes", "triggers", "buttons", "dpad"):
        for key, default_val in base[kind].items():
            val = saved.get(kind, {}).get(key)
            if val is not None:
                base[kind][key] = val
    return base


def load_mapping() -> dict:
    if os.path.exists(MAPPING_PATH):
        try:
            with open(MAPPING_PATH, "r", encoding="utf-8") as f:
                return merge_mapping(json.load(f))
        except Exception as exc:
            print(f"映射文件读取失败，将重新校准: {exc}")
    return default_mapping()


def save_mapping(mapping) -> None:
    with open(MAPPING_PATH, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)


# --------------------------------------------------------------------------
# 数值读取
# --------------------------------------------------------------------------
def deadzone(v: float) -> float:
    return 0.0 if abs(v) < STICK_DEADZONE else v


def read_stick(joy, cfg: dict) -> float:
    """归一化摇杆值：X 左负右正，Y 上正下负。"""
    return deadzone(cfg["sign"] * joy.get_axis(cfg["axis"]))


def read_trigger(joy, cfg: dict) -> float:
    """扳机 0.0（松）~ 1.0（满按）。"""
    return max(0.0, min(1.0, cfg["sign"] * joy.get_axis(cfg["axis"])))


# --------------------------------------------------------------------------
# 字体与文本
# --------------------------------------------------------------------------
def load_fonts():
    """加载字体字典；返回 (字体, 是否找到中文字体)。"""
    cjk = False
    fonts = {}
    for key, size in (("tiny", 16), ("small", 20), ("medium", 26), ("big", 34)):
        path = None
        for name in (
            "notosanscjksc", "notosanscjk", "wenquanyimicrohei",
            "wqymicrohei", "droidsansfallback", "microsoftyahei",
            "pingfangsc",
        ):
            path = pygame.font.match_font(name)
            if path:
                cjk = True
                break
        fonts[key] = pygame.font.Font(path, size) if path else pygame.font.SysFont(None, size)
    return fonts, cjk


# --------------------------------------------------------------------------
# 绘制辅助
# --------------------------------------------------------------------------
def draw_text(screen, font, text, pos, color=TEXT, center=False):
    surf = font.render(text, True, color)
    rect = surf.get_rect()
    if center:
        rect.center = pos
    else:
        rect.topleft = pos
    screen.blit(surf, rect)
    return rect


def draw_stick(screen, fonts, center, ind_pos, x_val, y_val, label, click_pressed):
    bx, by = center
    big_r, small_r = STICK_BIG_R, STICK_SMALL_R

    pygame.draw.circle(screen, PANEL, center, big_r)
    pygame.draw.circle(screen, BORDER, center, big_r, 3)

    # 十字准线
    pygame.draw.line(screen, (80, 88, 104), (bx - big_r, by), (bx + big_r, by), 1)
    pygame.draw.line(screen, (80, 88, 104), (bx, by - big_r), (bx, by + big_r), 1)

    # 中性位置小标记
    pygame.draw.circle(screen, (90, 96, 110), center, 5)

    # 小实心圆：X 右正左负；Y 上正下负（绘制时取反）
    max_d = big_r - small_r - 6
    dot = (int(bx + x_val * max_d), int(by - y_val * max_d))
    pygame.draw.circle(screen, STICK_DOT, dot, small_r)
    pygame.draw.circle(screen, STICK_DOT_EDGE, dot, small_r, 2)

    # 标签与数值
    draw_text(screen, fonts["small"], label, (bx, by + big_r + 6), TEXT_DIM, center=True)
    draw_text(
        screen,
        fonts["tiny"],
        f"X {x_val:+.2f}  Y {y_val:+.2f}",
        (bx, by + big_r + 28),
        TEXT_DIM,
        center=True,
    )

    # 摇杆按压指示（LS/RS 按下变红）
    color = RED if click_pressed else GREEN
    pygame.draw.circle(screen, color, ind_pos, 10)
    pygame.draw.circle(screen, BORDER, ind_pos, 10, 2)


def draw_trigger(screen, fonts, rect, value, label):
    pygame.draw.rect(screen, TRACK, rect, border_radius=8)
    fill_h = int(rect.height * value)
    if fill_h > 0:
        fill_rect = pygame.Rect(rect.x, rect.bottom - fill_h, rect.width, fill_h)
        pygame.draw.rect(screen, TRIGGER_FILL, fill_rect, border_radius=8)
    pygame.draw.rect(screen, BORDER, rect, 2, border_radius=8)

    draw_text(screen, fonts["small"], label, (rect.centerx, rect.top - 24), TEXT, center=True)
    draw_text(
        screen, fonts["tiny"], f"{value:.2f}",
        (rect.centerx, rect.bottom + 22), TEXT_DIM, center=True,
    )


def draw_rect_button(screen, fonts, rect, pressed, label, radius=10):
    color = RED if pressed else GREEN
    pygame.draw.rect(screen, color, rect, border_radius=radius)
    pygame.draw.rect(screen, BORDER, rect, 2, border_radius=radius)
    draw_text(
        screen, fonts["small"], label, rect.center,
        (255, 255, 255) if pressed else (15, 25, 15), center=True,
    )


def draw_circle_button(screen, fonts, pos, radius, pressed, label):
    color = RED if pressed else GREEN
    pygame.draw.circle(screen, color, pos, radius)
    pygame.draw.circle(screen, BORDER, pos, radius, 2)
    draw_text(
        screen, fonts["medium"], label, pos,
        (255, 255, 255) if pressed else (15, 25, 15), center=True,
    )


def draw_dpad(screen, fonts, pressed):
    """十字键：圆角方形底板 + 十字臂（无外圈圆），按下方向变红。"""
    cx, cy = DPAD_CENTER
    arm_w, total = 44, 150
    h = total // 2

    pygame.draw.rect(screen, PANEL, pygame.Rect(cx - h, cy - h, total, total), border_radius=18)

    parts = {
        "up": pygame.Rect(cx - arm_w // 2, cy - h, arm_w, h),
        "down": pygame.Rect(cx - arm_w // 2, cy, arm_w, h),
        "left": pygame.Rect(cx - h, cy - arm_w // 2, h, arm_w),
        "right": pygame.Rect(cx, cy - arm_w // 2, h, arm_w),
    }
    for key, rect in parts.items():
        color = RED if pressed.get(key) else GREEN
        pygame.draw.rect(screen, color, rect, border_radius=8)
        pygame.draw.rect(screen, BORDER, rect, 2, border_radius=8)

    pygame.draw.circle(screen, PANEL, (cx, cy), 13)
    pygame.draw.circle(screen, BORDER, (cx, cy), 13, 2)


# --------------------------------------------------------------------------
# 键位校准向导
# --------------------------------------------------------------------------
def poll_wizard_events():
    """返回 quit / skip / confirm / lost / None。"""
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return "quit"
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return "skip"
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                return "confirm"
        if event.type == pygame.JOYDEVICEREMOVED:
            return "lost"
    return None


def draw_calibration_screen(screen, fonts, joy, prompt, step, total, status, cjk):
    screen.fill(BG)
    draw_text(
        screen, fonts["medium"],
        f"键位校准  {step}/{total}" if cjk else f"Calibration  {step}/{total}",
        (WIDTH // 2, 70), TEXT, center=True,
    )
    draw_text(screen, fonts["big"], prompt, (WIDTH // 2, 170), TEXT, center=True)
    draw_text(screen, fonts["small"], status, (WIDTH // 2, 245), TEXT_DIM, center=True)
    hint = (
        "Enter = 确认本项 | ESC = 跳过（使用默认映射） | 关闭窗口 = 退出"
        if cjk else "Enter = confirm | ESC = skip (keep default) | Close window = quit"
    )
    draw_text(screen, fonts["tiny"], hint, (WIDTH // 2, 290), TEXT_DIM, center=True)

    # 实时数值回显：正在变化的轴用高亮色显示
    for i in range(joy.get_numaxes()):
        x = 90 + (i % 4) * 220
        y = 350 + (i // 4) * 28
        v = joy.get_axis(i)
        color = STICK_DOT if abs(v) > 0.20 else TEXT
        draw_text(screen, fonts["tiny"], f"A{i}: {v:+.2f}", (x, y), color)
    pressed_btns = [i for i in range(joy.get_numbuttons()) if joy.get_button(i)]
    label = "按下的按键: " if cjk else "Pressed buttons: "
    if pressed_btns:
        draw_text(screen, fonts["tiny"], label + ",".join(str(i) for i in pressed_btns), (90, 440), TEXT)
    hats = [str(joy.get_hat(h)) for h in range(joy.get_numhats())]
    hat_label = "十字键: " if cjk else "D-Pad: "
    draw_text(screen, fonts["tiny"], hat_label + ", ".join(hats), (90, 470), TEXT)


def wait_settled(screen, fonts, clock, joy, prompt, step, total, cjk, axes,
                 zh, en, settle_frames=3, max_frames=48):
    """等待候选轴稳定（相邻帧变化很小）后返回，用于干净地采集基线。

    不要求轴值归零，因此兼容 0~1 与 -1~1 两种扳机驱动。
    返回 quit / skip / lost / None（None 表示可以继续）。
    """
    prev = {a: joy.get_axis(a) for a in axes}
    stable = 0
    for _ in range(max_frames):
        ev = poll_wizard_events()
        if ev == "quit":
            return "quit"
        if ev == "skip":
            return "skip"
        if ev == "lost":
            return "lost"
        cur = {a: joy.get_axis(a) for a in axes}
        changed = any(abs(cur[a] - prev[a]) > 0.05 for a in axes)
        stable = 0 if changed else stable + 1
        prev = cur
        if stable >= settle_frames:
            return None
        draw_calibration_screen(screen, fonts, joy, prompt, step, total,
                                zh if cjk else en, cjk)
        pygame.display.flip()
        clock.tick(FPS)
    return None


def confirm_step(screen, fonts, clock, joy, prompt, step, total, cjk, get_candidate, fmt):
    """通用校准循环：实时记录最后一次检测到的操作，用户按 Enter 确认后进入下一项。

    get_candidate(joy) 返回当前检测到的操作（None 表示未检测到）；
    fmt(candidate) 生成已记录内容的文字。
    返回 (candidate 或 None, 状态: ok/skip/quit/lost)。
    """
    candidate = None
    warning = ""
    warning_frames = 0
    while True:
        ev = poll_wizard_events()
        if ev == "quit":
            return None, "quit"
        if ev == "skip":
            return None, "skip"
        if ev == "lost":
            return None, "lost"
        if ev == "confirm":
            if candidate is not None:
                return candidate, "ok"
            warning = (
                "未检测到操作，请先操作后再按 Enter" if cjk
                else "No input detected - operate the control first, then press Enter"
            )
            warning_frames = FPS * 2

        detected = get_candidate(joy)
        if detected is not None:
            candidate = detected
            warning = ""
            warning_frames = 0

        if warning_frames > 0:
            status = warning
            warning_frames -= 1
        elif candidate is not None:
            status = (
                ("已记录：" if cjk else "Recorded: ") + fmt(candidate) +
                ("　按 Enter 确认" if cjk else " - press Enter to confirm")
            )
        else:
            status = "等待操作…" if cjk else "Waiting..."
        draw_calibration_screen(screen, fonts, joy, prompt, step, total, status, cjk)
        pygame.display.flip()
        clock.tick(FPS)


def calibrate_axis(screen, fonts, clock, joy, prompt, step, total, expected, used_axes, cjk):
    """校准一个摇杆轴：基线相对检测，只认实际操作产生的变化。"""
    candidates = [a for a in range(joy.get_numaxes()) if a not in used_axes]
    outcome = wait_settled(
        screen, fonts, clock, joy, prompt, step, total, cjk, candidates,
        "请先松开摇杆…", "Release the stick first...",
    )
    if outcome:
        return None, outcome
    baseline = {a: joy.get_axis(a) for a in candidates}

    def get_candidate(joy):
        best_axis, best_dev = None, 0.0
        for a, base in baseline.items():
            dev = joy.get_axis(a) - base
            if abs(dev) > AXIS_DETECT_THRESHOLD and abs(dev) > abs(best_dev):
                best_axis, best_dev = a, dev
        if best_axis is None:
            return None
        sign = int(expected * math.copysign(1.0, best_dev))
        return {"axis": best_axis, "sign": sign}
    return confirm_step(
        screen, fonts, clock, joy, prompt, step, total, cjk, get_candidate,
        lambda cfg: f"axis {cfg['axis']} sign {cfg['sign']:+d}",
    )


def calibrate_trigger(screen, fonts, clock, joy, prompt, step, total, used_axes, cjk):
    """校准一个扳机轴（支持 0~1、-1~1 及正负半轴共用的驱动）。"""
    candidates = [a for a in range(joy.get_numaxes()) if a not in used_axes]
    outcome = wait_settled(
        screen, fonts, clock, joy, prompt, step, total, cjk, candidates,
        "请先松开扳机…", "Release the triggers first...",
    )
    if outcome:
        return None, outcome

    baseline = {a: joy.get_axis(a) for a in candidates}
    def get_candidate(joy):
        best_axis, best_dev = None, 0.0
        for a, base in baseline.items():
            dev = joy.get_axis(a) - base
            if abs(dev) > TRIGGER_DETECT_THRESHOLD and abs(dev) > abs(best_dev):
                best_axis, best_dev = a, dev
        if best_axis is None:
            return None
        sign = 1 if best_dev > 0 else -1
        return {"axis": best_axis, "sign": sign}
    result, status = confirm_step(
        screen, fonts, clock, joy, prompt, step, total, cjk, get_candidate,
        lambda cfg: f"axis {cfg['axis']} sign {cfg['sign']:+d}",
    )
    if status != "ok":
        return result, status

    # 确认后等待扳机回到基线附近，避免把“松开上一把扳机”误判为下一把扳机
    axis = result["axis"]
    wait_frames = 0
    while True:
        ev = poll_wizard_events()
        if ev == "quit":
            return None, "quit"
        if ev == "lost":
            return None, "lost"
        if ev == "skip" or abs(joy.get_axis(axis) - baseline[axis]) < 0.15:
            break
        wait_frames += 1
        if wait_frames > FPS * 5:
            print("警告：扳机未完全松开，继续下一步（若映射异常请重新校准）")
            break
        draw_calibration_screen(
            screen, fonts, joy, prompt, step, total,
            "请松开扳机…" if cjk else "Release the trigger...", cjk,
        )
        pygame.display.flip()
        clock.tick(FPS)
    return result, "ok"


def calibrate_button(screen, fonts, clock, joy, prompt, step, total, used_buttons, cjk):
    def get_candidate(joy):
        for i in range(joy.get_numbuttons()):
            if i not in used_buttons and joy.get_button(i):
                return i
        return None
    return confirm_step(
        screen, fonts, clock, joy, prompt, step, total, cjk, get_candidate,
        lambda i: f"button {i}",
    )


def calibrate_dpad(screen, fonts, clock, joy, prompt, step, total, used_buttons, used_dpads, cjk):
    def get_candidate(joy):
        # 按钮型十字键（优先，用户手柄为此类型）
        for i in range(joy.get_numbuttons()):
            if i not in used_buttons and joy.get_button(i):
                return {"type": "button", "button": i}
        # 帽子型十字键（兼容其他手柄）
        for h in range(joy.get_numhats()):
            state = joy.get_hat(h)
            if state != (0, 0) and tuple(state) not in used_dpads:
                return {"hat": h, "dir": list(state)}
        return None
    return confirm_step(
        screen, fonts, clock, joy, prompt, step, total, cjk, get_candidate,
        lambda cfg: (f"button {cfg['button']}" if cfg.get("type") == "button"
                     else f"hat {cfg['hat']} dir {cfg['dir']}"),
    )


def run_calibration(screen, fonts, clock, joy, cjk, mapping):
    """交互式校准全部键位。返回 (新映射, 状态: ok/quit/lost)。"""
    new_mapping = json.loads(json.dumps(mapping))
    used_axes, used_buttons, used_dpads = set(), set(), set()
    total = len(CALIBRATION_ITEMS)

    for idx, (kind, key, zh, en, expected) in enumerate(CALIBRATION_ITEMS, start=1):
        prompt = zh if cjk else en
        if kind == "axes":
            result, status = calibrate_axis(
                screen, fonts, clock, joy, prompt, idx, total, expected, used_axes, cjk
            )
        elif kind == "triggers":
            result, status = calibrate_trigger(
                screen, fonts, clock, joy, prompt, idx, total, used_axes, cjk
            )
        elif kind == "buttons":
            result, status = calibrate_button(
                screen, fonts, clock, joy, prompt, idx, total, used_buttons, cjk
            )
        else:
            result, status = calibrate_dpad(
                screen, fonts, clock, joy, prompt, idx, total, used_buttons, used_dpads, cjk
            )

        if status in ("quit", "lost"):
            return new_mapping, status
        if status == "skip" or result is None:
            print(f"  [{idx}/{total}] 跳过 {key}（保留默认）")
            continue

        if kind == "axes":
            new_mapping["axes"][key] = result
            used_axes.add(result["axis"])
            print(f"  [{idx}/{total}] {key}: axis={result['axis']} sign={result['sign']:+d}")
        elif kind == "triggers":
            new_mapping["triggers"][key] = result
            print(f"  [{idx}/{total}] {key}: axis={result['axis']} sign={result['sign']:+d}")
        elif kind == "buttons":
            new_mapping["buttons"][key] = result
            used_buttons.add(result)
            print(f"  [{idx}/{total}] {key}: button={result}")
        else:
            new_mapping["dpad"][key] = result
            if result.get("type") == "button":
                used_buttons.add(result["button"])
            else:
                used_dpads.add(tuple(result["dir"]))
            print(f"  [{idx}/{total}] {key}: {result}")

    return new_mapping, "ok"


# --------------------------------------------------------------------------
# 主循环
# --------------------------------------------------------------------------
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Xbox Gamepad Monitor")
    clock = pygame.time.Clock()
    fonts, cjk = load_fonts()

    mapping = load_mapping()
    first_time = not os.path.exists(MAPPING_PATH)
    force_calibrate = "--calibrate" in sys.argv
    joy = None

    def open_joystick():
        nonlocal joy
        if pygame.joystick.get_count() > 0:
            joy = pygame.joystick.Joystick(0)
            joy.init()
            print(f"手柄已连接: {joy.get_name()}")
            print(f"轴数: {joy.get_numaxes()}  按键数: {joy.get_numbuttons()}  帽子数: {joy.get_numhats()}")
        else:
            joy = None

    def run_calibration_flow():
        """启动校准向导。返回 True 表示需要退出程序。"""
        nonlocal mapping, first_time, joy
        if joy is None:
            print("未连接手柄，无法校准。")
            return False
        print("开始键位校准……")
        new_mapping, status = run_calibration(screen, fonts, clock, joy, cjk, mapping)
        if status == "quit":
            return True
        if status == "lost":
            print("校准过程中手柄断开，返回主界面。")
            joy = None
            return False
        mapping = new_mapping
        save_mapping(mapping)
        first_time = False
        print(f"键位映射已保存: {MAPPING_PATH}")
        return False

    open_joystick()
    if force_calibrate and joy is not None:
        if run_calibration_flow():
            pygame.quit()
            sys.exit(0)
    elif first_time and joy is not None:
        run_calibration_flow()

    ver = app_version()
    ver_suffix = f"  v{ver}" if ver else ""
    no_ctrl_text = (("未检测到 Xbox 手柄" + ver_suffix) if cjk
                    else ("No Xbox controller detected" + ver_suffix))
    hint_text = "连接手柄后按 R 重新检测 | C 重新校准 | ESC 退出" if cjk \
        else "Connect controller: R redetect | C calibrate | ESC quit"

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    open_joystick()
                    if first_time and joy is not None:
                        run_calibration_flow()
                elif event.key == pygame.K_c:
                    if run_calibration_flow():
                        running = False
            elif event.type == pygame.JOYDEVICEADDED:
                if joy is None:
                    open_joystick()
                    if first_time and joy is not None:
                        run_calibration_flow()
            elif event.type == pygame.JOYDEVICEREMOVED:
                if joy is not None and event.instance_id == joy.get_instance_id():
                    joy = None

        screen.fill(BG)
        title = f"Xbox Gamepad Monitor - {joy.get_name()}{ver_suffix}" if joy else no_ctrl_text
        draw_text(screen, fonts["medium"], title, (WIDTH // 2, 34), TEXT, center=True)

        if joy is None:
            draw_text(screen, fonts["big"], no_ctrl_text, (WIDTH // 2, HEIGHT // 2 - 20), TEXT, center=True)
            draw_text(screen, fonts["small"], hint_text, (WIDTH // 2, HEIGHT // 2 + 30), TEXT_DIM, center=True)
            pygame.display.flip()
            clock.tick(FPS)
            continue

        # ---- 读取状态（使用校准后的映射） ----
        left = (read_stick(joy, mapping["axes"]["lx"]), read_stick(joy, mapping["axes"]["ly"]))
        right = (read_stick(joy, mapping["axes"]["rx"]), read_stick(joy, mapping["axes"]["ry"]))
        lt = read_trigger(joy, mapping["triggers"]["lt"])
        rt = read_trigger(joy, mapping["triggers"]["rt"])
        buttons = {k: bool(joy.get_button(mapping["buttons"][k])) for k in BUTTON_ORDER}
        dpad_pressed = {}
        for d in DPAD_ORDER:
            cfg = mapping["dpad"][d]
            if cfg.get("type") == "button":
                dpad_pressed[d] = bool(joy.get_button(cfg["button"]))
            else:
                dpad_pressed[d] = joy.get_hat(cfg.get("hat", 0)) == tuple(cfg.get("dir", [0, 0]))

        # ---- 绘制 ----
        draw_trigger(screen, fonts, LT_RECT, lt, "LT")
        draw_trigger(screen, fonts, RT_RECT, rt, "RT")
        draw_rect_button(screen, fonts, LB_RECT, buttons["LB"], "LB")
        draw_rect_button(screen, fonts, RB_RECT, buttons["RB"], "RB")
        draw_dpad(screen, fonts, dpad_pressed)
        draw_stick(screen, fonts, LEFT_STICK, LS_INDICATOR, left[0], left[1], "L", buttons["LS"])
        draw_stick(screen, fonts, RIGHT_STICK, RS_INDICATOR, right[0], right[1], "R", buttons["RS"])
        draw_rect_button(screen, fonts, BACK_RECT, buttons["BACK"], "BACK", radius=8)
        draw_rect_button(screen, fonts, START_RECT, buttons["START"], "START", radius=8)
        draw_circle_button(screen, fonts, GUIDE_POS, GUIDE_R, buttons["GUIDE"], "X")
        for label, pos in ABXY.items():
            draw_circle_button(screen, fonts, pos, ABXY_R, buttons[label], label)
        draw_text(screen, fonts["tiny"], hint_text, (WIDTH // 2, HEIGHT - 18), TEXT_DIM, center=True)

        pygame.display.flip()
        clock.tick(FPS)

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
