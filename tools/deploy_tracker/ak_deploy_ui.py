import json
import os
import socket
import struct
import sys
import time
import ctypes
import concurrent.futures
from pathlib import Path
from tkinter import messagebox, ttk
import tkinter as tk

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import pymem
import pymem.exception
import pymem.memory

from tools.timer.ak_memory_reader import AKMemoryReader
from tools.deploy_tracker.ak_deploy_reader import DeployTrackerReader

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


EMULATOR_PROCESSES = [
    "MuMuVMMHeadless.exe",
    "NemuHeadless.exe",
    "Ld9BoxHeadless.exe",
    "LdBoxHeadless.exe",
    "dnplayer.exe",
    "NoxVMMHeadless.exe",
    "HD-Player.exe",
    "MEmuHeadless.exe",
]


# ---- TCP 通信 ----

def _send_hook_via_tcp(process_name: str, time_address_hex: str) -> bool:
    """与 timer 工具同款的 TCP 地址推送。"""
    port_str = os.getenv("AK_HOOK_PORT", "").strip()
    if not port_str:
        return False
    try:
        payload = json.dumps(
            {"process_name": process_name, "time_address": time_address_hex.strip()},
            ensure_ascii=False,
        )
        with socket.create_connection(("127.0.0.1", int(port_str)), timeout=3) as sock:
            sock.sendall((payload + "\n").encode("utf-8"))
        return True
    except Exception:
        return False


def _send_events_via_tcp(process_name: str, events: list) -> bool:
    """推送部署事件到打轴工具后端。"""
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


# ---- 内存扫描（复用 timer 的算法） ----

def scan_memory_chunk(handle, base_address, region_size, min_val, max_val):
    """与 ak_timer_ui.py 完全相同的扫描函数。"""
    try:
        data = pymem.memory.read_bytes(handle, base_address, region_size)

        remainder = len(data) % 4
        if remainder != 0:
            data = data[:-remainder]

        if HAS_NUMPY:
            arr = np.frombuffer(data, dtype="<f4")
            mask = (arr >= min_val) & (arr <= max_val)
            indices = np.nonzero(mask)[0]
            addrs = (indices.astype(np.int64) * 4 + base_address)
            addrs = addrs[(addrs & 0xFF) == 0x28]
            return addrs.tolist()
        else:
            results = []
            for offset, (val,) in enumerate(struct.iter_unpack("<f", data)):
                if min_val <= val <= max_val:
                    addr = base_address + offset * 4
                    if addr & 0xFF == 0x28:
                        results.append(addr)
            return results
    except Exception:
        return []


# ---- 扫描向导（从 timer 搬来的逻辑，确认地址后进入部署显示） ----

