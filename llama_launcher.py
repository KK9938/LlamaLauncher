# -*- coding: utf-8 -*-
"""Llama 一键启动器 - 圆角双主题版"""
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from datetime import datetime
from tkinter import BooleanVar, Canvas, Entry, Frame, Label, StringVar, Text, Tk, messagebox
from tkinter import filedialog, ttk

try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(APP_DIR, "config.json")
LOG_DIR = os.path.join(APP_DIR, "logs")

DEFAULT_CONFIG = {
    "llama_server": r"D:\llama.cpp\llama-server.exe",
    "llama_cli": r"D:\llama.cpp\llama-cli.exe",
    "model_folder": r"D:\llama.cpp\models\lmstudio-community\Qwen3.8-27B-GGUF",
    "ngl": 24, "ctx": 8192, "threads": 10, "port": 8080, "host": "127.0.0.1",
    "auto_open_browser": True, "minimize_to_tray": True, "log_to_file": True, "theme": "dark",
}

PRESETS = {"低显存模式": {"ngl": 8, "ctx": 4096}, "均衡模式": {"ngl": 24, "ctx": 8192}, "高性能模式": {"ngl": 99, "ctx": 16384}}

THEMES = {
    "dark": {
        "name": "深色", "bg": "#18191d", "card": "#202126", "card_border": "#2f3138",
        "input": "#282a31", "text": "#f1f2f6", "muted": "#8e919c", "accent": "#5b8dff",
        "accent_hover": "#7aa5ff", "accent_active": "#4672e0", "success": "#3fb950",
        "success_hover": "#5fd16f", "success_active": "#2e9a3e", "danger": "#e64c4c",
        "danger_hover": "#f56e6e", "danger_active": "#c03a3a", "danger_disabled": "#5c3333",
        "ghost": "#2a2c33", "ghost_hover": "#383b44", "ghost_active": "#1f2126",
        "border": "#363840", "log_bg": "#14151a", "header_start": "#2d3a66", "header_end": "#5b8dff",
    },
    "light": {
        "name": "浅色", "bg": "#f2f3f7", "card": "#ffffff", "card_border": "#e0e2e8",
        "input": "#f7f8fa", "text": "#1f2128", "muted": "#6b6e78", "accent": "#4f8cff",
        "accent_hover": "#3a7aee", "accent_active": "#2a65d5", "success": "#2da44e",
        "success_hover": "#248b3f", "success_active": "#1c7434", "danger": "#d93025",
        "danger_hover": "#b5251c", "danger_active": "#941c15", "danger_disabled": "#e8b4b0",
        "ghost": "#ebedf2", "ghost_hover": "#e0e2e8", "ghost_active": "#d4d7de",
        "border": "#d8dbe2", "log_bg": "#ffffff", "header_start": "#6fa2ff", "header_end": "#a8c5ff",
    },
}

FONT = ("Microsoft YaHei UI", 10)
FONT_BOLD = ("Microsoft YaHei UI", 11, "bold")
FONT_SMALL = ("Microsoft YaHei UI", 9)
FONT_LOG = ("Consolas", 9)
W, H, CORNER, CARD_R, BTN_R = 760, 840, 18, 12, 8


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg.update(json.load(f))
        except Exception:
            pass
    return cfg


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def rounded_rect(canvas, x1, y1, x2, y2, r, fill, outline="", width=0):
    pts = [x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2,
           x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1]
    return canvas.create_polygon(pts, fill=fill, outline=outline, width=width, smooth=True)


def find_candidates():
    roots = []
    for base in (APP_DIR, os.path.dirname(APP_DIR), os.getcwd()):
        roots.extend([base, os.path.join(base, "llama.cpp")])
    roots.extend([r"D:\llama.cpp", r"C:\llama.cpp", r"E:\llama.cpp"])
    return [os.path.abspath(p) for p in roots]


def find_exe(name):
    for root in find_candidates():
        p = os.path.join(root, name)
        if os.path.isfile(p):
            return p
    return None


