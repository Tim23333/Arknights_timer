# M23 / M25 / M26 独立边界复核

本次只新增 `tools/experiments/m26_peer/test_peer.py`、`verify.py` 和独立报告；没有修改三个候选、作者测试、正式输入、primary 或旧证据。所有场景由 peer 独立构造，数值预期为明确的 ATK12 / HP100 / 部署费用2 / 0.1秒半开持续时间，未引用作者 actual 或 expected 函数。

| 实际导入根 | 核心身份 | 实跑范围 |
|---|---|---|
| campaign_m23_roster_candidate | 0258f171d31daffb7b917e2ebad2603505e5fa762e99ef4a71b3b30342d62381 | 4项部署成员边界 |
| campaign_m25_eligibility_candidate | 281dc1fc3fc35e83adad37146b2bfb16afa92c5086f29fc22e881f116eb80ace | 2项独立资格端点 |
| campaign_m26_decision_eligibility_candidate | 7aa11610867291a2274d31a7ae2ec69fb8acc03e808314a8cde29fdedd88aabe | 12项组合边界 |

M23 的显式空编队和仅含 source 的编队都拒绝复制非成员 dormant target，原注册实例和 DP10 不变；省略编队的开放创作路径实际部署成功，DP10→8；不在公开编队中的 owned spawn 仍实际生成，所有权绑定 source。四项均 checkpoint continuation 和记录命令回放相等。M23夹具明确去除其尚不支持的 selection_state / selection_flags，仅检查成员门和 owned consumer，不声称执行后来的 M25 字段。

M25 独立端点显示：公开命令在 tick0 施加 target-free Buff，tick1 发射被排除，tick3（0.1秒）到期后真实12点伤害；heal_free 对普通攻击资格不变，对 healing ability context 则拒绝。纯资格调用前后完整 checkpoint 不变。两项含 CP 和完整 recorded-command replay，未调用作者 helper。

M26 同一真实资格 consumer 已在 eligible 和 select 两边接入。target-free 存续的前三 tick，enemy 每 tick 移动0.1且无伤害；tick3 到期后停在 col0.3 并实际造成12点伤害。几何范围之外但资格合法的目标不会使敌人停移。自定义纯 qualification rule 返回拒绝时也不会开火；零可用目标时 eligible 不写事件/状态、不耗 RNG。资格规则异常在 session.atomic 中完整回滚。未声明新 eligibility 的旧定义仍按原模型攻击，不由新状态隐式改变许可。

验证工具实际重读 source audit 的5个 AdvancedSelector 对应 Unity Typetree，逐项比较原始 raw 字段和资产 SHA。每个 fixture 在 decode / compile 前记录实际序列化 bytes SHA、初态、显式 seed2603；实际 ark_sim module path 和 implementation digest 检查，helper / source / runtime 的前后锁相等。报告不改变原报告输入身份，也不把未运行的 stage 包登记为已执行。

报告：

- `validation/campaign/m23_peer/final.json` SHA `adce58faf927f4d67d8ea3da65da969e3ba86bd92e71b747f020a57aef983e28`。
- `validation/campaign/m25_peer/final.json` SHA `1621a96010599ab7c4292c3a53403e7c1a35e442e1cde53ededdae8dd183453a`。
- `validation/campaign/m26_peer/final.json` SHA `17d3c590c0ae00e28d5d1449bb3ec961ee1a6940dab63efb2a38ee68b9a15b91`。

初次开放部署正对照删除全部 initial actor 后，目标定义被编译依赖裁剪，实际拒绝 unknown definition；修正为有来源引用的 dormant initial actor。owned spawn 最初把参数放到 effect 根而被 schema 拒绝，随后 public skill 的位置误放到 payload 外而失败，最终按实际接口修正。新增 standalone packet 最初使用持续0.1秒 cast，在 tick1→tick3 的再次施放仍忙；最终采用独立即时 on_start probe 来检查半开资格，而不改变 canonical ability 或冻结 core。这些是本次夹具构造修正，没有实现差异或测试预期放宽。

当前声明范围内无新阻断。这里只证明通用边界和 M26 wiring，未审签 M23 原生12卡完整养成数据、原生教学战斗、M25 native getter/comparator 方法体或任何完整阶段。source-relative side、默认 typed state、INPUT_TARGET 继承转交与原生 permission 算法仍为方法体/客户端证据缺口。固定12/36目标以及实际游戏中间数据正确要求不变；没有 formal receipt、promotion 或实际游戏正确性声明。