class DeployScannerWizard:
    """引导用户扫描 s_fixedPlayTimeFloat，找到后自动连接 BattleController。"""

    def __init__(self, root, reader: AKMemoryReader, on_complete_callback):
        self.root = root
        self.reader = reader
        self.on_complete = on_complete_callback

        self.root.title("摸轴工具 — 扫描地址")
        self.root.geometry("400x380")
        self.root.configure(bg="#1E1E1E")

        self.candidate_addresses = []

        tk.Label(
            self.root,
            text=f"目标: {self.reader.process_name}",
            fg="#AAAAAA",
            bg="#1E1E1E",
            font=("Consolas", 9),
        ).pack(pady=(5, 0))

        self.info_label = tk.Label(
            self.root,
            text="Step 1: 暂停游戏后填入时间范围，开始扫描",
            fg="#00FF00",
            bg="#1E1E1E",
            font=("Consolas", 11, "bold"),
        )
        self.info_label.pack(pady=5)

        self.count_label = tk.Label(
            self.root,
            text="候选地址: 0",
            fg="white",
            bg="#1E1E1E",
            font=("Consolas", 10),
        )
        self.count_label.pack(pady=5)

        frame_input = tk.Frame(self.root, bg="#1E1E1E")
        frame_input.pack(pady=10)

        tk.Label(frame_input, text="最小值:", fg="white", bg="#1E1E1E", font=("Consolas", 10)).grid(
            row=0, column=0, padx=5
        )
        self.entry_min = tk.Entry(frame_input, width=10, bg="black", fg="#00FF00", font=("Consolas", 12))
        self.entry_min.grid(row=0, column=1, padx=5)

        tk.Label(frame_input, text="最大值:", fg="white", bg="#1E1E1E", font=("Consolas", 10)).grid(
            row=1, column=0, padx=5, pady=10
        )
        self.entry_max = tk.Entry(frame_input, width=10, bg="black", fg="#00FF00", font=("Consolas", 12))
        self.entry_max.grid(row=1, column=1, padx=5, pady=10)

        self.scan_btn = tk.Button(
            self.root,
            text="开始首次扫描",
            command=self._perform_scan,
            bg="#333333",
            fg="white",
            font=("Consolas", 10, "bold"),
        )
        self.scan_btn.pack(pady=10)

    def _perform_scan(self):
        try:
            min_val = float(self.entry_min.get())
            max_val = float(self.entry_max.get())
        except ValueError:
            messagebox.showerror("输入错误", "请输入有效的数字！")
            return

        pm = self.reader.pm

        if not self.candidate_addresses:
            self.scan_btn.config(state="disabled", text="并发扫描中...")
            self.root.update()
            self._first_scan(pm, min_val, max_val)
            self.info_label.config(text="Step 2: 走秒后暂停，再填入新时间范围扫描")
        else:
            self.scan_btn.config(state="disabled", text="精准过滤中...")
            self.root.update()
            self._next_scan(pm, min_val, max_val)

        self.count_label.config(text=f"候选地址: {len(self.candidate_addresses)}")
        self.scan_btn.config(state="normal", text="继续扫描")

        self.entry_min.delete(0, tk.END)
        self.entry_max.delete(0, tk.END)

        if len(self.candidate_addresses) == 1:
            self._confirm()
        elif len(self.candidate_addresses) == 0:
            messagebox.showwarning("扫描失败", "候选地址清零，请重启程序重新扫描！\n注意：查找浮点时间时，请务必暂停游戏后再搜！")

    def _first_scan(self, pm, min_val, max_val):
        handle = pm.process_handle
        regions = []
        curr = 0
        while True:
            try:
                mbi = pymem.memory.virtual_query(pm.process_handle, curr)
                curr += mbi.RegionSize
                if mbi.State == 0x1000 and (mbi.Protect & 0x66) and mbi.RegionSize >= 1024:
                    regions.append((mbi.BaseAddress, mbi.RegionSize))
            except Exception:
                break

        if regions:
            regions.sort(key=lambda r: r[0])
            merged = []
            buf_base, buf_size = regions[0]
            for base, size in regions[1:]:
                if base == buf_base + buf_size:
                    buf_size += size
                else:
                    merged.append((buf_base, buf_size))
                    buf_base, buf_size = base, size
            merged.append((buf_base, buf_size))
            regions = merged

        max_workers = min(32, (os.cpu_count() or 4) * 2)
        total = len(regions)
        completed = 0
        last_update = time.monotonic()

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(scan_memory_chunk, handle, base, size, min_val, max_val)
                for base, size in regions
            ]
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                if res:
                    self.candidate_addresses.extend(res)
                completed += 1
                now = time.monotonic()
                if now - last_update >= 0.2:
                    self.scan_btn.config(text=f"扫描中... {int((completed / total) * 100)}%")
                    self.root.update()
                    last_update = now

    def _next_scan(self, pm, min_val, max_val):
        survivors = []
        handle = pm.process_handle
        PAGE_SIZE = 0x1000
        sorted_addrs = sorted(self.candidate_addresses)
        total = len(sorted_addrs)
        last_update = time.monotonic()
        processed = 0

        i = 0
        while i < total:
            page_start = sorted_addrs[i] & ~(PAGE_SIZE - 1)
            page_end = page_start + PAGE_SIZE

            batch = []
            while i < total and sorted_addrs[i] < page_end:
                batch.append(sorted_addrs[i])
                i += 1

            try:
                page_data = pymem.memory.read_bytes(handle, page_start, PAGE_SIZE)
                for addr in batch:
                    offset = addr - page_start
                    val = struct.unpack_from("<f", page_data, offset)[0]
                    if min_val <= val <= max_val and (addr & 0xFF) == 0x28:
                        survivors.append(addr)
            except Exception:
                for addr in batch:
                    try:
                        data = pymem.memory.read_bytes(handle, addr, 4)
                        val = struct.unpack("<f", data)[0]
                        if min_val <= val <= max_val and (addr & 0xFF) == 0x28:
                            survivors.append(addr)
                    except Exception:
                        pass

            processed += len(batch)
            now = time.monotonic()
            if now - last_update >= 0.2:
                self.scan_btn.config(text=f"过滤中... {int((processed / total) * 100)}%")
                self.root.update()
                last_update = now

        self.candidate_addresses = survivors

    def _confirm(self):
        selected_address = self.candidate_addresses[0]
        hex_str = hex(selected_address).upper()

        for widget in self.root.winfo_children():
            widget.destroy()

        self.on_complete(hex_str)


# ---- 部署时间轴显示 ----

