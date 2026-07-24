import json
import os
import socket
import sys
import threading
from pathlib import Path
from tkinter import messagebox, ttk
import tkinter as tk

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.deploy_tracker.ak_deploy_reader import DeployTrackerReader
from tools.enemy_health.memcore import MemCore


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

        web_btn = tk.Button(
            toolbar, text="网页可视化", command=self._open_web,
            bg="#444444", fg="white", font=("Consolas", 9),
        )
        web_btn.pack(side="right", padx=5, pady=5)

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

    def _open_web(self):
        """启动 Web 可视化服务并在浏览器打开 (独立进程, 自带定位)。"""
        import subprocess
        import webbrowser
        port = os.getenv("AK_DEPLOY_PORT", "8793")
        try:
            subprocess.Popen(
                [sys.executable, "-m", "tools.deploy_tracker.web_server", "--port", port],
                cwd=str(_PROJECT_ROOT),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        except OSError as exc:
            messagebox.showerror("启动失败", str(exc))
            return
        webbrowser.open(f"http://127.0.0.1:{port}/")


class DeployWizardApp:
    """主流程：等待进程 → 全自动定位 → 显示时间轴 (可打开网页可视化)。"""

    def __init__(self, root, process_name, mc):
        self.root = root
        self._process_name = process_name
        self._mc = mc
        self._reader = DeployTrackerReader(self._mc)
        self._reader.set_status_callback(
            lambda m: self.root.after(0, lambda: self.status_var.set(m)))

        self.root.geometry("520x320")
        self.root.title("摸轴工具 — 自动定位")
        self.root.configure(bg="#1E1E1E")
        self.root.attributes("-topmost", False)

        self._build_ui()
        self.root.after(300, self._start_locate)

    def _build_ui(self):
        tk.Label(
            self.root, text=f"目标进程: {self._process_name}",
            fg="#AAAAAA", bg="#1E1E1E", font=("Consolas", 9),
        ).pack(pady=(10, 5))

        tk.Label(
            self.root, text="全自动定位",
            fg="#00FF00", bg="#1E1E1E", font=("Consolas", 14, "bold"),
        ).pack(pady=10)

        guide = tk.Frame(self.root, bg="#252526", padx=15, pady=12)
        guide.pack(fill="x", padx=20, pady=5)
        for s in [
            "1. 进入作战关卡（尚未部署干员也可定位）",
            "2. 定位自动进行 (扫描约需数十秒)",
            "3. 代理指挥作战可直接读取完整代理序列",
        ]:
            tk.Label(guide, text=s, fg="#AAAAAA", bg="#252526",
                     font=("Consolas", 10)).pack(anchor="w", pady=1)

        btn_row = tk.Frame(self.root, bg="#1E1E1E")
        btn_row.pack(pady=12)
        self.rescan_btn = tk.Button(
            btn_row, text="重新定位", command=self._start_locate,
            bg="#3d7eff", fg="white", font=("Consolas", 11, "bold"),
            width=12, height=1, state="disabled",
        )
        self.rescan_btn.pack(side="left", padx=5)

        self.status_var = tk.StringVar(value="准备定位 ...")
        tk.Label(
            self.root, textvariable=self.status_var,
            fg="#FFFF00", bg="#1E1E1E", font=("Consolas", 9), wraplength=480,
        ).pack(pady=5, fill="x", padx=20)

    def _start_locate(self):
        self.rescan_btn.config(state="disabled", text="定位中 ...")

        def task():
            ok = self._reader.locate()
            self.root.after(0, lambda: self._on_locate_done(ok))

        threading.Thread(target=task, daemon=True).start()

    def _on_locate_done(self, ok):
        self.rescan_btn.config(state="normal", text="重新定位")
        if ok:
            self._launch_display()
        else:
            self.status_var.set(
                "定位失败 — 请确认游戏进程正常且已进入作战关卡,\n"
                "然后点「重新定位」"
            )

    def _launch_display(self):
        for w in self.root.winfo_children():
            w.destroy()
        DeployDisplayApp(self.root, self._reader, self._process_name)

class ProcessWaiter:
    """哨兵模式：等待 adb 设备上的游戏进程，找到后直接进入部署引导。"""

    def __init__(self, root):
        self.root = root
        self.root.title("摸轴工具")
        self.root.geometry("350x120")
        self.root.configure(bg="#1E1E1E")
        self.root.attributes("-topmost", True)

        self.label = tk.Label(
            self.root, text="等待游戏进程...",
            fg="#00FFFF", bg="#1E1E1E", font=("Consolas", 14, "bold"),
        )
        self.label.pack(expand=True, fill="both")

        self._dot_count = 0
        self._checking = False
        self._check()

    def _check(self):
        self._dot_count = (self._dot_count + 1) % 4
        self.label.config(text=f"正在监听游戏进程{'.' * self._dot_count}")
        if not self._checking:
            self._checking = True
            threading.Thread(target=self._try_connect, daemon=True).start()
        self.root.after(1000, self._check)

    def _try_connect(self):
        try:
            mc = MemCore()
            pid = mc.connect()
        except Exception:
            self._checking = False
            return
        name = f"{mc.package} (pid {pid})"
        self.root.after(0, lambda: self._launch_wizard(name, mc))

    def _launch_wizard(self, process_name, mc):
        for w in self.root.winfo_children():
            w.destroy()
        self.root.attributes("-topmost", False)
        DeployWizardApp(self.root, process_name, mc)


def main():
    root = tk.Tk()
    ProcessWaiter(root)
    root.mainloop()


if __name__ == "__main__":
    main()
