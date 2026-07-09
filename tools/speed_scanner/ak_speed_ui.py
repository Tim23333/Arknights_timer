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

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

import socket

def _send_speed_hook_via_tcp(process_name: str, speed_address_hex: str, timescale_address_hex: str) -> bool:
    """通过 TCP 将倍速/暂停地址推送给打轴工具。"""
    port_str = os.getenv("AK_HOOK_PORT", "").strip()
    if not port_str:
        return False
    try:
        payload = json.dumps({
            "process_name": process_name,
            "speed_address": speed_address_hex.strip(),
            "timescale_address": timescale_address_hex.strip(),
        }, ensure_ascii=False)
        with socket.create_connection(("127.0.0.1", int(port_str)), timeout=3) as sock:
            sock.sendall((payload + "\n").encode("utf-8"))
        return True
    except Exception:
        return False


from ak_speed_reader import (
    AKSpeedReader, SPEED_STANDARD, SPEED_FAST,
    OFFSET_M_STATE, OFFSET_M_SPEED_LEVEL,
    STATE_PLAYING,
)


# ============================================================
# 内存扫描函数
# ============================================================

def scan_int32_chunk(handle, base_address, region_size, target_val):
    """扫描 int32 == target_val 的地址"""
    try:
        data = pymem.memory.read_bytes(handle, base_address, region_size)
        remainder = len(data) % 4
        if remainder != 0:
            data = data[:-remainder]
        if HAS_NUMPY:
            arr = np.frombuffer(data, dtype='<i4')
            indices = np.nonzero(arr == target_val)[0]
            return (indices.astype(np.int64) * 4 + base_address).tolist()
        else:
            results = []
            for offset, (val,) in enumerate(struct.iter_unpack('<i', data)):
                if val == target_val:
                    results.append(base_address + offset * 4)
            return results
    except Exception:
        return []


def scan_float32_chunk(base_address, data, min_val, max_val):
    """扫描 float32 在 [min_val, max_val] 范围内的地址"""
    try:
        remainder = len(data) % 4
        if remainder != 0:
            data = data[:-remainder]
        if HAS_NUMPY:
            arr = np.frombuffer(data, dtype='<f4')
            mask = (arr >= min_val) & (arr <= max_val)
            indices = np.nonzero(mask)[0]
            return (indices.astype(np.int64) * 4 + base_address).tolist()
        else:
            results = []
            for offset, (val,) in enumerate(struct.iter_unpack('<f', data)):
                if min_val <= val <= max_val:
                    results.append(base_address + offset * 4)
            return results
    except Exception:
        return []


def get_memory_regions(pm):
    """获取所有可读内存区域（合并连续区域）"""
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
    if not regions:
        return regions
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
    return merged


# ============================================================
# 扫描向导 UI
# ============================================================

