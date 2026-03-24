import tkinter as tk
from tkinter import messagebox
import struct
import pymem
import pymem.memory
import pymem.exception
import concurrent.futures
import threading
import os
import sys
import ctypes


class LiveRNGTracker:
    def __init__(self, root):
        self.root = root
        self.root.title("真理之眼 - 实时 RNG 预测")
        self.root.geometry("400x180")
        self.root.configure(bg="#0D0D0D")
        self.root.attributes("-topmost", True)

        # 内存寻址相关状态
        self.pm = None
        self.array_base = 0
        self.inext_addr = 0
        self.inextp_addr = 0
        self.is_tracking = False

        self.last_inext = -1
        self.total_calls = 0

        # UI 布局
        self.status_label = tk.Label(self.root, text="状态: 等待骇入", fg="#FFaa00", bg="#0D0D0D",
                                     font=("Consolas", 12, "bold"))
        self.status_label.pack(pady=5)

        self.cursor_label = tk.Label(self.root, text="当前游标 (inext): --", fg="#AAAAAA", bg="#0D0D0D",
                                     font=("Consolas", 14))
        self.cursor_label.pack(fill="x", padx=10)

        self.next_val_label = tk.Label(self.root, text="下一次判定: 0.000000", fg="#00FF00", bg="#0D0D0D",
                                       font=("Consolas", 18, "bold"))
        self.next_val_label.pack(fill="x", padx=10, pady=5)

        self.hint_label = tk.Label(self.root, text="预测: --", fg="#00FFFF", bg="#0D0D0D", font=("Consolas", 12))
        self.hint_label.pack(fill="x", padx=10)

        self.hack_btn = tk.Button(self.root, text="锁定战场 RNG 核心", command=self.start_hack_thread, bg="#333333",
                                  fg="white", font=("Consolas", 10, "bold"))
        self.hack_btn.pack(pady=5)

        self.target_processes = [
            "MuMuVMMHeadless.exe", "NemuHeadless.exe", "Ld9BoxHeadless.exe",
            "LdBoxHeadless.exe", "dnplayer.exe", "NoxVMMHeadless.exe",
            "HD-Player.exe", "MEmuHeadless.exe"
        ]

    def start_hack_thread(self):
        """开启后台线程进行内存扫描，防止 UI 卡死"""
        self.hack_btn.config(state="disabled", text="骇入中 (扫描物理内存)...")
        self.status_label.config(text="状态: 正在全盘搜索特征码...", fg="#00FFFF")
        self.is_tracking = False
        threading.Thread(target=self.hack_memory_routine, daemon=True).start()

    def hack_memory_routine(self):
        found_process = None
        for proc in self.target_processes:
            try:
                self.pm = pymem.Pymem(proc)
                found_process = proc
                break
            except Exception:
                continue

        if not found_process:
            self.root.after(0, self.hack_failed, "未找到模拟器进程，请确游戏运行中。")
            return

        try:
            # 1. 获取所有内存块
            pid = self.pm.process_id
            regions = []
            curr = 0
            while True:
                try:
                    mbi = pymem.memory.virtual_query(self.pm.process_handle, curr)
                    curr += mbi.RegionSize
                    if mbi.State == 0x1000 and (mbi.Protect & 0x66) and mbi.RegionSize >= 1024:
                        regions.append((mbi.BaseAddress, mbi.RegionSize))
                except Exception:
                    break

            # 2. 并发寻找 SeedArray 特征码 (Length=56, vector[0]=0)
            signature = struct.pack('<qi', 56, 0)
            candidate_arrays = []

            def scan_array(base, size):
                try:
                    data = self.pm.read_bytes(base, size)
                    import re
                    pattern = re.compile(re.escape(signature))
                    res = []
                    for match in pattern.finditer(data):
                        # 检查对齐和种子合法性
                        addr = base + match.start()
                        if addr % 8 != 0: continue
                        seeds_data = data[match.start() + 12: match.start() + 12 + 220]
                        if len(seeds_data) < 220: continue
                        seeds = struct.unpack('<55i', seeds_data)
                        if any(s < 0 or s >= 2147483647 for s in seeds): continue
                        if sum(1 for s in seeds if s == 0) > 1: continue
                        res.append(addr - 0x18)
                    return res
                except:
                    return []

            with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
                futures = [executor.submit(scan_array, base, size) for base, size in regions]
                for future in concurrent.futures.as_completed(futures):
                    res = future.result()
                    if res: candidate_arrays.extend(res)

            if not candidate_arrays:
                self.root.after(0, self.hack_failed, "未找到 RNG 核心数组，请在干员攻击后重试。")
                return

            # 3. 邻域爆破：在数组周围寻找 inext 游标
            target_locked = False
            for arr_base in candidate_arrays:
                search_start = max(0, arr_base - 1024)
                try:
                    surroundings = self.pm.read_bytes(search_start, 2048)
                    for offset in range(0, 2048 - 8, 4):
                        inext, inextp = struct.unpack('<ii', surroundings[offset:offset + 8])
                        if 0 <= inext <= 56 and 0 <= inextp <= 56:
                            diff = inextp - inext
                            if diff == 21 or diff == -34:
                                self.array_base = arr_base
                                self.inext_addr = search_start + offset
                                self.inextp_addr = search_start + offset + 4
                                target_locked = True
                                break
                except:
                    pass
                if target_locked: break

            if target_locked:
                self.root.after(0, self.hack_success)
            else:
                self.root.after(0, self.hack_failed, "找到数组，但未锁定游标，可能被GC回收。")

        except Exception as e:
            self.root.after(0, self.hack_failed, f"扫描崩溃: {str(e)}")

    def hack_failed(self, msg):
        self.status_label.config(text="状态: 骇入失败", fg="#FF0000")
        messagebox.showwarning("警告", msg)
        self.hack_btn.config(state="normal", text="重试骇入")

    def hack_success(self):
        self.status_label.config(text="状态: RNG 引擎已接管", fg="#00FF00")
        self.hack_btn.pack_forget()
        self.total_calls = 0
        self.is_tracking = True
        self.update_live_data()

    def update_live_data(self):
        if not self.is_tracking: return

        try:
            # 实时读取内存中的当前游标
            curr_inext = self.pm.read_int(self.inext_addr)
            curr_inextp = self.pm.read_int(self.inextp_addr)

            # 如果游标变动，说明游戏刚刚调用了一次随机数
            if curr_inext != self.last_inext:
                if self.last_inext != -1:
                    self.total_calls += 1
                self.last_inext = curr_inext

                # 更新当前游标 UI
                self.cursor_label.config(text=f"底层游标: {curr_inext:02d} (本局共消耗: {self.total_calls})")

                # ==== 核心黑科技：直接根据物理定律预测下一次输出 ====
                # 计算下一次引擎调用时的游标位置
                next_i = curr_inext + 1
                if next_i >= 56: next_i = 1

                next_ip = curr_inextp + 1
                if next_ip >= 56: next_ip = 1

                # 瞬间跨维度读取游戏内存里 SeedArray 的原始种子
                seed_i = self.pm.read_int(self.array_base + 0x20 + next_i * 4)
                seed_ip = self.pm.read_int(self.array_base + 0x20 + next_ip * 4)

                # 运用 Knuth 减法复刻判定过程
                MBIG = 2147483647
                ret_val = seed_i - seed_ip
                if ret_val == MBIG: ret_val -= 1
                if ret_val < 0: ret_val += MBIG

                next_float = ret_val * (1.0 / MBIG)

                # 刷新 UI 数据
                self.next_val_label.config(text=f"下一发: {next_float:.6f}")

                # 战术辅助判定 (以 20% 暴击 / 闪避为例)
                if next_float < 0.2:
                    self.hint_label.config(text="战术预测: \033[91m极高概率触发 (≤20%)\033[0m", fg="#FF4444")
                    self.next_val_label.config(fg="#FF4444")
                elif next_float < 0.5:
                    self.hint_label.config(text="战术预测: 可能触发 (≤50%)", fg="#FFFF00")
                    self.next_val_label.config(fg="#FFFF00")
                else:
                    self.hint_label.config(text="战术预测: 普通攻击 (安全区)", fg="#00FF00")
                    self.next_val_label.config(fg="#00FF00")

        except Exception:
            self.is_tracking = False
            self.status_label.config(text="状态: 内存连接丢失 (游戏结束或关闭)", fg="#FF0000")
            self.hack_btn.pack(pady=5)
            self.hack_btn.config(state="normal", text="重新骇入")
            return

        # 10 毫秒高频超静默轮询
        self.root.after(10, self.update_live_data)


# ================= 权限提权核心模块 =================
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


if __name__ == "__main__":
    if is_admin():
        root = tk.Tk()
        app = LiveRNGTracker(root)
        root.mainloop()
    else:
        script = os.path.abspath(sys.argv[0])
        params = ' '.join([f'"{arg}"' for arg in sys.argv[1:]])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script}" {params}', None, 1)
        sys.exit()