def pick_model_subdir(models_dir):
    if not os.path.isdir(models_dir):
        return None
    subs = [os.path.join(models_dir, d) for d in os.listdir(models_dir) if os.path.isdir(os.path.join(models_dir, d))]
    valid = [s for s in subs if any(f.lower().endswith(".gguf") for f in os.listdir(s))]
    if len(valid) == 1:
        return valid[0]
    if len(valid) > 1:
        return models_dir
    if any(f.lower().endswith(".gguf") for f in os.listdir(models_dir)):
        return models_dir
    return None


def find_model_folder():
    for root in find_candidates():
        if os.path.isdir(root):
            picked = pick_model_subdir(root)
            if picked:
                return picked
    return None


def auto_detect(cfg):
    changed = False
    if not os.path.isfile(cfg.get("llama_server", "")):
        f = find_exe("llama-server.exe")
        if f:
            cfg["llama_server"] = f
            changed = True
    if not os.path.isfile(cfg.get("llama_cli", "")):
        f = find_exe("llama-cli.exe")
        if f:
            cfg["llama_cli"] = f
            changed = True
    if not os.path.isdir(cfg.get("model_folder", "")):
        f = find_model_folder()
        if f:
            cfg["model_folder"] = f
            changed = True
    return cfg, changed


class RoundedButton(Canvas):
    def __init__(self, parent, text, command=None, color="accent", width=80, height=34, font=FONT_BOLD, theme=None, **kw):
        self._t = theme if theme else getattr(parent, "theme", getattr(parent, "_t", THEMES["dark"]))
        super().__init__(parent, width=width, height=height, highlightthickness=0, cursor="hand2", bg=self._t["bg"], **kw)
        self.text = text
        self.command = command
        self.color = color
        self.enabled = True
        self.pressed = False
        self.wid, self.hei = width, height
        self.font = font
        self._draw("normal")
        self.bind("<Enter>", lambda e: self._draw("hover"))
        self.bind("<Leave>", lambda e: self._draw("normal"))
        self.bind("<ButtonPress-1>", lambda e: (self._draw("active"), setattr(self, "pressed", True)))
        self.bind("<ButtonRelease-1>", self._on_release)

    def _color(self, state):
        t = self._t
        if not self.enabled:
            return t.get(self.color + "_disabled", "#555")
        return t.get(self.color + ("_active" if state == "active" else "_hover" if state == "hover" else ""), t.get(self.color, "#888"))

    def _draw(self, state):
        self.delete("all")
        fill = self._color(state)
        rounded_rect(self, 1, 1, self.wid - 1, self.hei - 1, BTN_R, fill)
        off = 1 if state == "active" else 0
        txt_col = self._text_color(fill)
        self.create_text(self.wid // 2, self.hei // 2 + off, text=self.text, fill=txt_col, font=self.font, anchor="center")

    def _text_color(self, hexcol):
        h = hexcol.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return "#1f2128" if (r * 0.299 + g * 0.587 + b * 0.114) > 160 else "#ffffff"

    def _on_release(self, e):
        if self.enabled and self.pressed:
            self._draw("hover")
            if self.command:
                self.command()
        self.pressed = False

    def set_enabled(self, enabled):
        self.enabled = enabled
        self.config(cursor="hand2" if enabled else "arrow")
        self._draw("normal")

    def update_theme(self, theme):
        self._t = theme
        self.config(bg=theme["bg"])
        self._draw("normal")


class RoundedCard(Canvas):
    def __init__(self, parent, height, **kw):
        self._t = parent.theme
        self.theme = parent.theme
        super().__init__(parent, width=700, height=height, highlightthickness=0, bg=self._t["bg"], **kw)
        self.hei = height
        self.pack(fill="x", pady=6)
        self.pack_propagate(False)
        self.update_theme(self._t)

    def update_theme(self, theme):
        self._t = theme
        self.config(bg=theme["bg"])
        self.delete("all")
        rounded_rect(self, 0, 0, 700, self.hei, CARD_R, theme["card"], outline=theme["card_border"], width=1)


class GreenCheck(Frame):
    def __init__(self, parent, text, variable, enabled=True):
        super().__init__(parent)
        self.theme = parent.theme
        self.variable = variable
        self.enabled = enabled
        self.mark = Label(self, font=FONT_BOLD)
        self.mark.pack(side="left")
        self.lbl = Label(self, text=text, font=FONT)
        self.lbl.pack(side="left", padx=(4, 0))
        if enabled:
            self.lbl.bind("<Button-1>", lambda e: self.variable.set(not self.variable.get()))
            self.mark.bind("<Button-1>", lambda e: self.variable.set(not self.variable.get()))
            self.lbl.bind("<Enter>", lambda e: self.lbl.config(fg=self.theme["accent"]))
            self.lbl.bind("<Leave>", lambda e: self.lbl.config(fg=self.theme["text"]))
        self.variable.trace_add("write", lambda *_: self._render())
        self.update_theme(self.theme)

    def update_theme(self, theme):
        self.theme = theme
        self.config(bg=theme["card"])
        self.lbl.config(bg=theme["card"])
        self.mark.config(bg=theme["card"])
        self._render()

    def _render(self):
        if self.variable.get():
            self.mark.config(text="✔", fg=self.theme["success"])
        else:
            self.mark.config(text="☐", fg=self.theme["muted"])
        self.lbl.config(fg=self.theme["text"] if self.enabled else self.theme["muted"])


class LlamaLauncher:
    def __init__(self, root):
        self.root = root
        self.cfg = load_config()
        self.cfg, _ = auto_detect(self.cfg)
        save_config(self.cfg)
        self.theme = THEMES[self.cfg.get("theme", "dark")]
        self.theme_name = self.cfg.get("theme", "dark")
        self.process = None
        self.models = []
        self.tray_icon = None
        self._closing = False
        self._drag = {"x": 0, "y": 0}
        self._widgets = []
        self._preset_btns = []

        self._build_window()
        self._build_ui()
        self._scan_models()
        self._check_paths()
        self._log("启动器已就绪", "info")

    def _build_window(self):
        self.root.title("Llama 一键启动器")
        self.root.geometry(f"{W}x{H}")
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"+{(sw - W) // 2}+{(sh - H) // 2}")
        self.root.resizable(False, False)
        self.root.overrideredirect(True)
        self.root.wm_attributes("-transparentcolor", "magenta")
        self.root.config(bg="magenta")

        self.canvas = Canvas(self.root, width=W, height=H, bg="magenta", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        rounded_rect(self.canvas, 0, 0, W, H, CORNER, self.theme["bg"])

        self.content = Frame(self.canvas, bg=self.theme["bg"])
        self.canvas.create_window((0, 0), window=self.content, anchor="nw", width=W, height=H)

        self.canvas.bind("<Button-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._on_drag)

    def _bind_drag(self, widget):
        widget.bind("<Button-1>", self._start_drag)
        widget.bind("<B1-Motion>", self._on_drag)
        for child in widget.winfo_children():
            child.bind("<Button-1>", self._start_drag)
            child.bind("<B1-Motion>", self._on_drag)

    def _start_drag(self, e):
        if e.y < 50:
            self._drag["x"] = e.x_root - self.root.winfo_x()
            self._drag["y"] = e.y_root - self.root.winfo_y()

    def _on_drag(self, e):
        if e.y < 50:
            self.root.geometry(f"+{e.x_root - self._drag['x']}+{e.y_root - self._drag['y']}")

    def _build_ui(self):
        header = Frame(self.content, bg=self.theme["bg"], height=50)
        header.pack(fill="x", padx=24, pady=(16, 4))
        header.pack_propagate(False)
        self._bind_drag(header)
        Label(header, text="Llama 一键启动器", font=FONT_BOLD, bg=self.theme["bg"], fg=self.theme["text"]).pack(side="left")

        ctrl = Frame(header, bg=self.theme["bg"])
        ctrl.pack(side="right")
        self.theme_btn = RoundedButton(ctrl, text=self.theme["name"], command=self._toggle_theme, color="ghost", width=58, height=28, font=FONT_SMALL, theme=self.theme)
        self.theme_btn.pack(side="left", padx=(0, 10))
        min_lbl = Label(ctrl, text="—", font=FONT_BOLD, bg=self.theme["bg"], fg=self.theme["muted"], cursor="hand2")
        min_lbl.pack(side="left", padx=8)
        min_lbl.bind("<Enter>", lambda e: min_lbl.config(fg=self.theme["text"]))
        min_lbl.bind("<Leave>", lambda e: min_lbl.config(fg=self.theme["muted"]))
        min_lbl.bind("<Button-1>", lambda e: (self.root.iconify(), "break")[1])
        close_lbl = Label(ctrl, text="×", font=("Microsoft YaHei UI", 14, "bold"), bg=self.theme["bg"], fg=self.theme["muted"], cursor="hand2")
        close_lbl.pack(side="left", padx=(8, 0))
        close_lbl.bind("<Enter>", lambda e: close_lbl.config(fg=self.theme["danger"]))
        close_lbl.bind("<Leave>", lambda e: close_lbl.config(fg=self.theme["muted"]))
        close_lbl.bind("<Button-1>", lambda e: self.on_close())

        body = Frame(self.content, bg=self.theme["bg"])
        body.theme = self.theme
        body.pack(fill="both", expand=True, padx=24, pady=(0, 8))

        c1 = RoundedCard(body, 130)
        self._widgets.append(c1)
        Label(c1, text="模型选择", font=FONT_BOLD, bg=self.theme["card"], fg=self.theme["text"]).place(x=16, y=12)
        self.model_var = StringVar()
        self.combo = ttk.Combobox(c1, textvariable=self.model_var, state="readonly", font=FONT)
        self.combo.place(x=16, y=40, width=668)
        self.path_lbl = Label(c1, text="", font=FONT_SMALL, bg=self.theme["card"], fg=self.theme["muted"], anchor="w")
        self.path_lbl.place(x=16, y=70, width=668)
        self.refresh_btn = RoundedButton(c1, "刷新", self._scan_models, "ghost", 70, 30, FONT_SMALL)
        self.refresh_btn.place(x=16, y=90)
        self.locate_btn = RoundedButton(c1, "定位 llama.cpp", self._locate_llama, "ghost", 115, 30, FONT_SMALL)
        self.locate_btn.place(x=94, y=90)
        self.model_btn = RoundedButton(c1, "选择模型文件夹", self._choose_model_folder, "ghost", 135, 30, FONT_SMALL)
        self.model_btn.place(x=217, y=90)

        c2 = RoundedCard(body, 72)
        self._widgets.append(c2)
        Label(c2, text="快速预设", font=FONT_BOLD, bg=self.theme["card"], fg=self.theme["text"]).place(x=16, y=10)
        x0 = 16
        for name in PRESETS:
            btn = RoundedButton(c2, name, lambda n=name: self._apply_preset(n), "ghost", 120, 30, FONT_SMALL)
            self._preset_btns.append(btn)
            btn.place(x=x0, y=38)
            x0 += 128

        c3 = RoundedCard(body, 150)
        self._widgets.append(c3)
        Label(c3, text="参数设置", font=FONT_BOLD, bg=self.theme["card"], fg=self.theme["text"]).place(x=16, y=10)
        self.entries = {}
        params = [("NGL (GPU层数)", "ngl"), ("CTX (上下文)", "ctx"), ("Threads (线程)", "threads"), ("Port (端口)", "port"), ("Host (地址)", "host")]
        for i, (lab, key) in enumerate(params):
            Label(c3, text=lab, font=FONT_SMALL, bg=self.theme["card"], fg=self.theme["muted"]).place(x=16 + (i % 2) * 340, y=42 + (i // 2) * 38)
            e = Entry(c3, font=FONT, relief="flat", width=20)
            e.insert(0, str(self.cfg[key]))
            e.place(x=110 + (i % 2) * 340, y=40 + (i // 2) * 38)
            self.entries[key] = e

        c4 = RoundedCard(body, 110)
        self._widgets.append(c4)
        Label(c4, text="功能选项", font=FONT_BOLD, bg=self.theme["card"], fg=self.theme["text"]).place(x=16, y=10)
        self.var_browser = BooleanVar(value=self.cfg["auto_open_browser"])
        self.var_tray = BooleanVar(value=self.cfg["minimize_to_tray"] and TRAY_AVAILABLE)
        self.var_logfile = BooleanVar(value=self.cfg["log_to_file"])
        txt = "关闭窗口时最小化到系统托盘" + ("" if TRAY_AVAILABLE else "（需安装 pystray）")
        self.g1 = GreenCheck(c4, "启动后自动打开浏览器", self.var_browser)
        self.g1.place(x=16, y=42)
        self.g2 = GreenCheck(c4, txt, self.var_tray, TRAY_AVAILABLE)
        self.g2.place(x=16, y=68)
        self.g3 = GreenCheck(c4, "日志写入文件 (logs/ 目录)", self.var_logfile)
        self.g3.place(x=280, y=42)

        c5 = RoundedCard(body, 70)
        self._widgets.append(c5)
        self.api_btn = RoundedButton(c5, "▶ 启动 API 服务", self.start_server, "accent", 160, 38, FONT_BOLD)
        self.api_btn.place(x=16, y=16)
        self.cli_btn = RoundedButton(c5, "💬 终端对话", self.start_cli, "success", 160, 38, FONT_BOLD)
        self.cli_btn.place(x=188, y=16)
        self.stop_btn = RoundedButton(c5, "■ 停止", self.stop_process, "danger", 160, 38, FONT_BOLD)
        self.stop_btn.place(x=360, y=16)
        self.stop_btn.set_enabled(False)
        self.save_btn = RoundedButton(c5, "💾 保存配置", self.on_save_config, "ghost", 160, 38, FONT_BOLD)
        self.save_btn.place(x=532, y=16)

        c6 = RoundedCard(body, 200)
        self._widgets.append(c6)
        Label(c6, text="运行日志", font=FONT_BOLD, bg=self.theme["card"], fg=self.theme["text"]).place(x=16, y=10)
        self.log = Text(c6, font=FONT_LOG, wrap="word", state="disabled", relief="flat")
        self.log.place(x=16, y=38, width=668, height=150)

        self.status = Frame(self.content, bg=self.theme["bg"], height=24)
        self.status.pack(fill="x", side="bottom", padx=24, pady=(0, 18))
        self.status.pack_propagate(False)
        self.dot = Label(self.status, text="●", font=FONT_SMALL, bg=self.theme["bg"], fg=self.theme["muted"])
        self.dot.pack(side="left")
        self.status_text = Label(self.status, text="空闲", font=FONT_SMALL, bg=self.theme["bg"], fg=self.theme["muted"])
        self.status_text.pack(side="left", padx=(6, 0))

        self._apply_theme()

    def _apply_theme(self):
        t = self.theme
        self.root.config(bg="magenta")
        self.canvas.itemconfig(self.canvas.find_all()[0], fill=t["bg"])
        self.content.config(bg=t["bg"])
        for card in self._widgets:
            card.update_theme(t)
        for btn in [self.theme_btn, self.refresh_btn, self.locate_btn, self.model_btn, self.api_btn, self.cli_btn, self.stop_btn, self.save_btn] + self._preset_btns:
            btn.update_theme(t)
        self.stop_btn.set_enabled(self._is_running())
        for g in [self.g1, self.g2, self.g3]:
            g.update_theme(t)
        self.path_lbl.config(bg=t["card"], fg=t["muted"])
        for e in self.entries.values():
            e.config(bg=t["input"], fg=t["text"], insertbackground=t["text"], highlightbackground=t["border"], highlightcolor=t["accent"], highlightthickness=1)
        s = ttk.Style(self.root)
        s.theme_use("clam")
        s.configure("TCombobox", fieldbackground=t["input"], foreground=t["text"], background=t["input"], arrowcolor=t["text"], bordercolor=t["border"], padding=4)
        s.map("TCombobox", fieldbackground=[("readonly", t["input"])], foreground=[("readonly", t["text"])],
              selectbackground=[("readonly", t["input"])], selectforeground=[("readonly", t["text"])])
        self.root.option_add("*TCombobox*Listbox.background", t["input"])
        self.root.option_add("*TCombobox*Listbox.foreground", t["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", t["accent"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.log.config(bg=t["log_bg"], fg=t["text"], insertbackground=t["text"])
        self.log.tag_config("info", foreground=t["accent"])
        self.log.tag_config("ok", foreground=t["success"])
        self.log.tag_config("warn", foreground="#e8a13c")
        self.log.tag_config("err", foreground=t["danger"])
        self.status.config(bg=t["bg"])
        self.dot.config(bg=t["bg"], fg=t["success"] if self._is_running() else t["muted"])
        self.status_text.config(bg=t["bg"], fg=t["success"] if self._is_running() else t["muted"])

        # 递归更新 Frame/Label 颜色
        def _rec(parent, bg):
            for c in parent.winfo_children():
                if isinstance(c, GreenCheck):
                    c.update_theme(t)
                    continue
                if isinstance(c, RoundedCard):
                    c.update_theme(t)
                    _rec(c, t["card"])
                elif isinstance(c, Frame):
                    c.config(bg=bg)
                    _rec(c, bg)
                elif isinstance(c, Label):
                    c.config(bg=bg, fg=t["muted"] if c.cget("fg") in (THEMES["dark"]["muted"], THEMES["light"]["muted"]) else t["text"])
        _rec(self.content, t["bg"])

    def _toggle_theme(self):
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.theme = THEMES[self.theme_name]
        self.cfg["theme"] = self.theme_name
        save_config(self.cfg)
        self.theme_btn.text = self.theme["name"]
        self.theme_btn.update_theme(self.theme)
        self._apply_theme()

    def _check_paths(self):
        ok = (os.path.isfile(self.cfg.get("llama_server", "")) and os.path.isfile(self.cfg.get("llama_cli", "")) and os.path.isdir(self.cfg.get("model_folder", "")))
        if not ok:
            self._log('未能自动定位 llama.cpp，请点击"定位 llama.cpp"或"选择模型文件夹"', "warn")
        self._update_path_lbl()

    def _update_path_lbl(self):
        self.path_lbl.config(text=f"当前模型目录: {self.cfg.get('model_folder', '')}")

    def _locate_llama(self):
        folder = filedialog.askdirectory(title="选择 llama.cpp 所在文件夹")
        if not folder:
            return
        if not os.path.isfile(os.path.join(folder, "llama-server.exe")) or not os.path.isfile(os.path.join(folder, "llama-cli.exe")):
            messagebox.showerror("错误", f"未在 {folder} 找到 llama-server.exe / llama-cli.exe")
            return
        self.cfg["llama_server"] = os.path.join(folder, "llama-server.exe")
        self.cfg["llama_cli"] = os.path.join(folder, "llama-cli.exe")
        md = os.path.join(folder, "models")
        self.cfg["model_folder"] = pick_model_subdir(md) if os.path.isdir(md) else md
        save_config(self.cfg)
        self._scan_models()
        self._update_path_lbl()
        self._log(f"已定位 llama.cpp: {folder}", "ok")

    def _choose_model_folder(self):
        folder = filedialog.askdirectory(title="选择模型文件夹（包含 .gguf 的目录）")
        if not folder:
            return
        if not any(f.lower().endswith(".gguf") for f in os.listdir(folder)):
            if not messagebox.askyesno("确认", "该目录下没有 .gguf 文件，确定要选择它吗？"):
                return
        self.cfg["model_folder"] = folder
        save_config(self.cfg)
        self._scan_models()
        self._update_path_lbl()
        self._log(f"已设置模型文件夹: {folder}", "ok")

    def _apply_preset(self, name):
        p = PRESETS[name]
        for k, v in p.items():
            self.entries[k].delete(0, "end")
            self.entries[k].insert(0, str(v))
        self._log(f"已应用预设 [{name}]", "ok")

    def _scan_models(self):
        folder = self.cfg.get("model_folder", "")
        if not os.path.isdir(folder):
            self._log(f"模型文件夹不存在: {folder}", "err")
            return
        ggufs = [f for f in os.listdir(folder) if f.lower().endswith(".gguf") and os.path.isfile(os.path.join(folder, f))]
        skipped = sum(1 for f in ggufs if f.lower().startswith("mmproj"))
        self.models = sorted(os.path.join(folder, f) for f in ggufs if not f.lower().startswith("mmproj"))
        if not self.models:
            self._log("未找到可用模型", "warn")
            return
        self.combo["values"] = [os.path.basename(p) for p in self.models]
        if self.combo.current() < 0:
            self.combo.current(0)
        self._log(f"扫描到 {len(self.models)} 个模型", "info")
        if skipped:
            self._log(f"已隐藏 {skipped} 个 mmproj 文件", "info")

    def _read_params(self):
        try:
            return {
                "ngl": int(self.entries["ngl"].get()),
                "ctx": int(self.entries["ctx"].get()),
                "threads": int(self.entries["threads"].get()),
                "port": int(self.entries["port"].get()),
                "host": self.entries["host"].get().strip() or "127.0.0.1",
            }
        except ValueError:
            messagebox.showerror("错误", "NGL / CTX / Threads / Port 必须是数字")
            return None

    def _get_model(self):
        idx = self.combo.current()
        if idx < 0 or idx >= len(self.models):
            messagebox.showerror("错误", "请先选择一个模型")
            return None
        return self.models[idx]

    def _validate(self, key):
        exe = self.cfg[key]
        if not os.path.isfile(exe):
            messagebox.showerror("错误", f'找不到可执行文件:\n{exe}\n\n请点击"定位 llama.cpp"选择目录')
            return False
        return True

    def _is_running(self):
        return self.process is not None and self.process.poll() is None

    def _port_in_use(self, host, port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            return s.connect_ex((host if host != "0.0.0.0" else "127.0.0.1", port)) == 0

    def _collect_config(self):
        self.cfg["auto_open_browser"] = self.var_browser.get()
        self.cfg["minimize_to_tray"] = self.var_tray.get()
        self.cfg["log_to_file"] = self.var_logfile.get()
        p = self._read_params()
        if p:
            self.cfg.update(p)

    def on_save_config(self):
        self._collect_config()
        save_config(self.cfg)
        self._log("配置已保存", "ok")

    def start_server(self):
        if not self._validate("llama_server"):
            return
        if self._is_running():
            messagebox.showwarning("提示", "已有服务在运行，请先停止")
            return
        model = self._get_model()
        p = self._read_params()
        if not model or not p:
            return
        if self._port_in_use(p["host"], p["port"]):
            if not messagebox.askyesno("端口占用", f"端口 {p['port']} 已被占用，仍要尝试启动吗？"):
                return
        cmd = [self.cfg["llama_server"], "-m", model, "--n-gpu-layers", str(p["ngl"]), "-c", str(p["ctx"]),
               "-t", str(p["threads"]), "--host", p["host"], "--port", str(p["port"]), "--jinja"]
        self._run_capture(cmd)
        self._set_status(True, f"API 服务运行中 · http://{p['host']}:{p['port']}/v1")
        self._collect_config()
        save_config(self.cfg)
        if self.var_browser.get():
            threading.Thread(target=self._open_browser_when_ready, args=(p["host"], p["port"]), daemon=True).start()

    def start_cli(self):
        if not self._validate("llama_cli"):
            return
        model = self._get_model()
        p = self._read_params()
        if not model or not p:
            return
        cmd = [self.cfg["llama_cli"], "-m", model, "--n-gpu-layers", str(p["ngl"]), "-c", str(p["ctx"]),
               "-t", str(p["threads"]), "--color", "on"]
        args = subprocess.list2cmdline(cmd)
        self._log(f"执行: {args}", "info")
        try:
            subprocess.Popen(f'start "Llama CLI" cmd /k "{args}"', shell=True)
            self._log("终端对话已启动", "ok")
        except Exception as e:
            self._log(f"启动失败: {e}", "err")

    def _run_capture(self, cmd):
        self._log(f"执行: {' '.join(cmd)}", "info")
        try:
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                            text=True, encoding="utf-8", errors="replace",
                                            creationflags=subprocess.CREATE_NO_WINDOW)
        except Exception as e:
            self._log(f"启动失败: {e}", "err")
            return
        self.stop_btn.set_enabled(True)
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        try:
            for line in self.process.stdout:
                self.root.after(0, self._log, line.rstrip(), "")
        except Exception:
            pass
        self.root.after(0, self._on_process_exit)

    def _on_process_exit(self):
        code = self.process.poll() if self.process else None
        self._set_status(False, "空闲")
        self._log(f"进程已退出 (返回码: {code})", "warn" if code else "info")
        self.process = None
        self.stop_btn.set_enabled(False)

    def stop_process(self):
        if self._is_running():
            self.process.terminate()
            self._log("已发送终止信号…", "warn")
        else:
            self._log("当前没有运行中的服务", "info")

    def _open_browser_when_ready(self, host, port):
        uh = "127.0.0.1" if host == "0.0.0.0" else host
        url = f"http://{uh}:{port}"
        for _ in range(90):
            try:
                with urllib.request.urlopen(f"{url}/health", timeout=2) as r:
                    if r.status == 200:
                        webbrowser.open(url)
                        self.root.after(0, self._log, f"已在浏览器打开 {url}", "ok")
                        return
            except Exception:
                pass
            if not self._is_running():
                return
            time.sleep(1)
        self.root.after(0, self._log, "等待服务就绪超时", "warn")

    def _set_status(self, running, text):
        color = self.theme["success"] if running else self.theme["muted"]
        self.dot.config(fg=color)
        self.status_text.config(text=text, fg=color)

    def _log(self, msg, tag=""):
        if not msg:
            return
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self.log.config(state="normal")
        self.log.insert("end", line + "\n", tag if tag else ())
        self.log.see("end")
        self.log.config(state="disabled")
        if self.var_logfile.get():
            try:
                os.makedirs(LOG_DIR, exist_ok=True)
                with open(os.path.join(LOG_DIR, f"launcher_{datetime.now():%Y%m%d}.log"), "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception:
                pass

    def _make_tray_image(self):
        img = Image.new("RGB", (64, 64), self.theme["accent"])
        d = ImageDraw.Draw(img)
        d.ellipse((6, 6, 58, 58), fill=self.theme["accent_hover"])
        d.text((22, 16), "L", fill="#ffffff")
        return img

    def minimize_to_tray(self):
        if not TRAY_AVAILABLE:
            return
        self.root.withdraw()
        menu = pystray.Menu(
            pystray.MenuItem("显示主界面", lambda: self.root.after(0, self.restore_from_tray), default=True),
            pystray.MenuItem("退出", lambda: self.root.after(0, self.quit_app)))
        self.tray_icon = pystray.Icon("llama_launcher", self._make_tray_image(), "Llama 一键启动器", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()
        self._log("已最小化到系统托盘", "info")

    def restore_from_tray(self):
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None
        self.root.deiconify()
        self.root.lift()

    def on_close(self):
        if self.var_tray.get() and TRAY_AVAILABLE and not self._closing:
            self.minimize_to_tray()
            return
        if self._is_running():
            if not messagebox.askyesno("确认退出", "API 服务仍在运行，退出将终止它。确定退出吗？"):
                return
        self.quit_app()

    def quit_app(self):
        self._closing = True
        self._collect_config()
        save_config(self.cfg)
        if self._is_running():
            self.process.terminate()
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.destroy()


def main():
    root = Tk()
    LlamaLauncher(root)
    root.mainloop()


if __name__ == "__main__":
    main()
