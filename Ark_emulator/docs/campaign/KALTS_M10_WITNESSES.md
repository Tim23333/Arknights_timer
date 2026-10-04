# 凯尔希15项M10完整重验

本批只新增 `tools/export_canonical_kalts_candidate.py`、本说明与新证据。冻结的15项场景、独立预期、原f8失败、前21项、Night13及Weedy10都没有修改或重标。

运行对象为独立candidate root `D:/Arknights/Arknights_timer/unpack_work/campaign_m10_cast_freeze_candidate`，实现digest `f6bb448edc40641f55550f7188b412f57e68a56fa083ac4f4c1c24e30502328e`；综合输入 `level_main_00-10.m10.json` SHA `2b7fe8d63a30765614a63a9914b6c3a59248600663f85972527491390bd44de8`。bootstrap在primary helper前实际导入candidate ark_sim，并核api.__file__，primary f8未改。

全部15项 **15 passed in178.05s**，`validation/campaign/canonical_kalts_witness.m10_f6bb.json` 的 `identity_stable=true`，input/source/core/test/helper开始与结束相等，所有测试/helper文件当前SHA与证据一致。证据SHA `d947ced6fb1e225950e91199e7a6a63cb67cccef49208f1fde0bc68e43d73d1b`，导出工具SHA `44d2fa293418f9a3884a472397f5e5623b7b0196bdbed416198c630bcf7c306f`。

| 已执行组 | 独立预期与实际见证 |
|---|---|
| fixed source/config | E270/pot1/trust100/M3/noEquip；hostHP1996/ATK468，Mon5177/1345/389/block3；native token10002、不发明token skill ID，exact normal7/S320帧 |
| deploy/capacity/payload | battleDP10、paid_cost10、owner ref；第二只/容量不足/payload缺失失败完整原子回滚 |
| source/owned SP门 | foreign不能启动自己S3；无token不回SP、live host失token后清0；只取消具体S3而ordinary heal继续 |
| normal/S3时钟与衰减 | normal tick7对DEF100物伤1245；t8激活S3保留next_attack60，f20在80true，1345×(1+2.6×(1−72/600))；host付15/token mode1 |
| self/own/foreign治疗 | self14tick468；两Mon同时伤口，own20tick468优于更低HP的foreign；own满血fallback foreign27tick468 |
| native death/withdraw | Mon死亡实际source1200 true与3秒stun；withdraw不触发该爆炸，CD25拒立即再放；owner退场清理token |
| skill结束/kill marker | 20秒无自己击杀时损失.5×5177=2588.5并还原mode/mark；自己击杀清mark、结束HP5177不处罚 |

上述刺激仅来自固定场景初态及实际commands；rawcases保存program/runtime身份、完整输入命令、场景初态、source/target/owner IDs、实体HP/SP、score/伤害/治疗/死亡/中断事件、RNG及完整snapshot的checkpoint/restore和命令replay一致。没有把ctx直接写入当可回放命令，没有用stub simulator或空handler。

证据采用 `ark-sim/campaign-mechanism-test-evidence/v1` 的真实 `passed`、`implementation_sha256`、`tests[]` sourceSHA/result字段，可供外部review引用，仍为 `review_receipt=false, formal_approval=false`。不是完整stage、fullOperator或fullNative签收。

未测的other-unit kill marker和出host治疗范围DEF归零独立边界仍在证据 `untested_boundaries` 中；不能用旧prototype升级。外部2025token与本地2026版本对应、native FSM/动画缩放、治疗字段64比较器正文继续client_pending。当前15项范围内未发现新的实际模型阻断。

```powershell
..\.venv\Scripts\python.exe tools/export_canonical_kalts_candidate.py
```

以后c0或任何新candidate身份可复用这些冻结场景，显式传 `--candidate-root`、`--expected-digest`、`--package`、**新的** `--output` 后重新执行。不得改本f6bb evidence身份或把旧通过迁移过去。