class SpeedScannerWizard:
    def __init__(self, root, reader, on_complete_callback):
        self.root = root
        self.reader = reader
        self.on_complete = on_complete_callback

        self.root.title("倍速/暂停寻址工具")
        self.root.geometry("480x420")
        self.root.configure(bg="#1E1E1E")

        # 状态
        self.phase = "speed"         # "speed" 或 "timescale"
        self.speed_candidates = []
        self.ts_candidates = []
        self.scan_round = 0
        self._next_scan_val = SPEED_STANDARD

        proc_label = tk.Label(
            self.root, text=f"Target: {self.reader.process_name}",
            fg="#AAAAAA", bg="#1E1E1E", font=("Consolas", 9),
        )
        proc_label.pack(pady=(5, 0))

        self.phase_label = tk.Label(
            self.root, text="Phase 1: 寻找倍速地址 (m_speedLevel)",
            fg="#FF8800", bg="#1E1E1E", font=("Consolas", 11, "bold"),
        )
        self.phase_label.pack(pady=5)

        self.info_label = tk.Label(
            self.root,
            text="请确保游戏处于 1 倍速，然后点击扫描",
            fg="#00FF00", bg="#1E1E1E", font=("Consolas", 11, "bold"),
        )
        self.info_label.pack(pady=5)

        self.count_label = tk.Label(
            self.root, text="候选地址数: 0", fg="white", bg="#1E1E1E",
            font=("Consolas", 10),
        )
        self.count_label.pack(pady=3)

        self.hint_label = tk.Label(
            self.root, text="", fg="#888888", bg="#1E1E1E",
            font=("Consolas", 9),
        )
        self.hint_label.pack(pady=2)

        # Phase 1 按钮区
        self.btn_frame_speed = tk.Frame(self.root, bg="#1E1E1E")
        self.btn_frame_speed.pack(pady=10)

        self.scan_btn = tk.Button(
            self.btn_frame_speed, text="扫描 1 倍速", command=self._on_scan_click,
            bg="#333333", fg="white", font=("Consolas", 10, "bold"),
            width=22, height=2,
        )
        self.scan_btn.pack(side="left", padx=5)

        self.confirm_btn = tk.Button(
            self.btn_frame_speed, text="确认地址", command=self._on_confirm_click,
            bg="#005500", fg="white", font=("Consolas", 10, "bold"),
            width=12, height=2, state="disabled",
        )
        self.confirm_btn.pack(side="left", padx=5)

        # Phase 2 按钮区（初始隐藏）
        self.btn_frame_ts = tk.Frame(self.root, bg="#1E1E1E")

        self.btn_ts_0 = tk.Button(
            self.btn_frame_ts, text="扫描 0 (暂停)", command=lambda: self._do_ts_scan_val(0.0),
            bg="#552222", fg="white", font=("Consolas", 10, "bold"), width=14, height=2,
        )
        self.btn_ts_0.pack(side="left", padx=3)

        self.btn_ts_1 = tk.Button(
            self.btn_frame_ts, text="扫描 1 (1倍速)", command=lambda: self._do_ts_scan_val(1.0),
            bg="#225522", fg="white", font=("Consolas", 10, "bold"), width=14, height=2,
        )
        self.btn_ts_1.pack(side="left", padx=3)

        self.btn_ts_2 = tk.Button(
            self.btn_frame_ts, text="扫描 2 (2倍速)", command=lambda: self._do_ts_scan_val(2.0),
            bg="#222255", fg="white", font=("Consolas", 10, "bold"), width=14, height=2,
        )
        self.btn_ts_2.pack(side="left", padx=3)

        self.btn_ts_confirm = tk.Button(
            self.btn_frame_ts, text="确认地址", command=self._on_confirm_click,
            bg="#005500", fg="white", font=("Consolas", 10, "bold"),
            width=10, height=2, state="disabled",
        )
        self.btn_ts_confirm.pack(side="left", padx=3)

    @property
    def _next_label(self):
        return "1 倍速" if self._next_scan_val == SPEED_STANDARD else "2 倍速"

    def _on_scan_click(self):
        if self.phase == "speed":
            self._do_speed_scan(self._next_scan_val)
        elif self.phase == "timescale":
            self._do_timescale_scan()

    def _on_confirm_click(self):
        if self.phase == "speed" and len(self.speed_candidates) == 1:
            self._enter_timescale_phase()
        elif self.phase == "timescale" and len(self.ts_candidates) == 1:
            self._confirm_all()

    # ── Phase 1: 扫描 m_speedLevel (int32) ──

    def _do_speed_scan(self, target_val):
        label = "1 倍速" if target_val == SPEED_STANDARD else "2 倍速"
        self.scan_btn.config(state="disabled", text=f"扫描 {label} 中...")
        self.confirm_btn.config(state="disabled")
        self.root.update()

        handle = self.reader.pm.process_handle

        if self.scan_round == 0:
            # 第一轮：全内存扫描
            regions = get_memory_regions(self.reader.pm)
            max_workers = min(32, os.cpu_count() * 2)
            total = len(regions)
            completed = 0
            last_update = time.monotonic()

            found = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [
                    executor.submit(scan_int32_chunk, handle, base, size, target_val)
                    for base, size in regions
                ]
                for future in concurrent.futures.as_completed(futures):
                    res = future.result()
                    if res:
                        found.extend(res)
                    completed += 1
                    now = time.monotonic()
                    if now - last_update >= 0.2:
                        pct = int((completed / total) * 100)
                        self.scan_btn.config(text=f"扫描 {label} 中... {pct}%")
                        self.root.update()
                        last_update = now

            self.speed_candidates = found
        else:
            # 后续轮次：只读候选地址
            survivors = self._filter_candidates(handle, self.speed_candidates, target_val)
            self.speed_candidates = survivors

        self.scan_round += 1
        count = len(self.speed_candidates)
        self.count_label.config(text=f"候选地址数: {count}")

        self._next_scan_val = SPEED_FAST if self._next_scan_val == SPEED_STANDARD else SPEED_STANDARD

        if count == 0:
            messagebox.showwarning("扫描失败", "候选地址清零，请重新开始扫描！")
            self._reset_speed()
        elif count == 1:
            self._verify_speed_single()
        else:
            self.info_label.config(
                text=f"第 {self.scan_round} 轮完成，请切到 {self._next_label} 后继续扫描",
            )
            self.hint_label.config(text=f"本轮({label})筛选后剩余 {count} 个")
            self.scan_btn.config(state="normal", text=f"扫描 {self._next_label}")
            self.confirm_btn.config(state="normal")

    def _filter_candidates(self, handle, addrs, target_val):
        """读取候选地址的当前 int32 值，保留 == target_val 的"""
        PAGE_SIZE = 0x1000
        sorted_addrs = sorted(addrs)
        total = len(sorted_addrs)
        last_update = time.monotonic()
        processed = 0
        survivors = []

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
                    val = struct.unpack_from('<i', page_data, offset)[0]
                    if val == target_val:
                        survivors.append(addr)
            except Exception:
                for addr in batch:
                    try:
                        data = pymem.memory.read_bytes(handle, addr, 4)
                        val = struct.unpack('<i', data)[0]
                        if val == target_val:
                            survivors.append(addr)
                    except Exception:
                        pass
            processed += len(batch)
            now = time.monotonic()
            if now - last_update >= 0.2:
                pct = int((processed / total) * 100)
                self.scan_btn.config(text=f"筛选中... {pct}%")
                self.root.update()
                last_update = now

        return survivors

    def _verify_speed_single(self):
        addr = self.speed_candidates[0]
        handle = self.reader.pm.process_handle
        state_offset = OFFSET_M_STATE - OFFSET_M_SPEED_LEVEL
        try:
            data = pymem.memory.read_bytes(handle, addr + state_offset, 4)
            state_val = struct.unpack('<i', data)[0]
            if state_val == STATE_PLAYING:
                self.info_label.config(text="✅ 找到倍速地址！")
                self.hint_label.config(text=f"m_speedLevel = {hex(addr)}")
                self.scan_btn.config(state="disabled", text="扫描完成")
                self.confirm_btn.config(state="normal")
                return
        except Exception:
            pass
        self.info_label.config(text="找到唯一地址（状态未验证）")
        self.hint_label.config(text=f"m_speedLevel = {hex(addr)}")
        self.scan_btn.config(state="disabled", text="扫描完成")
        self.confirm_btn.config(state="normal")

    def _enter_timescale_phase(self):
        """进入 Phase 2: 扫描 Time.timeScale"""
        self.reader.set_speed_address(hex(self.speed_candidates[0]))
        self.phase = "timescale"
        self.ts_candidates = []

        # 切换按钮区
        self.btn_frame_speed.pack_forget()
        self.btn_frame_ts.pack(pady=10)

        self.phase_label.config(text="Phase 2: 寻找 Time.timeScale")
        self.info_label.config(
            text="当前状态就点哪个按钮，交替点击缩小范围",
        )
        self.hint_label.config(text="建议：先点1，再暂停点0，反复直到剩1个")
        self.count_label.config(text="候选地址数: 0")

    def _set_ts_buttons_state(self, state):
        self.btn_ts_0.config(state=state)
        self.btn_ts_1.config(state=state)
        self.btn_ts_2.config(state=state)

    def _do_ts_scan_val(self, val):
        """Phase 2: 扫描指定 float 精确值"""
        self._set_ts_buttons_state("disabled")
        self.root.update()

        handle = self.reader.pm.process_handle
        min_val = val
        max_val = val

        if not self.ts_candidates:
            # 第一次：全内存扫描
            self.info_label.config(text=f"全内存扫描 float={val:g}...")
            self.root.update()

            regions = get_memory_regions(self.reader.pm)
            max_workers = min(32, os.cpu_count() * 2)
            total = len(regions)
            completed = 0
            last_update = time.monotonic()

            found = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [
                    executor.submit(self._ts_read_and_scan, handle, base, size, min_val, max_val)
                    for base, size in regions
                ]
                for future in concurrent.futures.as_completed(futures):
                    res = future.result()
                    if res:
                        found.extend(res)
                    completed += 1
                    now = time.monotonic()
                    if now - last_update >= 0.2:
                        pct = int((completed / total) * 100)
                        self.info_label.config(text=f"扫描 float={val:g}... {pct}%")
                        self.root.update()
                        last_update = now

            self.ts_candidates = found
        else:
            # 后续：筛选候选
            self.info_label.config(text=f"筛选 float={val:g}...")
            self.root.update()
            self.ts_candidates = self._ts_filter_candidates(handle, self.ts_candidates, min_val, max_val)

        count = len(self.ts_candidates)
        self.count_label.config(text=f"候选地址数: {count}")
        self._set_ts_buttons_state("normal")

        if count == 0:
            messagebox.showwarning("扫描失败", "候选地址清零，请重新开始！")
            self._reset_timescale()
        elif count == 1:
            self._verify_timescale_single()
        elif count <= 10:
            # 自动读取每个候选的当前值并显示
            self._show_candidate_values(handle)
        else:
            self.hint_label.config(text=f"本轮 float={val:g} 后剩余 {count} 个，继续切换状态扫描")

    def _ts_read_and_scan(self, handle, base, size, min_val, max_val):
        try:
            data = pymem.memory.read_bytes(handle, base, size)
            return scan_float32_chunk(base, data, min_val, max_val)
        except Exception:
            return []

    def _ts_filter_candidates(self, handle, addrs, min_val, max_val):
        """筛选候选地址中 float 在范围内的"""
        PAGE_SIZE = 0x1000
        sorted_addrs = sorted(addrs)
        total = len(sorted_addrs)
        survivors = []

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
                    if min_val <= val <= max_val:
                        survivors.append(addr)
            except Exception:
                for addr in batch:
                    try:
                        data = pymem.memory.read_bytes(handle, addr, 4)
                        val = struct.unpack('<f', data)[0]
                        if min_val <= val <= max_val:
                            survivors.append(addr)
                    except Exception:
                        pass

        return survivors

    def _show_candidate_values(self, handle):
        """弹出候选列表窗口，显示每个地址的实时值，支持手动选择"""
        win = tk.Toplevel(self.root)
        win.title(f"候选地址 ({len(self.ts_candidates)} 个)")
        win.geometry("420x400")
        win.configure(bg="#1E1E1E")
        win.attributes("-topmost", True)

        tk.Label(win, text="切换游戏状态（退出重进关卡等）观察值变化，点击选择正确地址",
                 fg="#00FF00", bg="#1E1E1E", font=("Consolas", 9), wraplength=400).pack(pady=5)

        list_frame = tk.Frame(win, bg="#1E1E1E")
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        rows = []
        for addr in self.ts_candidates:
            row = tk.Frame(list_frame, bg="#252526")
            row.pack(fill="x", pady=2)
            lbl_addr = tk.Label(row, text=hex(addr), fg="#AAAAAA", bg="#252526",
                                font=("Consolas", 10), width=16, anchor="w")
            lbl_addr.pack(side="left", padx=5)
            lbl_val = tk.Label(row, text="—", fg="#FFFF00", bg="#252526",
                               font=("Consolas", 10, "bold"), width=8)
            lbl_val.pack(side="left", padx=5)

            def _select(a=addr):
                self.ts_candidates = [a]
                win.destroy()
                self._verify_timescale_single()

            tk.Button(row, text="选择", command=_select,
                      bg="#005500", fg="white", font=("Consolas", 9)).pack(side="right", padx=5)
            rows.append((addr, lbl_val))

        def refresh():
            for addr, lbl in rows:
                try:
                    data = pymem.memory.read_bytes(handle, addr, 4)
                    v = struct.unpack('<f', data)[0]
                    lbl.config(text=f"{v:g}")
                except Exception:
                    lbl.config(text="?")

        tk.Button(win, text="刷新数值", command=refresh,
                  bg="#333333", fg="white", font=("Consolas", 10)).pack(pady=5)

        refresh()

    def _verify_timescale_single(self):
        addr = self.ts_candidates[0]
        self.info_label.config(text="✅ 找到 Time.timeScale 地址！")
        self.hint_label.config(text=f"Time.timeScale = {hex(addr)}")
        self._set_ts_buttons_state("disabled")
        self.btn_ts_confirm.config(state="normal")

    def _confirm_all(self):
        speed_hex = hex(self.speed_candidates[0]).upper()
        ts_hex = hex(self.ts_candidates[0]).upper()
        self.reader.set_speed_address(speed_hex)
        self.reader.set_timescale_address(ts_hex)
        _send_speed_hook_via_tcp(self.reader.process_name, speed_hex, ts_hex)
        for widget in self.root.winfo_children():
            widget.destroy()
        self.on_complete(speed_hex, ts_hex)

    def _reset_speed(self):
        self.scan_round = 0
        self.speed_candidates = []
        self._next_scan_val = SPEED_STANDARD
        self.info_label.config(text="请确保游戏处于 1 倍速，然后点击扫描")
        self.count_label.config(text="候选地址数: 0")
        self.hint_label.config(text="")
        self.scan_btn.config(state="normal", text="扫描 1 倍速")
        self.confirm_btn.config(state="disabled")

    def _reset_timescale(self):
        self.ts_candidates = []
        self.info_label.config(text="当前状态就点哪个按钮，交替点击缩小范围")
        self.count_label.config(text="候选地址数: 0")
        self.hint_label.config(text="建议：先点1，再暂停点0，反复直到剩1个")
        self._set_ts_buttons_state("normal")


