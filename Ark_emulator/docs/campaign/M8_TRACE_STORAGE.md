# M8 事件与trace内部存储共享

本轮仅改 `ark_sim/kernel/events.py` 和 `ark_sim/domains/context.py` 的trace存储相关代码，保留root并行添加的timeline属性。没有改API、schema、生命周期、移动、资源、编译器、M6内容或M7测试。旧探索66701继续其已加载实现，本轮结果不替旧证据重标身份。

## 观察合同与实现

默认event JSON没有新增/删除字段，事件顺序、id、cause、time、随机样本和所有现有操作数保持逐项值相等。compact仍按原规则剔除snapshot键并把context角色缩为ID；没有进一步删减inputs或数值证据。full trace也保留完整数据。内部存储记为M8 immutable-DAG策略，外部trace representation无需新版本字段；源码implementation身份仍变化，因此checkpoint/replay必须使用新身份。

`compact_trace` 使用单次DAG memo与copy-on-change：未发生删改的FrozenMapping/FrozenTuple路径直接保留；重复alias只转换一次，需要剔除snapshot/context的路径生成新冻结节点。计算trace的full路径与value不再先thaw成整棵可变树，仅在实际返回调用者时仍thaw结果，隔离语义不变。

`EventLog.emit` 用严格JSON校验与memo冻结替代整棵JSON clone→再次freeze。mutable节点复制为独立immutable数据，已经冻结且所有子项合法的节点复用，重复输入alias共享。没有跨emit缓存或全局intern池，不增加需要回滚的cache；原子操作仍按原journal容器/长度/next ID截断恢复。

FrozenMapping公开构造器本身并不保证JSON合法。本实现对其键与全部子项同样验证，拒绝非str键、NaN/Inf、非JSON对象与循环。对子类使用基类descriptor读取str/int/float真实底值，避免重载转换方法改变旧JSON encoder的语义；字符串键同样处理。共享并不是强安全边界，不承诺抵抗绕过Python对象协议的强制修改。

snapshot仍返回原有plain dict/list JSON结构，可独立修改；restore先验证并冻结其全部数据，再校验连续ID、时间与cause约束，然后替换journal。未改变检查点格式。

## 实际验证

新 `tests_v2/test_m8_trace_storage.py` 18例，与已有kernel/engine组合共 **84 passed in 5.59s**：

- mutable输入之后修改不影响journal；immutable同次alias及跨事件同一合法子树保持身份共享。
- snapshot/restore独立且事件值完整，写入只读视图失败；原子失败截断事件并恢复id/cause分配。
- 非str键/非finite/非JSON对象，无论普通输入或Frozen包装均拒绝且不消耗event id。
- 循环拒绝；公开Frozen对象中强制塞入mutable子项会复制脱离，强制塞cycle会拒绝。
- 底值3但转换返回999的int/float子类、底值abc但转换返回different的str及key，ordinary/Frozen两种输入均与旧JSON行为相等。
- 同一真实Compiler程序、同V2算法，分别使用旧storage参考与新storage执行真实随机分支和伤害；compact/full两种trace政策的完整事件、快照逐项值相等。
- 新storage真实checkpoint恢复、输入回放、全部事件和随机状态一致。

旧storage参考 `tools/m8_trace_legacy_reference.py` 只保存旧compactor和旧EventLog.emit算法，不是V1战斗runtime，也不伪装为旧源码运行身份。数值与调度均由当前真实V2执行。

## 小段性能对照

`tools/benchmark_m8_trace_storage.py` 在独立进程使用同冻结0-10输入、seed953816614；只切换storage参考，保持同算法。逐项事件JSON按稳定key顺序流式计算SHA，state及输入身份一致，没有用事件数量相同代替值比较。

| 样本 | legacy | current | 解释 |
|---|---:|---:|---|
| 最终30帧事件数 | 1,655 | 1,655 | 完整事件SHA相同 |
| 最终30帧unique容器 | 53,346 | 40,130 | 减少24.8% |
| 最终30帧RSS | 54.61MB | 41.64MB | 约减少23.7% |
| 最终30帧private commit | 46.57MB | 33.37MB | 约减少28.4% |
| 最终30帧运行时间 | 2.31s | 2.33s | 接近，不声称速度改进 |
| 含Myrtle真实S2的300帧事件 | 21,536 | 21,536 | 完整事件SHA相同 |
| 300帧unique容器 | 734,570 | 564,051 | 减少23.2% |
| 300帧RSS | 358.07MB | 189.15MB | 约减少47.2% |
| 300帧private commit | 350.38MB | 180.62MB | 约减少48.5% |
| 300帧运行时间 | 29.78s | 28.75s | 单次样本，不能推广速度收益 |

30帧全值SHA：`e9047beb701ee0d081a4d79074ac4223045deaaa89aeac02244db815d333c9c5`；300帧全值SHA：`0c59853ff6032526ad0654e73f8c56be3d75a0c2758830e9b64715fdcc7f2790`。

300帧的`m8_trace_*_final_300.json`捕获于最后标量子类边界修订前，保持其真实runtime身份，不重标。修订不改变这些标准内置scalar样本的事件值；当前最终源码的30帧重新比较及完整新测试均过。完整4500帧与三路恢复的实际峰值仍由root独立运行，不能用prefix的47%宣称22GB问题全部解决。

## 身份与命令

```powershell
..\.venv\Scripts\python.exe -m pytest tests_v2/test_m8_trace_storage.py tests_v2/test_kernel.py tests_v2/test_engine.py -q
..\.venv\Scripts\python.exe tools/benchmark_m8_trace_storage.py --storage legacy --ticks 30 --output validation/campaign/m8_trace_legacy_final_30.json
..\.venv\Scripts\python.exe tools/benchmark_m8_trace_storage.py --storage current --ticks 30 --output validation/campaign/m8_trace_current_final_30.json
```

| 冻结文件 | SHA256 |
|---|---|
| ark_sim/kernel/events.py | 734720f3b0f8101e38319ba29b4deb516fc59037e19605af6eebd83a10726094 |
| ark_sim/domains/context.py | d8647ff099097885dfbcdca49c8e56a1234ab83efc9f9d20a39bd2b8a3359739 |
| tests_v2/test_m8_trace_storage.py | 29ec8bd73494a0dc7cdff2c8a267867623bbe086c1cf0d298c75dd2dbe332323 |
| tools/benchmark_m8_trace_storage.py | 5d9f4c314a576815c7e535526c757a4534423c587360c42a2c47e211d88700da |
| tools/m8_trace_legacy_reference.py | eb28111ede37b20eb1f29a9e34e44c30b5e2dcf58528f48575d5a5e3dc69cede |

root的顺序释放验证sim/restore/replay工具改动是另外一项峰值优化，本报告不计其收益。模型存储验证也不提供native客户端审批或formal主线通过。
