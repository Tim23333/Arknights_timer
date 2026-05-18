import json
import tkinter as tk
from tkinter import messagebox
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

        # Merge contiguous regions to reduce task count
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

        max_workers = min(32, os.cpu_count() * 2)
        total = len(regions)
        completed = 0
        last_update = time.monotonic()

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(scan_memory_chunk, handle, base, size, min_val, max_val) for base, size in regions]
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                if res:
                    self.candidate_addresses.extend(res)
                completed += 1
                now = time.monotonic()
                if now - last_update >= 0.2:
                    self.scan_btn.config(text=f"Scanning... {int((completed / total) * 100)}%")
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


class ProcessWaiter:
    """哨兵模式：后台静默轮询等待模拟器启动"""

    def __init__(self, root):
        self.root = root
        self.root.title("Waiting for Emulator")
        self.root.geometry("350x120")
        self.root.configure(bg="#1E1E1E")
        self.root.attributes("-topmost", True)

        self.label = tk.Label(self.root, text="等待模拟器启动...", fg="#00FFFF", bg="#1E1E1E",
                              font=("Consolas", 14, "bold"))
        self.label.pack(expand=True, fill="both")

        self.target_processes = [
            "MuMuVMMHeadless.exe",
            "NemuHeadless.exe",
            "Ld9BoxHeadless.exe",
            "LdBoxHeadless.exe",
            "dnplayer.exe",
            "NoxVMMHeadless.exe",
            "HD-Player.exe",
            "MEmuHeadless.exe"
        ]

        self.dot_count = 0
        self.check_process()

    def check_process(self):
        # 制造简单的动效，让界面看起来不是卡死的
        self.dot_count = (self.dot_count + 1) % 4
        dots = "." * self.dot_count
        self.label.config(text=f"正在监听模拟器进程{dots}")

        found_process = None
        for proc in self.target_processes:
            try:
                # 尝试触碰该进程
                pymem.Pymem(proc)
                found_process = proc
                break
            except Exception:
                pass

        if found_process:
            # 找到目标，瞬间切换形态
            self.launch_wizard(found_process)
        else:
            # 没找到，设定 1000 毫秒后再次无阻塞调用自己
            self.root.after(1000, self.check_process)

    def launch_wizard(self, found_process):
        reader = AKMemoryReader(process_name=found_process)
        if not reader.connect():
            messagebox.showerror("连接失败", f"挂载 {found_process} 时被系统拒绝。\n请确保程序以管理员权限运行。")
            sys.exit()

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