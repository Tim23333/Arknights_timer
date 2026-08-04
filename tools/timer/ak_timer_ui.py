import json
import tkinter as tk
from tkinter import messagebox, ttk
import struct
import pymem.memory
import pymem.exception
import concurrent.futures
import os
import sys
import ctypes
import time
import socket
from pathlib import Path

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

from ak_memory_reader import AKMemoryReader
from process_scan import find_emulator_processes, list_processes


# 单次 ReadProcessMemory 的最大读取量。扫描任务会按该大小切块，避免把模拟器的
# 整块 Guest RAM 一次性复制到 Python 进程中。
SCAN_CHUNK_SIZE = 4 * 1024 * 1024
MAX_SCAN_WORKERS = 32
MAX_PENDING_TASKS_PER_WORKER = 2


def _send_hook_via_tcp(process_name: str, time_address_hex: str) -> bool:
    """通过 TCP 将 hook 数据推送给打轴工具。失败时静默返回 False（不影响寻址工具自身功能）。"""
    port_str = os.getenv("AK_HOOK_PORT", "").strip()
    if not port_str:
        return False
    try:
        payload = json.dumps({
            "process_name": process_name,
            "time_address": time_address_hex.strip(),
        }, ensure_ascii=False)
        with socket.create_connection(("127.0.0.1", int(port_str)), timeout=3) as sock:
            sock.sendall((payload + "\n").encode("utf-8"))
        return True
    except Exception:
        return False


def scan_memory_chunk(handle, base_address, region_size, min_val, max_val):
    try:
        data = pymem.memory.read_bytes(handle, base_address, region_size)

        remainder = len(data) % 4
        if remainder != 0:
            data = data[:-remainder]

        if HAS_NUMPY:
            arr = np.frombuffer(data, dtype='<f4')
            mask = (arr >= min_val) & (arr <= max_val)
            indices = np.nonzero(mask)[0]
            addrs = (indices.astype(np.int64) * 4 + base_address)
            addrs = addrs[(addrs & 0xFF) == 0x28]
            return addrs.tolist()
        else:
            results = []
            for offset, (val,) in enumerate(struct.iter_unpack('<f', data)):
                if min_val <= val <= max_val:
                    addr = base_address + offset * 4
                    if addr & 0xFF == 0x28:
                        results.append(addr)
            return results
    except Exception:
        return []


def iter_scan_chunks(regions, chunk_size=SCAN_CHUNK_SIZE):
    """把 VirtualQueryEx 返回的区域惰性拆成固定大小的扫描块。"""
    for base, size in regions:
        offset = 0
        while offset < size:
            current_size = min(chunk_size, size - offset)
            yield base + offset, current_size
            offset += current_size


