import json
import os
import socket
import sys
import ctypes
import threading
from pathlib import Path
from tkinter import messagebox, ttk
import tkinter as tk

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pymem

from tools.deploy_tracker.ak_deploy_reader import DeployTrackerReader

EMULATOR_PROCESSES = [
    "MuMuVMMHeadless.exe", "NemuHeadless.exe", "Ld9BoxHeadless.exe",
    "LdBoxHeadless.exe", "dnplayer.exe", "NoxVMMHeadless.exe",
    "HD-Player.exe", "MEmuHeadless.exe",
]

DIRECTION_OPTIONS = ["UP (上)", "RIGHT (右)", "DOWN (下)", "LEFT (左)"]


def _send_events_via_tcp(process_name: str, events: list) -> bool:
    port_str = os.getenv("AK_HOOK_PORT", "").strip()
    if not port_str:
        return False
    try:
        payload = json.dumps(
            {"type": "deployment_events", "process_name": process_name, "events": events},
            ensure_ascii=False,
        )
        with socket.create_connection(("127.0.0.1", int(port_str)), timeout=3) as sock:
            sock.sendall((payload + "\n").encode("utf-8"))
        return True
    except Exception:
        return False


class DeployDisplayApp:
    def __init__(self, root, deploy_reader: DeployTrackerReader, process_name: str):
        self.root = root
        self.reader = deploy_reader
        self._process_name = process_name

        self.root.title("摸轴工具 — 部署时间轴")
        self.root.geometry("720x480")
        self.root.configure(bg="#1E1E1E")

        self._show_spawn_only = tk.BooleanVar(value=True)
        self._prev_event_keys = None

        self._build_ui()
        self._refresh()

    def _build_ui(self):
        toolbar = tk.Frame(self.root, bg="#2A2A2A")
        toolbar.pack(fill="x", padx=0, pady=0)

        self.status_label = tk.Label(
            toolbar, text="已连接", fg="#00FF00", bg="#2A2A2A", font=("Consolas", 10, "bold")
        )
        self.status_label.pack(side="left", padx=10, pady=5)

        self.event_count_label = tk.Label(
            toolbar, text="事件: 0", fg="#AAAAAA", bg="#2A2A2A", font=("Consolas", 10)
        )
        self.event_count_label.pack(side="left", padx=10, pady=5)

        cb = tk.Checkbutton(
            toolbar, text="仅部署", variable=self._show_spawn_only,
            fg="white", bg="#2A2A2A", selectcolor="#2A2A2A",
            activebackground="#2A2A2A", activeforeground="white",
            font=("Consolas", 10),
        )
        cb.pack(side="left", padx=10, pady=5)

        export_btn = tk.Button(
            toolbar, text="导出 JSON", command=self._export_json,
            bg="#444444", fg="white", font=("Consolas", 9),
        )
        export_btn.pack(side="right", padx=10, pady=5)

        tcp_btn = tk.Button(
            toolbar, text="推送至打轴工具", command=self._tcp_push,
            bg="#444444", fg="white", font=("Consolas", 9),
        )
        tcp_btn.pack(side="right", padx=5, pady=5)

        tree_frame = tk.Frame(self.root, bg="#1E1E1E")
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)

        columns = ("timestamp", "charId", "opName", "position", "direction", "uniqueId", "extraInfo")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("timestamp", text="时间 (s)")
        self.tree.heading("charId", text="干员 ID")
        self.tree.heading("opName", text="操作")
        self.tree.heading("position", text="位置")
        self.tree.heading("direction", text="方向")
        self.tree.heading("uniqueId", text="UID")
        self.tree.heading("extraInfo", text="额外信息")

        self.tree.column("timestamp", width=90, anchor="center")
        self.tree.column("charId", width=180, anchor="w")
        self.tree.column("opName", width=70, anchor="center")
        self.tree.column("position", width=70, anchor="center")
        self.tree.column("direction", width=55, anchor="center")
        self.tree.column("uniqueId", width=50, anchor="center")
        self.tree.column("extraInfo", width=150, anchor="w")

        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#1E1E1E", foreground="white", fieldbackground="#1E1E1E", rowheight=24)
        style.configure("Treeview.Heading", background="#333333", foreground="white")
        style.map("Treeview", background=[("selected", "#0066CC")])

        self.tree.tag_configure("spawn", foreground="#00FF00")
        self.tree.tag_configure("withdraw", foreground="#FF6666")
        self.tree.tag_configure("skill", foreground="#66CCFF")
        self.tree.tag_configure("cheat", foreground="#FFAA00")

    def _refresh(self):
        try:
            spawn_only = self._show_spawn_only.get()

            if self.reader._bc_addr and not self.reader.is_battle_active():
                self.status_label.config(text="等待作战开始...", fg="#FFFF00")
                self.tree.delete(*self.tree.get_children())
                self.event_count_label.config(text="事件: 0")
                self._prev_event_keys = None
            else:
                events = self.reader.get_spawn_events() if spawn_only else self.reader.get_events()
                new_keys = [(e["uniqueId"], e["timestamp"], e["op"]) for e in events]
                if new_keys != self._prev_event_keys:
                    self._prev_event_keys = new_keys
                    self._populate_table(events)
                    self.status_label.config(text="已连接", fg="#00FF00")
                    self.event_count_label.config(text=f"事件: {len(events)}")
        except pymem.exception.MemoryReadError:
            self.status_label.config(text="连接断开", fg="#FF0000")
        except Exception:
            pass
        self.root.after(200, self._refresh)

    def _populate_table(self, events):
        self.tree.delete(*self.tree.get_children())
        for e in events:
            position = f"({e['gridRow']}, {e['gridCol']})"
            tag = e["opName"].lower() if e["opName"] in ("SPAWN", "WITHDRAW", "SKILL", "CHEAT") else ""
            self.tree.insert(
                "", "end",
                values=(
                    f"{e['timestamp']:.3f}", e["charId"], e["opName"],
                    position, e["directionName"], e["uniqueId"], e["extraInfo"],
                ),
                tags=(tag,) if tag else (),
            )

    def _export_json(self):
        events = self.reader.get_spawn_events() if self._show_spawn_only.get() else self.reader.get_events()
        if not events:
            messagebox.showinfo("导出", "没有可导出的事件。")
            return
        try:
            path = os.path.join(os.path.expanduser("~"), "Desktop", "deploy_timeline.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(events, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("导出", f"已导出到:\n{path}")
        except OSError as exc:
            messagebox.showerror("导出失败", str(exc))

    def _tcp_push(self):
        events = self.reader.get_spawn_events() if self._show_spawn_only.get() else self.reader.get_events()
        if not events:
            messagebox.showinfo("推送", "没有可推送的事件。")
            return
        ok = _send_events_via_tcp(self._process_name, events)
        if ok:
            messagebox.showinfo("推送", "已推送到打轴工具。")
        else:
            messagebox.showwarning("推送", "推送失败，未设置 AK_HOOK_PORT 或后端未运行。")


class DeployWizardApp:
    """主流程：等待进程 → 引导部署 → 多次扫描 → 显示时间轴。"""

    def __init__(self, root, process_name, pm):
        self.root = root
        self._process_name = process_name
        self._pm = pm
        self._reader = DeployTrackerReader(self._pm)

        self.root.geometry("520x400")
        self.root.title("摸轴工具 — 部署引导")
        self.root.configure(bg="#1E1E1E")
        self.root.attributes("-topmost", False)

        self._build_ui()

    def _build_ui(self):
        tk.Label(
            self.root, text=f"目标进程: {self._process_name}",
            fg="#AAAAAA", bg="#1E1E1E", font=("Consolas", 9),
        ).pack(pady=(10, 5))

        tk.Label(
            self.root, text="增量扫描引导",
            fg="#00FF00", bg="#1E1E1E", font=("Consolas", 14, "bold"),
        ).pack(pady=10)

        guide = tk.Frame(self.root, bg="#252526", padx=15, pady=12)
        guide.pack(fill="x", padx=20, pady=5)

        steps = [
            "1. 进入作战关卡，部署第1个干员(记住朝向)",
            "2. 选择朝向后点击「第一步扫描」",
            "3. 再部署第2个干员(同样朝向)，点击「再次扫描」",
            "4. 若还不行，部署第3个干员再扫，直到锁定",
        ]
        for s in steps:
            tk.Label(
                guide, text=s, fg="#AAAAAA", bg="#252526",
                font=("Consolas", 10),
            ).pack(anchor="w", pady=1)

        # 朝向选择
        row = tk.Frame(self.root, bg="#1E1E1E")
        row.pack(fill="x", padx=40, pady=(15, 15))
        tk.Label(row, text="部署朝向:", fg="white", bg="#1E1E1E", font=("Consolas", 11)).pack(side="left", padx=(0, 8))
        self.dir_var = tk.StringVar(value=DIRECTION_OPTIONS[1])
        dir_dropdown = ttk.Combobox(
            row, textvariable=self.dir_var,
            values=DIRECTION_OPTIONS, state="readonly", width=15,
        )
        dir_dropdown.pack(side="left")

        # 按钮
        btn_row = tk.Frame(self.root, bg="#1E1E1E")
        btn_row.pack(pady=10)
        self.scan_btn = tk.Button(
            btn_row, text="第一步扫描", command=self._first_scan,
            bg="#3d7eff", fg="white", font=("Consolas", 12, "bold"),
            width=16, height=2,
        )
        self.scan_btn.pack(side="left", padx=5)

        self.scan_again_btn = tk.Button(
            btn_row, text="再次扫描", command=self._scan_again,
            bg="#555555", fg="#AAAAAA", font=("Consolas", 12, "bold"),
            width=16, height=2, state="disabled",
        )
        self.scan_again_btn.pack(side="left", padx=5)

        # 状态
        self.status_var = tk.StringVar(value="就绪 — 部署第1个干员, 选择朝向, 点「第一步扫描」")
        self.status_label = tk.Label(
            self.root, textvariable=self.status_var,
            fg="#FFFF00", bg="#1E1E1E", font=("Consolas", 10), wraplength=480,
        )
        self.status_label.pack(pady=5, fill="x", padx=20)

        self._step_count = tk.Label(
            self.root, text="步数: 0", fg="#888888", bg="#1E1E1E", font=("Consolas", 9),
        )
        self._step_count.pack(pady=5)

    def _first_scan(self):
        dir_idx = DIRECTION_OPTIONS.index(self.dir_var.get())

        self.scan_btn.config(state="disabled")
        self.dir_var.set(self.dir_var.get())  # lock dropdown

        def task():
            n = self._reader.start_scan(direction=dir_idx)
            self.root.after(0, lambda: self._on_first_scan_done(n))

        threading.Thread(target=task, daemon=True).start()

    def _on_first_scan_done(self, n):
        self._step_count.config(text=f"步数: 1")
        self.scan_again_btn.config(
            state="normal", bg="#3d7eff", fg="white",
            text="再次扫描 (部署第2个)",
        )
        self.status_var.set(
            f"第一步完成: {n} 个匹配\n"
            "→ 请部署第 2 个干员 (相同朝向), 然后点「再次扫描」"
        )

    def _scan_again(self):
        self.scan_again_btn.config(state="disabled", text="扫描中...")

        def task():
            result = self._reader.scan_again()
            self.root.after(0, lambda: self._on_scan_again_done(result))

        threading.Thread(target=task, daemon=True).start()

    def _on_scan_again_done(self, result):
        step = self._reader._round
        self._step_count.config(text=f"步数: {step}")

        if result == "found":
            self._launch_display()
        elif result == "more":
            self.scan_again_btn.config(
                state="normal", bg="#3d7eff", fg="white",
                text=f"再次扫描 (部署第{step + 1}个)",
            )
            self.status_var.set(
                f"候选仍较多, 请部署第 {step + 1} 个干员 (同朝向), 再点「再次扫描」"
            )
        else:  # failed
            self.scan_btn.config(state="normal")
            self.scan_again_btn.config(
                state="normal", bg="#555555", fg="#AAAAAA",
                text=f"再次扫描 (部署第{step + 1}个)",
            )
            self.status_var.set(
                "未找到相邻配对。请确认:\n"
                "→ 两次部署朝向相同\n"
                "→ 均为 SPAWN (部署) 操作\n"
                "可点「第一步扫描」重新开始"
            )
            messagebox.showwarning("失败", "未找到有效的相邻配对。\n请检查部署朝向是否一致。")

    def _launch_display(self):
        for w in self.root.winfo_children():
            w.destroy()
        DeployDisplayApp(self.root, self._reader, self._process_name)


class ProcessWaiter:
    """哨兵模式：等待模拟器进程，找到后直接进入部署引导。"""

    def __init__(self, root):
        self.root = root
        self.root.title("摸轴工具")
        self.root.geometry("350x120")
        self.root.configure(bg="#1E1E1E")
        self.root.attributes("-topmost", True)

        self.label = tk.Label(
            self.root, text="等待模拟器启动...",
            fg="#00FFFF", bg="#1E1E1E", font=("Consolas", 14, "bold"),
        )
        self.label.pack(expand=True, fill="both")

        self._dot_count = 0
        self._check()

    def _check(self):
        self._dot_count = (self._dot_count + 1) % 4
        self.label.config(text=f"正在监听模拟器进程{'.' * self._dot_count}")

        found = None
        pm = None
        for proc in EMULATOR_PROCESSES:
            try:
                pm = pymem.Pymem(proc)
                found = proc
                break
            except Exception:
                pass

        if found:
            self._launch_wizard(found, pm)
        else:
            self.root.after(1000, self._check)

    def _launch_wizard(self, process_name, pm):
        for w in self.root.winfo_children():
            w.destroy()
        self.root.attributes("-topmost", False)
        DeployWizardApp(self.root, process_name, pm)


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def main():
    root = tk.Tk()
    ProcessWaiter(root)
    root.mainloop()


if __name__ == "__main__":
    if is_admin():
        main()
    else:
        script = os.path.abspath(sys.argv[0])
        params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
        sys.exit()