# ============================================================
# 实时数据展示 UI
# ============================================================

class SpeedOverlay:
    def __init__(self, root, reader):
        self.root = root
        self.reader = reader

        self.root.title("Arknights Speed & Pause")
        self.root.geometry("360x160")
        self.root.configure(bg="black")
        self.root.attributes("-topmost", True)

        self.speed_label = tk.Label(
            self.root, text="Speed: --", font=("Consolas", 24, "bold"),
            fg="#FFFF00", bg="black", anchor="w",
        )
        self.speed_label.pack(expand=True, fill="both", padx=15)

        self.pause_label = tk.Label(
            self.root, text="State: --", font=("Consolas", 24, "bold"),
            fg="#00FF00", bg="black", anchor="w",
        )
        self.pause_label.pack(expand=True, fill="both", padx=15)

        self._update()

    def _update(self):
        data = self.reader.get_all()

        speed_name = data.get("speed_name", "未知")
        speed_lvl = data.get("speed_level")
        paused = data.get("is_paused")
        ts = data.get("timescale")

        if speed_lvl is not None:
            color = "#FFFF00" if speed_lvl == SPEED_STANDARD else "#FF8800"
            self.speed_label.config(text=f"Speed: {speed_name}", fg=color)
        else:
            self.speed_label.config(text="Speed: 读取失败", fg="#FF0000")

        if paused is not None:
            if paused:
                self.pause_label.config(text="State: ⏸ 暂停", fg="#FF4444")
            else:
                ts_str = f" ({ts:.2f})" if ts is not None else ""
                self.pause_label.config(text=f"State: ▶ 播放中{ts_str}", fg="#00FF00")
        else:
            self.pause_label.config(text="State: 读取失败", fg="#FF0000")

        self.root.after(10, self._update)