class MemoryScannerWizard:
    def __init__(self, root, reader, on_complete_callback):
        self.root = root
        self.reader = reader
        self.on_complete = on_complete_callback

        self.root.title("Tim's Arknights Scanner")
        self.root.geometry("400x380")
        self.root.configure(bg="#1E1E1E")

        self.candidate_addresses = []

        proc_label = tk.Label(self.root, text=f"Target: {self.reader.process_name}", fg="#AAAAAA", bg="#1E1E1E",
                              font=("Consolas", 9))
        proc_label.pack(pady=(5, 0))

        self.info_label = tk.Label(self.root, text="Step 1: 暂停游戏后扫范围", fg="#00FF00", bg="#1E1E1E",
                                   font=("Consolas", 12, "bold"))
        self.info_label.pack(pady=5)

        self.count_label = tk.Label(self.root, text="当前候选地址数: 0", fg="white", bg="#1E1E1E",
                                    font=("Consolas", 10))
        self.count_label.pack(pady=5)

        frame_input = tk.Frame(self.root, bg="#1E1E1E")
        frame_input.pack(pady=10)

        tk.Label(frame_input, text="Min Value:", fg="white", bg="#1E1E1E", font=("Consolas", 10)).grid(row=0, column=0,
                                                                                                       padx=5)
        self.entry_min = tk.Entry(frame_input, width=10, bg="black", fg="#00FF00", font=("Consolas", 12))
        self.entry_min.grid(row=0, column=1, padx=5)

        tk.Label(frame_input, text="Max Value:", fg="white", bg="#1E1E1E", font=("Consolas", 10)).grid(row=1, column=0,
                                                                                                       padx=5, pady=10)
        self.entry_max = tk.Entry(frame_input, width=10, bg="black", fg="#00FF00", font=("Consolas", 12))
        self.entry_max.grid(row=1, column=1, padx=5, pady=10)

        self.scan_btn = tk.Button(self.root, text="Start First Scan", command=self.perform_scan, bg="#333333",
                                  fg="white", font=("Consolas", 10, "bold"))
        self.scan_btn.pack(pady=10)

    def perform_scan(self):
        try:
            min_val = float(self.entry_min.get())
            max_val = float(self.entry_max.get())
        except ValueError:
            messagebox.showerror("输入错误", "请输入有效的数字！")
            return

        pm = self.reader.pm

        if not self.candidate_addresses:
            self.scan_btn.config(state="disabled", text="Scanning (并发捞针中)...")
            self.root.update()
            self.first_scan(pm, min_val, max_val)
            self.info_label.config(text="Step 2: 走秒后暂停，再扫描")
        else:
            self.scan_btn.config(state="disabled", text="Filtering (单线精准校验)...")
            self.root.update()
            self.next_scan(pm, min_val, max_val)

        self.count_label.config(text=f"当前候选地址数: {len(self.candidate_addresses)}")
        self.scan_btn.config(state="normal", text="Next Scan")

        self.entry_min.delete(0, tk.END)
        self.entry_max.delete(0, tk.END)

        if len(self.candidate_addresses) == 1:
            self.confirm_selection()
        elif len(self.candidate_addresses) == 0:
            messagebox.showwarning("扫描失败",
                                   "候选地址清零，请重启程序重新扫描！\n注意：查找浮点时间时，请务必暂停游戏后再搜！")

    def first_scan(self, pm, min_val, max_val):
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

        total_bytes = sum(size for _, size in regions)
        if total_bytes == 0:
            return

        max_workers = min(MAX_SCAN_WORKERS, max(1, (os.cpu_count() or 1) * 2))
        max_pending = max_workers * MAX_PENDING_TASKS_PER_WORKER
        chunks = iter(iter_scan_chunks(regions))
        scanned_bytes = 0
        last_update = time.monotonic()

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            pending = {}

            def submit_next_chunk():
                try:
                    base, size = next(chunks)
                except StopIteration:
                    return False
                future = executor.submit(scan_memory_chunk, handle, base, size, min_val, max_val)
                pending[future] = size
                return True

            for _ in range(max_pending):
                if not submit_next_chunk():
                    break

            while pending:
                done, _ = concurrent.futures.wait(
                    pending,
                    return_when=concurrent.futures.FIRST_COMPLETED,
                )
                for future in done:
                    chunk_bytes = pending.pop(future)
                    res = future.result()
                    if res:
                        self.candidate_addresses.extend(res)
                    scanned_bytes += chunk_bytes
                    submit_next_chunk()

                now = time.monotonic()
                if now - last_update >= 0.2:
                    self.scan_btn.config(text=f"Scanning... {int((scanned_bytes / total_bytes) * 100)}%")
                    self.root.update()
                    last_update = now

    def next_scan(self, pm, min_val, max_val):
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
                    val = struct.unpack_from('<f', page_data, offset)[0]
                    if min_val <= val <= max_val and (addr & 0xFF) == 0x28:
                        survivors.append(addr)
            except Exception:
                for addr in batch:
                    try:
                        data = pymem.memory.read_bytes(handle, addr, 4)
                        val = struct.unpack('<f', data)[0]
                        if min_val <= val <= max_val and (addr & 0xFF) == 0x28:
                            survivors.append(addr)
                    except Exception:
                        pass

            processed += len(batch)
            now = time.monotonic()
            if now - last_update >= 0.2:
                self.scan_btn.config(text=f"Filtering... {int((processed / total) * 100)}%")
                self.root.update()
                last_update = now

        self.candidate_addresses = survivors

    def confirm_selection(self):
        selected_address = self.candidate_addresses[0]
        hex_str = hex(selected_address).upper()

        for widget in self.root.winfo_children():
            widget.destroy()

        self.on_complete(hex_str)


