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
from pathlib import Path

from ak_memory_reader import AKMemoryReader


def _timer_data_dir() -> Path:
    """
    与 backend/app/services/timer_provider.py 保持一致：
    - 若设置 AK_TIMER_DATA_DIR，则优先使用该目录
    - 冻结 EXE 默认写到 %LOCALAPPDATA%/ArknightsTimer/data
    - 源码运行写到仓库 backend/data
    """
    env_dir = os.getenv("AK_TIMER_DATA_DIR", "").strip()
    if env_dir:
        return Path(env_dir)
    if getattr(sys, "frozen", False):
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ArknightsTimer" / "data"
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "backend" / "data"


def _write_timer_hook(process_name: str, time_address_hex: str) -> None:
    """供打轴桌面端读取：进程名 + 时间地址（帧地址仍由 AKMemoryReader 推导）。"""
    data_root = _timer_data_dir()
    path = data_root / "timer_hook.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "process_name": process_name,
        "time_address": time_address_hex.strip(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def scan_memory_chunk(pid, base_address, region_size, min_val, max_val):
    try:
        pm = pymem.Pymem()
        pm.open_process_from_id(pid)
        data = pm.read_bytes(base_address, region_size)

        remainder = len(data) % 4
        if remainder != 0:
            data = data[:-remainder]

        results = []
        for offset, (val,) in enumerate(struct.iter_unpack('<f', data)):
            if min_val <= val <= max_val:
                results.append(base_address + offset * 4)
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

        list_frame = tk.Frame(self.root, bg="black")
        self.listbox = tk.Listbox(list_frame, bg="black", fg="#00FFFF", font=("Consolas", 11),
                                  selectbackground="#0078D7", height=6)
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        self.listbox.config(yscrollcommand=scrollbar.set)

        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.list_frame = list_frame

        self.listbox.bind("<Double-Button-1>", lambda event: self.confirm_selection())

        self.confirm_btn = tk.Button(self.root, text="确认选中地址 (或双击列表)", command=self.confirm_selection,
                                     bg="#005500", fg="white", font=("Consolas", 10, "bold"))

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

        if 0 < len(self.candidate_addresses) <= 15:
            self.show_selection_list()
        elif len(self.candidate_addresses) == 0:
            messagebox.showwarning("扫描失败",
                                   "候选地址清零，请重启程序重新扫描！\n注意：查找浮点时间时，请务必暂停游戏后再搜！")

    def first_scan(self, pm, min_val, max_val):
        pid = pm.process_id
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

        max_workers = min(32, os.cpu_count() * 2)
        total = len(regions)
        completed = 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(scan_memory_chunk, pid, base, size, min_val, max_val) for base, size in regions]
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                if res:
                    self.candidate_addresses.extend(res)
                completed += 1
                if completed % 20 == 0:
                    self.scan_btn.config(text=f"Scanning... {int((completed / total) * 100)}%")
                    self.root.update()

    def next_scan(self, pm, min_val, max_val):
        survivors = []
        total_addrs = len(self.candidate_addresses)

        for i, addr in enumerate(self.candidate_addresses):
            try:
                data = pm.read_bytes(addr, 4)
                val = struct.unpack('<f', data)[0]
                if min_val <= val <= max_val:
                    survivors.append(addr)
            except Exception:
                pass

            if i % 1000 == 0 and total_addrs > 0:
                self.scan_btn.config(text=f"Filtering... {int((i / total_addrs) * 100)}%")
                self.root.update()

        self.candidate_addresses = survivors

    def show_selection_list(self):
        self.info_label.config(text="Step 3: 双击真理地址")
        self.scan_btn.pack_forget()

        self.list_frame.pack(fill="both", expand=True, padx=20, pady=5)
        self.confirm_btn.pack(pady=10)

        self.listbox.delete(0, tk.END)
        recommended_index = 0

        for idx, addr in enumerate(self.candidate_addresses):
            hex_str = hex(addr).upper().replace("0X", "")
            display_text = hex_str

            if hex_str.endswith("28"):
                display_text += " <-- [真理地址]"
                recommended_index = idx

            self.listbox.insert(tk.END, display_text)

        self.listbox.selection_set(recommended_index)
        self.listbox.activate(recommended_index)

    def confirm_selection(self):
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning("提示", "请先选择一个地址！")
            return

        index = selection[0]
        selected_address = self.candidate_addresses[index]
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
                try:
                    _write_timer_hook(reader.process_name, address_hex_str)
                except OSError:
                    pass
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