# ============================================================
# 进程等待
# ============================================================

class ProcessWaiter:
    TARGET_PROCESSES = [
        "MuMuVMMHeadless.exe",
        "NemuHeadless.exe",
        "Ld9BoxHeadless.exe",
        "LdBoxHeadless.exe",
        "dnplayer.exe",
        "NoxVMMHeadless.exe",
        "HD-Player.exe",
        "MEmuHeadless.exe",
    ]

    def __init__(self, root):
        self.root = root
        self.root.title("倍速/暂停寻址工具 - 等待模拟器")
        self.root.geometry("350x120")
        self.root.configure(bg="#1E1E1E")
        self.root.attributes("-topmost", True)

        self.label = tk.Label(
            self.root, text="正在监听模拟器进程...",
            fg="#00FFFF", bg="#1E1E1E", font=("Consolas", 14, "bold"),
        )
        self.label.pack(expand=True, fill="both")

        self.dot_count = 0
        self._check_process()

    def _check_process(self):
        self.dot_count = (self.dot_count + 1) % 4
        dots = "." * self.dot_count
        self.label.config(text=f"正在监听模拟器进程{dots}")

        found = None
        for proc in self.TARGET_PROCESSES:
            try:
                pymem.Pymem(proc)
                found = proc
                break
            except Exception:
                pass

        if found:
            self._launch(found)
        else:
            self.root.after(1000, self._check_process)

    def _launch(self, process_name):
        reader = AKSpeedReader(process_name=process_name)
        if not reader.connect():
            messagebox.showerror(
                "连接失败",
                f"挂载 {process_name} 时被系统拒绝。\n请确保程序以管理员权限运行。",
            )
            sys.exit()

        for widget in self.root.winfo_children():
            widget.destroy()
        self.root.attributes("-topmost", False)

        def on_scan_complete(_speed_hex, _ts_hex):
            self.root.attributes("-topmost", True)
            SpeedOverlay(self.root, reader)

        SpeedScannerWizard(self.root, reader, on_scan_complete)


# ============================================================
# 入口
# ============================================================

def main():
    root = tk.Tk()
    ProcessWaiter(root)
    root.mainloop()


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


if __name__ == "__main__":
    if is_admin():
        main()
    else:
        script = os.path.abspath(sys.argv[0])
        params = " ".join(f'"{arg}"' for arg in sys.argv[1:])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
        sys.exit()
