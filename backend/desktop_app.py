"""
明日方舟打轴工具 — 独立桌面程序（tkinter）。
读取游戏时间与帧（tools/timer 内存方案），加载前端导出的排轴 JSON，显示事项与当前步骤。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

# 保证可导入 app.services（从 backend 目录运行）
_BACKEND_ROOT = Path(__file__).resolve().parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.schedule_engine import build_status_payload
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

        self._var_process = tk.StringVar(value=self._provider.process_name)
        self._var_address = tk.StringVar(value=self._provider.time_address_hex or "")
        self._var_cache_user = tk.StringVar(value="default")

        self._build_ui()

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 6}

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
            text="对接 tools/timer 读取游戏时间/帧 · 加载排轴 JSON 显示当前步骤与各区间倒计时",
            font=("Segoe UI", 9),
            fg=MUTED,
            bg=BG,
        )
        sub.pack(anchor="w", padx=12, pady=(0, 8))

        cfg = tk.LabelFrame(self.root, text="进程与地址（与原先 API 配置一致）", fg=FG, bg=BG, padx=8, pady=8)
        cfg.pack(fill="x", padx=12, pady=4)

        row1 = tk.Frame(cfg, bg=BG)
        row1.pack(fill="x")
        tk.Label(row1, text="进程名", fg=FG, bg=BG, width=10, anchor="w").pack(side="left")
        e1 = tk.Entry(row1, textvariable=self._var_process, width=36, bg=ENTRY_BG, fg=FG, insertbackground=FG)
        e1.pack(side="left", **pad)

        row2 = tk.Frame(cfg, bg=BG)
        row2.pack(fill="x")
        tk.Label(row2, text="时间地址", fg=FG, bg=BG, width=10, anchor="w").pack(side="left")
        e2 = tk.Entry(row2, textvariable=self._var_address, width=36, bg=ENTRY_BG, fg=FG, insertbackground=FG)
        e2.pack(side="left", **pad)
        tk.Button(
            row2,
            text="应用配置",
            command=self._on_apply_config,
            bg="#333",
            fg=FG,
        ).pack(side="left", padx=8)

        game_frame = tk.LabelFrame(self.root, text="游戏状态（自动刷新）", fg=FG, bg=BG, padx=8, pady=8)
        game_frame.pack(fill="x", padx=12, pady=4)

        self._lbl_game = tk.Label(game_frame, text="读取中…", fg=FG, bg=BG, justify="left", anchor="w")
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

        cols = ("row", "label", "range", "phase", "until", "note")
        self._tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=18)
        headings = [
            ("row", "轨道", 120),
            ("label", "标签", 100),
            ("range", "时间范围", 220),
            ("phase", "状态", 80),
            ("until", "距开始 / 剩余", 200),
            ("note", "备注", 280),
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

    def _on_apply_config(self) -> None:
        pn = self._var_process.get().strip() or None
        addr = self._var_address.get().strip() or None
        result = self._provider.configure(process_name=pn, time_address=addr)
        if result.get("ok"):
            if result.get("time_address"):
                self._var_address.set(str(result["time_address"]))
            messagebox.showinfo("配置", result.get("message", "成功"))
        else:
            messagebox.showerror("配置失败", result.get("message", "未知错误"))

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
        st = build_status_payload(payload, game)

        lines = [
            f"连接: {'是' if game.get('connected') else '否'}  |  已配置地址: {'是' if game.get('configured') else '否'}",
            f"游戏时间: {game.get('game_time') if game.get('game_time') is not None else '—'}",
            f"逻辑帧: {game.get('frame_count') if game.get('frame_count') is not None else '—'}",
            f"用于对齐的当前帧: {st.get('current_frame') if st.get('current_frame') is not None else '—'} "
            f"（来源: {st.get('current_frame_source', '—')}）  FPS={st.get('fps', 60)}",
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
                    it.get("label", "") or "—",
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
