# tools — 验证工具

- `scan_unhandled.py` — 全 bundle 未实现 buff 节点扫描器。
  用法：`python tools/scan_unhandled.py --ticks 600 --workers 4 [--stride N]`。
  逐关加载跑 N tick，汇总 `buff_node_unhandled`；`--stride 1` = 全部 3864 关。
  多进程共享一份进程级 DataStore，内存平稳。当前扫描结果：0 未实现节点。