class TimerApp:
    def __init__(self, root, reader):
        self.root = root
        self.reader = reader

        self.root.title("Arknights Data Overlay")
        self.root.geometry("380x140")
        self.root.configure(bg="black")
        self.root.attributes("-topmost", True)

        self.time_label = tk.Label(self.root, text="Time : --", font=("Consolas", 28, "bold"), fg="#00FF00", bg="black",
                                   anchor="w")
        self.time_label.pack(expand=True, fill="both", padx=20)

        self.frame_label = tk.Label(self.root, text="Frame: --", font=("Consolas", 28, "bold"), fg="#00FFFF",
                                    bg="black", anchor="w")
        self.frame_label.pack(expand=True, fill="both", padx=20)

        self.update_data()

    def update_data(self):
        game_time, frame_count = self.reader.get_game_data()

        if game_time is not None and frame_count is not None:
            self.time_label.config(text=f"Time : {game_time:.6f} s", fg="#00FF00")
            self.frame_label.config(text=f"Frame: {frame_count}", fg="#00FFFF")
        else:
            self.time_label.config(text="Data Invalid", fg="#FF0000")
            self.frame_label.config(text="Frame: --", fg="#FF0000")

        self.root.after(10, self.update_data)


class ProcessPickerDialog:
    """兜底：自动识别不到模拟器时，手动选择持有游戏内存的进程。"""

    def __init__(self, parent, on_pick):
        self.on_pick = on_pick
        self.processes = []

        self.top = tk.Toplevel(parent)
        self.top.title("手动选择模拟器进程")
        self.top.geometry("680x440")
        self.top.configure(bg="#1E1E1E")

        hint = tk.Label(
            self.top,
            text="选择持有游戏内存的模拟器虚拟机进程：MuMu 5.0 通常是 MuMuNxDevice.exe，"
                 "旧版 MuMu 是 MuMuVMMHeadless.exe（不是 MuMuPlayer.exe 界面进程）。",
            fg="#AAAAAA", bg="#1E1E1E", font=("Consolas", 9),
            wraplength=640, justify="left")
        hint.pack(padx=10, pady=(8, 4), anchor="w")

        filter_row = tk.Frame(self.top, bg="#1E1E1E")
        filter_row.pack(fill="x", padx=10)
        tk.Label(filter_row, text="筛选:", fg="white", bg="#1E1E1E",
                 font=("Consolas", 10)).pack(side="left")
        self.filter_var = tk.StringVar()
        entry = tk.Entry(filter_row, textvariable=self.filter_var, bg="black",
                         fg="#00FF00", font=("Consolas", 10))
        entry.pack(side="left", fill="x", expand=True, padx=5)
        self.filter_var.trace_add("write", lambda *_: self._reload_rows())
        entry.focus_set()

        tree_frame = tk.Frame(self.top, bg="#1E1E1E")
        tree_frame.pack(fill="both", expand=True, padx=10, pady=6)
        self.tree = ttk.Treeview(tree_frame, columns=("name", "pid", "path"),
                                 show="headings", height=14)
        self.tree.heading("name", text="进程名")
        self.tree.heading("pid", text="PID")
        self.tree.heading("path", text="路径")
        self.tree.column("name", width=180)
        self.tree.column("pid", width=70, anchor="e")
        self.tree.column("path", width=380)
        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda _e: self._confirm())

        btn_row = tk.Frame(self.top, bg="#1E1E1E")
        btn_row.pack(fill="x", padx=10, pady=(0, 10))
        tk.Button(btn_row, text="使用选中进程", command=self._confirm, bg="#333333",
                  fg="white", font=("Consolas", 10, "bold")).pack(side="left")
        tk.Button(btn_row, text="刷新列表", command=self._reload_processes, bg="#333333",
                  fg="white", font=("Consolas", 10)).pack(side="left", padx=8)

        self._reload_processes()

    def _reload_processes(self):
        self.processes = sorted(list_processes(), key=lambda item: item[0].lower())
        self._reload_rows()

    def _reload_rows(self):
        keyword = self.filter_var.get().strip().lower()
        self.tree.delete(*self.tree.get_children())
        for name, pid, path in self.processes:
            if keyword and keyword not in f"{name} {path}".lower():
                continue
            self.tree.insert("", "end", values=(name, pid, path))

    def _confirm(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("未选择", "请先在列表中选择一个进程。", parent=self.top)
            return
        name = str(self.tree.item(selection[0], "values")[0])
        self.top.destroy()
        self.on_pick(name)


class ProcessWaiter:
    """哨兵模式：后台静默轮询等待模拟器启动"""

    def __init__(self, root):
        self.root = root
        self.root.title("Waiting for Emulator")
        self.root.geometry("350x160")
        self.root.configure(bg="#1E1E1E")
        self.root.attributes("-topmost", True)

        self.label = tk.Label(self.root, text="等待模拟器启动...", fg="#00FFFF", bg="#1E1E1E",
                              font=("Consolas", 14, "bold"))
        self.label.pack(expand=True, fill="both")

        # 兜底：自动识别失败时手动选择持有游戏内存的模拟器进程
        self.picker = None
        self.pick_btn = tk.Button(self.root, text="找不到？手动选择进程",
                                  command=self.open_process_picker, bg="#333333",
                                  fg="white", font=("Consolas", 10))
        self.pick_btn.pack(pady=(0, 10))

        self.dot_count = 0
        self.check_process()

    def check_process(self):
        # 制造简单的动效，让界面看起来不是卡死的
        self.dot_count = (self.dot_count + 1) % 4
        dots = "." * self.dot_count
        self.label.config(text=f"正在监听模拟器进程{dots}")

        # 已知名单 (含 MuMu 5.0 的 MuMuNxDevice.exe) 优先，名称/路径特征兜底
        for name, _pid, _path in find_emulator_processes():
            try:
                # 尝试触碰该进程
                pymem.Pymem(name)
            except Exception:
                continue
            # 找到目标，瞬间切换形态
            self.launch_wizard(name)
            return

        # 没找到，设定 1000 毫秒后再次无阻塞调用自己
        self.root.after(1000, self.check_process)

    def open_process_picker(self):
        if self.picker is not None and self.picker.top.winfo_exists():
            self.picker.top.lift()
            return
        self.picker = ProcessPickerDialog(
            self.root, lambda name: self.launch_wizard(name, exit_on_failure=False))

    def launch_wizard(self, found_process, exit_on_failure=True):
        reader = AKMemoryReader(process_name=found_process)
        if not reader.connect():
            messagebox.showerror("连接失败", f"挂载 {found_process} 时被系统拒绝。\n请确保程序以管理员权限运行。")
            if exit_on_failure:
                sys.exit()
            return

        # 清除等待界面的UI元素
        for widget in self.root.winfo_children():
            widget.destroy()

        # 扫描向导不需要强行置顶，避免挡住用户的其他操作
        self.root.attributes("-topmost", False)

        def launch_timer_ui(address_hex_str):
            if reader.set_address(address_hex_str):
                _send_hook_via_tcp(reader.process_name, address_hex_str)
                self.root.attributes("-topmost", True)
                TimerApp(self.root, reader)
            else:
                messagebox.showerror("错误", "挂载时间与帧数地址失败！")
                self.root.destroy()

        # 唤醒正式的扫描向导
        MemoryScannerWizard(self.root, reader, launch_timer_ui)


def main():
    main_root = tk.Tk()
    # 启动哨兵模式，接管控制流
    waiter = ProcessWaiter(main_root)
    main_root.mainloop()


# ================= 权限提权核心模块 =================
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


if __name__ == "__main__":
    if is_admin():
        main()
    else:
        script = os.path.abspath(sys.argv[0])
        params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
        sys.exit()