class DeployDisplayApp:
    """部署时间轴显示窗口。"""

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
            toolbar,
            text="仅部署",
            variable=self._show_spawn_only,
            fg="white",
            bg="#2A2A2A",
            selectcolor="#2A2A2A",
            activebackground="#2A2A2A",
            activeforeground="white",
            font=("Consolas", 10),
        )
        cb.pack(side="left", padx=10, pady=5)

        tcp_btn = tk.Button(
            toolbar,
            text="推送至打轴工具",
            command=self._tcp_push,
            bg="#444444",
            fg="white",
            font=("Consolas", 9),
        )
        tcp_btn.pack(side="right", padx=10, pady=5)

        export_btn = tk.Button(
            toolbar,
            text="导出 JSON",
            command=self._export_json,
            bg="#444444",
            fg="white",
            font=("Consolas", 9),
        )
        export_btn.pack(side="right", padx=5, pady=5)

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
                "",
                "end",
                values=(
                    f"{e['timestamp']:.3f}",
                    e["charId"],
                    e["opName"],
                    position,
                    e["directionName"],
                    e["uniqueId"],
                    e["extraInfo"],
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


# ---- 流程控制 ----

class ProcessWaiter:
    """哨兵模式：后台静默轮询等待模拟器启动。"""

    def __init__(self, root):
        self.root = root
        self.root.title("摸轴工具")
        self.root.geometry("350x120")
        self.root.configure(bg="#1E1E1E")
        self.root.attributes("-topmost", True)

        self.label = tk.Label(
            self.root,
            text="等待模拟器启动...",
            fg="#00FFFF",
            bg="#1E1E1E",
            font=("Consolas", 14, "bold"),
        )
        self.label.pack(expand=True, fill="both")

        self._dot_count = 0
        self._check()

    def _check(self):
        self._dot_count = (self._dot_count + 1) % 4
        dots = "." * self._dot_count
        self.label.config(text=f"正在监听模拟器进程{dots}")

        found = None
        for proc in EMULATOR_PROCESSES:
            try:
                pymem.Pymem(proc)
                found = proc
                break
            except Exception:
                pass

        if found:
            self._launch_scanner(found)
        else:
            self.root.after(1000, self._check)

    def _launch_scanner(self, process_name):
        for w in self.root.winfo_children():
            w.destroy()
        self.root.attributes("-topmost", False)

        reader = AKMemoryReader(process_name=process_name)
        if not reader.connect():
            messagebox.showerror("连接失败", f"挂载 {process_name} 时被系统拒绝。\n请确保程序以管理员权限运行。")
            sys.exit(1)

        def on_address_found(address_hex_str):
            reader.set_address(address_hex_str)
            _send_hook_via_tcp(reader.process_name, address_hex_str)

            # 显示发现进度界面
            self._show_discovery_progress(address_hex_str, reader, process_name)

        DeployScannerWizard(self.root, reader, on_address_found)

    def _show_discovery_progress(self, address_hex_str, reader, process_name):
        for w in self.root.winfo_children():
            w.destroy()
        self.root.geometry("500x180")
        self.root.title("摸轴工具 — 发现 BattleController")
        self.root.attributes("-topmost", False)

        tk.Label(
            self.root,
            text=f"地址: {address_hex_str}",
            fg="#AAAAAA",
            bg="#1E1E1E",
            font=("Consolas", 9),
        ).pack(pady=(10, 5))

        status_var = tk.StringVar(value="正在发现 BattleController...")
        status_label = tk.Label(
            self.root,
            textvariable=status_var,
            fg="#00FF00",
            bg="#1E1E1E",
            font=("Consolas", 11, "bold"),
        )
        status_label.pack(pady=10)

        progress_var = tk.StringVar(value="")
        progress_label = tk.Label(
            self.root,
            textvariable=progress_var,
            fg="#FFFF00",
            bg="#1E1E1E",
            font=("Consolas", 10),
        )
        progress_label.pack(pady=5)

        self.root.update()

        addr_int = int(address_hex_str.replace("0x", "").replace("0X", ""), 16)
        deploy_reader = DeployTrackerReader(reader.pm, addr_int)
        deploy_reader.set_status_callback(lambda msg: progress_var.set(msg))

        ok = deploy_reader.discover()
        if not ok:
            status_var.set("未找到 BattleController")
            status_label.config(fg="#FF0000")
            progress_var.set("请确认已进入作战关卡，且战斗已开始。")

            retry_btn = tk.Button(
                self.root,
                text="重试",
                command=lambda: self._retry_discovery(address_hex_str, reader, process_name),
                bg="#444444",
                fg="white",
                font=("Consolas", 10),
            )
            retry_btn.pack(pady=10)
            return

        status_var.set("连接成功！")
        self.root.after(500, lambda: self._launch_display(deploy_reader, process_name))

    def _retry_discovery(self, address_hex_str, reader, process_name):
        for w in self.root.winfo_children():
            w.destroy()
        self._show_discovery_progress(address_hex_str, reader, process_name)

    def _launch_display(self, deploy_reader, process_name):
        for w in self.root.winfo_children():
            w.destroy()
        DeployDisplayApp(self.root, deploy_reader, process_name)


# ---- 启动 ----

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
