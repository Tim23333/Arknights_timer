# Ark_data — 逆向原始数据

- `dump.cs` — 游戏 IL2CPP 反编译签名（87MB，含全部类/字段/方法定义），
  是逆向战斗逻辑、节点字段、环境系统配置的第一手来源。
- `DummyDll/` — 供静态分析的托管桩程序集。
- `config.json`、`ida.py`、`ghidra.py` 等 — 反编译工具辅助脚本。

模拟器/解析器的字段映射均以本目录 dump.cs 为准。
