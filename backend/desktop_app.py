"""
明日方舟打轴工具 — 独立桌面程序（tkinter）。
读取游戏时间与帧（tools/timer 内存方案），加载前端导出的排轴 JSON，显示事项与当前步骤。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

# 保证可导入 app.services（从 backend 目录运行）
_BACKEND_ROOT = Path(__file__).resolve().parent
_REPO_ROOT = _BACKEND_ROOT.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.schedule_engine import build_status_payload, game_frame_for_anchor
from app.services.schedule_store import ScheduleStore
from app.services.timer_provider import TimerDataProvider
from app.services.timeline_cache import TimelineCacheService

BG = "#1e1e1e"
FG = "#e8e8e8"
MUTED = "#9a9a9a"
ACCENT = "#3d7eff"
ENTRY_BG = "#2d2d2d"


def _validate_payload(data: dict) -> tuple[bool, str]:
    if not isinstance(data, dict):
        return False, "不是有效的 JSON 对象。"
    if "rows" not in data or "meta" not in data:
        return False, "缺少 rows 或 meta（需与前端导出格式一致）。"
    if not isinstance(data.get("rows"), list):
        return False, "rows 必须是数组。"
    if not isinstance(data.get("meta"), dict):
        return False, "meta 必须是对象。"
    return True, ""


class CoachDesktopApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("明日方舟打轴工具")
        self.root.geometry("1180x760")
        self.root.minsize(900, 560)
        self.root.configure(bg=BG)

        self._provider = TimerDataProvider()
        self._store = ScheduleStore()
        self._cache = TimelineCacheService()

        self._var_cache_user = tk.StringVar(value="default")
        self._var_exec_mode = tk.StringVar(value="from_start")
        self._var_start_frame = tk.StringVar(value="0")
        self._anchor_game_frame: int | None = None

        self._build_ui()
        self._var_exec_mode.trace_add("write", self._on_exec_mode_trace)

    def _build_ui(self) -> None:
        title = tk.Label(
            self.root,
            text="明日方舟打轴工具 · 桌面版",
            font=("Segoe UI", 14, "bold"),
            fg=FG,
            bg=BG,
        )
        title.pack(anchor="w", padx=12, pady=(12, 4))

        sub = tk.Label(
            self.root,
            text="用「寻址工具」逐步扫描内存；完成后点「刷新游戏状态」从同一配置读取时间与逻辑帧（非实时轮询）",
            font=("Segoe UI", 9),
            fg=MUTED,
            bg=BG,
        )
        sub.pack(anchor="w", padx=12, pady=(0, 8))

        cfg = tk.LabelFrame(self.root, text="内存寻址（tools/timer）", fg=FG, bg=BG, padx=8, pady=8)
        cfg.pack(fill="x", padx=12, pady=4)

        brow = tk.Frame(cfg, bg=BG)
        brow.pack(fill="x")
        tk.Button(
            brow,
            text="打开寻址工具",
            command=self._on_open_timer_tool,
            bg="#2a4a8a",
            fg="white",
        ).pack(side="left", padx=4)
        tk.Button(
            brow,
            text="刷新游戏状态",
            command=self._on_refresh_game,
            bg="#1a6b3a",
            fg="white",
        ).pack(side="left", padx=4)
        tk.Label(
            brow,
            text="（寻址工具需管理员；完成向导后会写入 backend/data/timer_hook.json）",
            fg=MUTED,
            bg=BG,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=12)

        game_frame = tk.LabelFrame(self.root, text="游戏状态（上次刷新）", fg=FG, bg=BG, padx=8, pady=8)
        game_frame.pack(fill="x", padx=12, pady=4)

        self._lbl_game = tk.Label(game_frame, text="请点击「刷新游戏状态」…", fg=FG, bg=BG, justify="left", anchor="w")
        self._lbl_game.pack(fill="x")

        json_frame = tk.LabelFrame(self.root, text="排轴数据", fg=FG, bg=BG, padx=8, pady=8)
        json_frame.pack(fill="x", padx=12, pady=4)

        jrow = tk.Frame(json_frame, bg=BG)
        jrow.pack(fill="x")
        tk.Button(jrow, text="从文件加载 JSON…", command=self._on_load_json, bg="#2a4a8a", fg="white").pack(
            side="left", padx=4
        )
        tk.Button(jrow, text="清空排轴", command=self._on_clear_schedule, bg="#553333", fg=FG).pack(side="left", padx=4)

        tk.Label(jrow, text="用户ID（读后端缓存文件）", fg=MUTED, bg=BG).pack(side="left", padx=(16, 4))
        tk.Entry(jrow, textvariable=self._var_cache_user, width=14, bg=ENTRY_BG, fg=FG, insertbackground=FG).pack(
            side="left"
        )
        tk.Button(jrow, text="从缓存载入", command=self._on_load_cache, bg="#333", fg=FG).pack(side="left", padx=8)

        tbase = tk.Frame(json_frame, bg=BG)
        tbase.pack(fill="x", pady=(8, 0))
        tk.Label(tbase, text="时间基准", fg=FG, bg=BG).pack(side="left", padx=(0, 8))
        tk.Radiobutton(
            tbase,
            text="从头执行（轴上帧数 = 游戏帧）",
            variable=self._var_exec_mode,
            value="from_start",
            fg=FG,
            bg=BG,
            selectcolor=ENTRY_BG,
            activebackground=BG,
            activeforeground=FG,
        ).pack(side="left", padx=4)
        tk.Radiobutton(
            tbase,
            text="从当前帧起算",
            variable=self._var_exec_mode,
            value="from_current",
            fg=FG,
            bg=BG,
            selectcolor=ENTRY_BG,
            activebackground=BG,
            activeforeground=FG,
        ).pack(side="left", padx=4)
        tk.Label(tbase, text="起始轴帧", fg=FG, bg=BG).pack(side="left", padx=(12, 4))
        tk.Entry(
            tbase,
            textvariable=self._var_start_frame,
            width=8,
            bg=ENTRY_BG,
            fg=FG,
            insertbackground=FG,
        ).pack(side="left")
        tk.Button(
            tbase,
            text="按当前帧应用",
            command=self._apply_anchor_from_current_frame,
            bg="#333",
            fg=FG,
        ).pack(side="left", padx=8)

        step_frame = tk.LabelFrame(self.root, text="当前进度", fg=FG, bg=BG, padx=8, pady=8)
        step_frame.pack(fill="x", padx=12, pady=4)
        self._lbl_step = tk.Label(
            step_frame,
            text="—",
            fg="#7ec8ff",
            bg="#252526",
            font=("Segoe UI", 11, "bold"),
            justify="left",
            anchor="w",
            wraplength=1080,
        )
        self._lbl_step.pack(fill="x", ipadx=8, ipady=8)

        table_frame = tk.LabelFrame(self.root, text="时间轴事项", fg=FG, bg=BG, padx=4, pady=4)
        table_frame.pack(fill="both", expand=True, padx=12, pady=(4, 12))

        cols = ("row", "range", "phase", "until", "note")
        self._tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=18)
        headings = [
            ("row", "轨道", 140),
            ("range", "时间范围", 260),
            ("phase", "状态", 80),
            ("until", "距开始 / 剩余", 220),
            ("note", "备注", 360),
        ]
        for cid, text, w in headings:
            self._tree.heading(cid, text=text)
            self._tree.column(cid, width=w, stretch=True)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        style = ttk.Style()
        try:
            style.theme_use("clam")
            style.configure("Treeview", background=ENTRY_BG, fieldbackground=ENTRY_BG, foreground=FG, rowheight=24)
            style.configure("Treeview.Heading", background="#333", foreground=FG)
        except tk.TclError:
            pass

        self.root.after(400, self._tick)

    def _on_open_timer_tool(self) -> None:
        script = _REPO_ROOT / "tools" / "timer" / "ak_timer_ui.py"
        if not script.is_file():
            messagebox.showerror("寻址工具", f"未找到脚本：\n{script}")
            return
        try:
            subprocess.Popen(
                [sys.executable, str(script)],
                cwd=str(script.parent),
                close_fds=sys.platform != "win32",
            )
        except OSError as e:
            messagebox.showerror("寻址工具", f"无法启动：{e}")

    def _on_exec_mode_trace(self, *_args: object) -> None:
        if self._var_exec_mode.get() == "from_current":
            if not self._apply_anchor_from_current_frame(show_message=True):
                self._var_exec_mode.set("from_start")
                return
        else:
            self._anchor_game_frame = None
        self._refresh_view()

    def _apply_anchor_from_current_frame(self, show_message: bool = False) -> bool:
        payload = self._store.get()
        if not payload:
            messagebox.showwarning("时间基准", "请先加载排轴 JSON。")
            return False
        try:
            start_frame = int((self._var_start_frame.get() or "0").strip())
        except ValueError:
            messagebox.showwarning("时间基准", "起始轴帧必须是整数。")
            return False

        game = self._provider.get_game_data()
        cf = game_frame_for_anchor(payload, game)
        if cf is None:
            messagebox.showwarning(
                "时间基准",
                "无法解析当前游戏帧，请先点击「刷新游戏状态」。",
            )
            return False

        # 当前游戏帧对应到用户指定轴帧：schedule_frame = game_frame - anchor
        self._anchor_game_frame = int(cf) - start_frame
        if show_message:
            messagebox.showinfo(
                "时间基准",
                f"已应用：当前游戏帧 F{int(cf)} 对齐到轴上 F{start_frame}。",
            )
        self._refresh_view()
        return True

    def _on_refresh_game(self) -> None:
        res = self._provider.refresh_from_hook_file()
        self._refresh_view()
        if not res.get("ok"):
            messagebox.showwarning("游戏状态", res.get("message", "刷新失败"))

    def _on_load_json(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title="选择排轴 JSON",
            filetypes=[("JSON", "*.json"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            raw = Path(path).read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as e:
            messagebox.showerror("加载失败", str(e))
            return
        ok, msg = _validate_payload(data)
        if not ok:
            messagebox.showerror("格式错误", msg)
            return
        self._store.load(data)
        messagebox.showinfo("排轴", "已加载，列表将自动刷新。")

    def _on_clear_schedule(self) -> None:
        self._store.clear()
        messagebox.showinfo("排轴", "已清空。")

    def _on_load_cache(self) -> None:
        uid = self._var_cache_user.get().strip() or "default"
        res = self._cache.load(uid)
        if not res.get("ok"):
            messagebox.showerror("缓存", res.get("message", "读取失败"))
            return
        if not res.get("has_cache") or not res.get("data"):
            messagebox.showwarning("缓存", f"用户「{uid}」无缓存文件。")
            return
        data = res["data"]
        ok, msg = _validate_payload(data)
        if not ok:
            messagebox.showerror("格式错误", msg)
            return
        self._store.load(data)
        messagebox.showinfo("排轴", f"已从缓存载入用户 {res.get('user_id', uid)}。")

    def _refresh_view(self) -> None:
        game = self._provider.get_game_data()
        payload = self._store.get()
        anchor = self._anchor_game_frame if self._var_exec_mode.get() == "from_current" else None
        st = build_status_payload(payload, game, relative_anchor_game_frame=anchor)

        lr = game.get("last_refresh")
        start_frame_text = self._var_start_frame.get().strip() or "0"
        mode_line = (
            f"时间基准: 从当前帧起算（当前帧映射到轴上 F{start_frame_text}，锚点={self._anchor_game_frame}）"
            if anchor is not None
            else "时间基准: 从头执行"
        )
        lines = [
            mode_line,
            f"连接: {'是' if game.get('connected') else '否'}  |  已配置地址: {'是' if game.get('configured') else '否'}",
            f"游戏时间 (s): {game.get('game_time') if game.get('game_time') is not None else '—'}",
            f"逻辑帧: {game.get('frame_count') if game.get('frame_count') is not None else '—'}",
            f"排轴对照帧: {st.get('current_frame') if st.get('current_frame') is not None else '—'}  "
            f"FPS={st.get('fps', 60)}",
            f"最近一次刷新: {lr if lr else '—'}",
            f"说明: {game.get('message', '')}",
        ]
        self._lbl_game.configure(text="\n".join(lines))

        step = st.get("current_step") or {}
        self._lbl_step.configure(text=step.get("summary") or st.get("message") or "—")

        for item in self._tree.get_children():
            self._tree.delete(item)

        items = st.get("items") or []
        for it in items:
            phase = it.get("phase", "")
            phase_zh = {"active": "进行中", "upcoming": "未开始", "past": "已结束", "unknown": "未知"}.get(
                phase, phase
            )
            self._tree.insert(
                "",
                "end",
                values=(
                    it.get("row_name", ""),
                    it.get("range_text", "") or "—",
                    phase_zh,
                    f"{it.get('until_start_text', '—')} / {it.get('until_end_text', '—')}",
                    (it.get("note") or "")[:120],
                ),
                tags=(phase,),
            )
        self._tree.tag_configure("active", background="#1a3d5c")
        self._tree.tag_configure("past", foreground="#777777")

    def _tick(self) -> None:
        try:
            self._refresh_view()
        except Exception:
            pass
        self.root.after(400, self._tick)

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    CoachDesktopApp().run()


if __name__ == "__main__":
    main()
