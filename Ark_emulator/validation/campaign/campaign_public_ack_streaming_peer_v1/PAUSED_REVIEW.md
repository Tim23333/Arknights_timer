# ACK V3 独立审阅暂停交接

2026-10-07 用户明确暂停后，仅整理已读源码结论。本 agent 没有启动 ACK V3 实际场景、没有写验证实现、没有提交或推送；Root 负责最终统一提交。该审阅 **未完成、未批准、没有独立 actual proof**。

读过的固定文件：

- `tools/control_driver/public_ack_v2.py`：SHA256 `004eb515760db4887edb83554eb2964a238403e94277acb04f96cd318c9ba107`。
- `tools/control_driver/public_ack_v3.py`：SHA256 `113fbadc4edaeb3583acbcc176475507b1d3f5e238aee49c88bc541f62209a0c`。
- `ark_sim/kernel/events.py` 的 `iter_records`：锁内构造 `tuple(self._records[start:])`，磁盘后端会读取并物化整段记录。
- Session 的共享 RLock、API 的公开 submit/command ledger 路径；没有修改这些源码。

静态已看到的保持项：V3 POLICY 仍是 `external_dialogue_observation_plus_one_tick/v2`；ACK 仍来自实际 `control.awaiting_ack` 的 event/control/step，执行时刻仍是实际 submit 时刻+1；恢复仍要求 policy/program/runtime/time、完整 cursor、实际 awaits 与提交 ledger/公开 replay 命令严格对应；没有将控制换成 immediate/noop。新 records 用实际拥有的 `_records[index]`，持 Session 锁并拒绝 advancing/atomic boundary，避免旧整段 list/tuple 物化。恢复只保留 awaits，observe 逐条读取，checkpoint 用长度核边界。

尚未实际验证的关键边界：

1. **读取异常的提交边界可能不同。** V2 observe 先完成全段读取/list，再提交任何 ACK。V3 可在读取前部 await 后立即公开 submit 并增加 ledger，再因后面的磁盘读取/hash 校验异常退出；这样异常前可能已有部分 ACK 副作用，cursor 却尚未更新，重试还可能触发 duplicate observed event。此为直接源码推导，尚未构造真实 disk counter，不能当作实际反例或宣布完整等价。
2. **并发闭边界未证。** records 生成器结束时释放锁，observe 最后 `cursor=len(...)` 在该锁之外；checkpoint 以及恢复的部分 len/time 读取也不在同一锁域。若另一个线程在这两个操作之间追加/advance，可能把未观察记录计入 cursor。V2 也存在分阶段读取间隙，不能据此断言 V3 独有回归。普通串行 idle 场景需要独立实际证据，跨线程契约需要另外界定。
3. **初始化校验时机不同。** V2 即使 state=None 也先读完已有 events；V3 state=None 不读 journal，验证会延后到 observe。损坏 journal 的构造/observe 异常时机尚未验证。
4. `_advancing`/`_atomic_depth` 拒门、bool/float cursor/step 等、missing/duplicate ACK ledger、program/runtime/time 和公开 command tamper、no-whole-iteration spy、完整 disk CP/head/driver state 尚未跑独立门。

恢复工作时应先核两文件是否仍为上述字节，读取 Root 新冻结/author evidence；如有修订须分版本。可先用自有很短 control scene，真实 disk journal + E lease/cleanup，分别验证 V2/V3 正向行为、故障前后公开命令与 driver 状态。读取异常是否保持原事务边界、并发是否属于授权契约，应明确处理；不要把 Root 的作者 actual 当成本 agent 独立通过。暂停期间不继续这些工作。
