# -*- coding: utf-8 -*-
"""明日方舟 实时 RNG 追踪器 (tkinter 图形界面 —— 纯展示层)

功能逻辑全部在 rng_service.RngService (连接/定位/轮询/缓存), 本文件只做
界面渲染: 随机数序列 (历史 + 未来预测条图), 当前随机数 (下一发),
以及游标指向的下一个随机数位置 (inext/inextp)。

用法:
  python ak_rng_ui.py                          # adb 后端 (默认, 免管理员), 只看关键随机
  python ak_rng_ui.py --package com.hypergryph.arknights.bilibili
  python ak_rng_ui.py --no-cache --heuristic   # 同控制台版参数
"""

import argparse
import os
import sys
import threading
import time
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rng_service import RngService

PREDICT_COUNT = 20          # 未来序列条图发数
HISTORY_MAX = 300           # 历史列表最大行数
REFRESH_MS = 150            # 界面刷新间隔

BG = "#1e1e1e"
FG = "#d4d4d4"
DIM = "#808080"
BAR_OK = "#61afef"
BAR_NEXT = "#98c379"
YELLOW = "#e5c07b"


class RngWindow:
    def __init__(self, root, svc):
        self.root = root
        self.svc = svc
        self._last_seq = 0
        self._hist_engine = None   # 历史列表当前对应的引擎 id (切换即清空)
        root.title("明日方舟 实时 RNG 追踪")
        root.configure(bg=BG)
        root.minsize(620, 640)

        # ---- 顶部状态 ----
        top = tk.Frame(root, bg=BG)
        top.pack(fill="x", padx=10, pady=(8, 0))
        self.lbl_proc = tk.Label(top, text="连接中 ...", bg=BG, fg=FG,
                                 font=("微软雅黑", 9), anchor="w", justify="left")
        self.lbl_proc.pack(fill="x")

        row = tk.Frame(top, bg=BG)
        row.pack(fill="x", pady=(4, 0))
        tk.Label(row, text="关键随机 (imp) · 干员判定流", bg=BG, fg=DIM,
                 font=("微软雅黑", 9)).pack(side="left")
        tk.Button(row, text="重新扫描", command=self._on_rescan,
                  bg="#3c3c3c", fg=FG, activebackground="#4c4c4c",
                  activeforeground=FG, relief="flat",
                  font=("微软雅黑", 9)).pack(side="left", padx=(12, 0))
        self.lbl_stats = tk.Label(row, text="", bg=BG, fg=DIM, font=("微软雅黑", 9))
        self.lbl_stats.pack(side="right")

        # ---- 当前随机数 (下一发) ----
        mid = tk.Frame(root, bg=BG)
        mid.pack(fill="x", padx=10, pady=(10, 0))
        tk.Label(mid, text="当前随机数 (下一发)", bg=BG, fg=DIM,
                 font=("微软雅黑", 9)).pack(anchor="w")
        self.lbl_next = tk.Label(mid, text="--", bg=BG, fg=BAR_NEXT,
                                 font=("Consolas", 30, "bold"), anchor="w")
        self.lbl_next.pack(fill="x")
        self.lbl_cursor = tk.Label(mid, text="", bg=BG, fg=FG,
                                   font=("微软雅黑", 9), anchor="w", justify="left")
        self.lbl_cursor.pack(fill="x")

        # ---- 未来序列条图 ----
        tk.Label(root, text="未来随机数序列 (左=下一发)",
                 bg=BG, fg=DIM, font=("微软雅黑", 9)).pack(anchor="w", padx=10, pady=(10, 0))
        self.canvas = tk.Canvas(root, bg="#252526", height=170,
                                highlightthickness=1, highlightbackground="#3c3c3c")
        self.canvas.pack(fill="x", padx=10, pady=4)

        # ---- 最近消耗 ----
        tk.Label(root, text="最近消耗序列", bg=BG, fg=DIM,
                 font=("微软雅黑", 9)).pack(anchor="w", padx=10, pady=(6, 0))
        self.listbox = tk.Listbox(root, bg="#252526", fg=FG, font=("Consolas", 10),
                                  activestyle="none", highlightthickness=1,
                                  highlightbackground="#3c3c3c")
        self.listbox.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------- 事件 ----------------

    def _on_rescan(self):
        # 手动重定位 (新一局/换模拟器后); 实际扫描在轮询线程执行, 不卡界面
        self._last_seq = 0
        self._hist_engine = None
        self.listbox.delete(0, "end")
        self.svc.request_rescan(0)

    def _on_close(self):
        self.svc.stop()
        self.root.destroy()

    # ---------------- 渲染 ----------------

    def refresh(self):
        try:
            snap = self.svc.snapshot(history_len=HISTORY_MAX,
                                     predict_len=PREDICT_COUNT)
            self._render(snap)
        except Exception:
            pass
        self.root.after(REFRESH_MS, self.refresh)

    def _render(self, snap):
        self.lbl_proc.config(text="进程: %s    定位: %s    %s" % (
            snap["process"] or "未连接", snap["via"] or "--", snap["status"]))
        sel = snap["selected"]

        # 统计
        if sel is not None:
            self.lbl_stats.config(text="累计消耗 %d    %.1f 发/秒    状态 %s" % (
                sel["total"], sel["rate"], sel["status"]))
        else:
            self.lbl_stats.config(text="")

        # 当前随机数 + 游标位置
        preds = sel["predictions"] if sel else []
        if preds:
            nxt = preds[0]
            self.lbl_next.config(text="%.6f" % nxt["frac"], fg=BAR_NEXT)
            self.lbl_cursor.config(text="raw = %d" % nxt["raw"])
        else:
            self.lbl_next.config(text="--", fg=DIM)
            self.lbl_cursor.config(text="等待引擎基线 ..." if sel else "未定位到引擎")
        if sel:
            cur, cur2 = sel["cursor"], sel["cursor2"]
            if sel["kind"] == "knuth" and cur >= 0:
                nxt_pos = cur + 1 if cur < 55 else 1
                self.lbl_cursor.config(text=self.lbl_cursor.cget("text") +
                                       "    游标 inext=%d → 下一发取 SeedArray[%d] (inextp=%d)"
                                       % (cur, nxt_pos, cur2))
            elif cur >= 0:
                self.lbl_cursor.config(text=self.lbl_cursor.cget("text") +
                                       "    游标 mti=%d / 624" % cur)

        self._draw_bars(preds)
        self._fill_history(sel["history"] if sel else [],
                           sel["id"] if sel else None)

    def _draw_bars(self, preds):
        c = self.canvas
        c.delete("all")
        w = max(c.winfo_width(), 100)     # 首帧未映射时 winfo 为 1
        h = max(c.winfo_height(), 100)
        if not preds:
            c.create_text(w / 2, h / 2, text="等待随机数序列 ...",
                          fill=DIM, font=("微软雅黑", 10))
            return
        n = len(preds)
        bw = w / n
        for i, p in enumerate(preds):
            frac = p["frac"]
            bh = frac * (h - 24)
            x0, x1 = i * bw + 2, (i + 1) * bw - 2
            color = BAR_NEXT if i == 0 else BAR_OK
            c.create_rectangle(x0, h - 8 - bh, x1, h - 8, fill=color, width=0)
            if i == 0:
                c.create_rectangle(x0, h - 8 - bh, x1, h - 8,
                                   outline=YELLOW, width=2)
            if n <= 20:
                c.create_text((x0 + x1) / 2, h - 14 - bh, text="%.2f" % frac,
                              fill=FG, font=("Consolas", 7))
            c.create_text((x0 + x1) / 2, h - 3, text="+%d" % p["n"],
                          fill=DIM, font=("Consolas", 7), anchor="s")

    def _fill_history(self, hist, engine_id):
        if engine_id != self._hist_engine:
            # 切换引擎: 序号命名空间不同, 清空重填
            self._hist_engine = engine_id
            self._last_seq = 0
            self.listbox.delete(0, "end")
        if hist and hist[-1]["seq"] < self._last_seq:
            # 序号回退: 已重扫并新建 tracker (新一局), 清空重填
            self._last_seq = 0
            self.listbox.delete(0, "end")
        new = [p for p in hist if p["seq"] > self._last_seq]
        for p in new:
            self._last_seq = p["seq"]
            self.listbox.insert("end", "#%-6d %.6f  (%d)  %s" % (
                p["seq"], p["frac"], p["raw"],
                time.strftime("%H:%M:%S", time.localtime(p["ts"]))))
        while self.listbox.size() > HISTORY_MAX:
            self.listbox.delete(0)
        if new:
            self.listbox.see("end")


def main():
    parser = argparse.ArgumentParser(description="明日方舟 实时 RNG 追踪 (图形界面)")
    parser.add_argument("--backend", choices=["adb", "pymem"], default="adb")
    parser.add_argument("--package", default="com.hypergryph.arknights")
    parser.add_argument("--adb", help="adb.exe 路径 (默认自动探测)")
    parser.add_argument("--process", help="pymem 后端: 指定模拟器进程名")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--heuristic", action="store_true")
    args = parser.parse_args()

    svc = RngService(
        backend=args.backend, package=args.package, adb_path=args.adb,
        process_names=[args.process] if args.process else None,
        prefer_role="imp",                       # 只看关键随机 (干员判定流)
        use_cache=not args.no_cache,
        allow_heuristic=args.heuristic)

    root = tk.Tk()
    win = RngWindow(root, svc)

    def worker():
        # 连接/定位放工作线程, 避免扫描期间卡界面
        while not svc.attach():
            svc.status_msg = "连接失败, 10 秒后重试 ..."
            time.sleep(10)
        svc.locate()
        svc.start()

    threading.Thread(target=worker, daemon=True).start()
    root.after(REFRESH_MS, win.refresh)
    root.mainloop()


if __name__ == "__main__":
    main()
