# -*- coding: utf-8 -*-
import unittest

from tools.timer.process_scan import find_emulator_processes, list_processes


class ProcessScanTests(unittest.TestCase):
    def test_exact_names_take_priority_and_skip_ui_process(self):
        processes = [
            ('MuMuPlayer.exe', 100, r'D:\MuMu9\shell\MuMuPlayer.exe'),
            ('MuMuVMMHeadless.exe', 200,
             r'C:\MuMuVMMVbox\Hypervisor\MuMuVMMHeadless.exe'),
        ]
        found = find_emulator_processes(processes)
        self.assertEqual([name for name, _, _ in found], ['MuMuVMMHeadless.exe'])

    def test_mumu50_nx_device_is_detected(self):
        """MuMu 模拟器12 5.0: 设备进程改为 nx_device 目录下的 MuMuNxDevice.exe。"""
        processes = [
            ('MuMuPlayer.exe', 100, r'E:\MuMu Player 12\shell\MuMuPlayer.exe'),
            ('MuMuNxDevice.exe', 300,
             r'E:\MuMu Player 12\nx_device\12.0\shell\MuMuNxDevice.exe'),
        ]
        found = find_emulator_processes(processes)
        self.assertEqual([name for name, _, _ in found], ['MuMuNxDevice.exe'])

    def test_unknown_future_container_process_matched_by_hints(self):
        """名单外的新进程靠 家族特征(路径含 mumu) + 容器特征(名含 nxdevice) 识别。"""
        processes = [
            ('MuMuNxDevice64.exe', 400,
             r'E:\MuMu Player 12\nx_device\13.0\shell\MuMuNxDevice64.exe'),
        ]
        found = find_emulator_processes(processes)
        self.assertEqual([name for name, _, _ in found], ['MuMuNxDevice64.exe'])

    def test_service_updater_and_unrelated_processes_are_excluded(self):
        processes = [
            ('MuMuVMMSVC.exe', 500, r'C:\MuMuVMMVbox\Hypervisor\MuMuVMMSVC.exe'),
            ('MuMuPlayerUpdater.exe', 600, r'D:\MuMu9\shell\MuMuPlayerUpdater.exe'),
            ('chrome.exe', 700, r'C:\chrome.exe'),
        ]
        self.assertEqual(find_emulator_processes(processes), [])

    def test_list_processes_smoke(self):
        names = [name.lower() for name, _, _ in list_processes()]
        self.assertTrue(any('python' in name for name in names))


if __name__ == '__main__':
    unittest.main()
