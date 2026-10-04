# tools — V2 验证与历史提取工具

- `verify_v2_baseline.py`：当前 V2 模型验收，覆盖自定义规则集、0-1、检查点续跑和回放。
- `build_level_pack.py`：离线提取工具，读取 V1 数据与解析辅助代码，生成固定 JSON 产物供独立转换使用；不属于 V2 运行路径。
- `scan_unhandled.py`：V1 历史扫描器，仅用于查阅旧结果；其覆盖数字不能证明 V2 能力。

下文保留旧扫描工具的原说明。

- `scan_unhandled.py` — 全 bundle 未实现 buff 节点扫描器。
  用法：`python tools/scan_unhandled.py --ticks 600 --workers 4 [--stride N]`。
  逐关加载跑 N tick，汇总 `buff_node_unhandled`；`--stride 1` = 全部 3864 关。
  多进程共享一份进程级 DataStore，内存平稳。当前扫描结果：0 未实现节点。
