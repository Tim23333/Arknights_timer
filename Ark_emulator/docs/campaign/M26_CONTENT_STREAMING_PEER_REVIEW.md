# M26 第1章内容与流式证据独立复核

本批只新增peer工具、测试与报告，未修改候选core、Root builder、旧包、运行脚本或live进程。实际运行根为campaign_m26_decision_eligibility_candidate，core `7aa11610867291a2274d31a7ae2ec69fb8acc03e808314a8cde29fdedd88aabe`。

最终内容输入是Root明确修订后的1-11 SHA `a1a8a9091da743d0cbf966e2d44f521488f64d5dbd6d6bfe153f452d7431e215`，1-12 SHA `a68023a0ec81cc95df9ccdec452979f5131fda648dc6673b8a3e9110108e38a1`。peer读文件前核SHA，再decode，记录实际fixture字节/初态/seed2604。旧无教学overlay的3e5/5915首轮六项通过、三项peer夹具错误，未迁移为新版通过；其后hash门实际拒绝变更包，未执行新身份。Root已保存旧history包，本peer报告记录这些历史边界。

## 内容端点与闭包

新9项独立测试fresh通过24.68秒。76项源/helper/input前后锁和core前后相等，真实重读W prefab全部组件及NPC Character Typetree；实际模块路径验证，没有从metadata推断候选路径执行。

- 飞行player目标，selection motion2，C4原显式selector motion3允许，普通motion1拒绝。真实C4自动支付/发射，在tick114爆炸，W ATK470×1.8、DEF0实际846；没有普通攻击事件。CP和完整recorded-command replay相等。
- 把外观player标签与selection.side1或category2组合，真实C4不启动、不发射、不伤害。这证明相对side/类别规则由actual state consumer使用，未仅凭tag放行。
- 更近的FLY目标距1、WALK目标距2时，普通攻击仍选WALK。源f9/f23、弹速5、距2需12 motion ticks，实际tick21/35各470；FLY HP不变。首轮我误沿用距1的第二落点29，按冻结源和明确profile算术更正为35，未改内容或core。
- 两包完整Compiler闭包通过，普通四个选择器的region/filter/order与M22原输入逐字段一致（新增资格和metadata单独剔除，空metadata与absent归一仅用于非执行字段比较）。
- 每actor运行state等于其显式math policy与sparse source patch的合并，两个集合不重叠。全部actual_client_verified=false；native FSM gap仍保留。NPC使用实际E0L20来源Character motion0→WALK mask1、SNIPER→profession2，不取固定十二人E270。1-11保留M23 fixed12_test_override、12个公开roster成员且不含预定义NPC。

报告 `validation/campaign/m26_content_peer/final.json` SHA `a048a6e8f8a513314c42727a05ef390fa3ba6dde2b29932dd45f9f1947a08f3e`；6个实际运行fixture，另外是静态闭包/source及canonical字节case。不会把9项说成两个整阶段执行。

source literal patch源于serialized字段/枚举，不自动证明live getter/状态写入时机。未知side/category/unit_type/status仍明确数学策略和clientFalse。sourcerelative side、normal/C4 INPUT_TARGET继承、SecondaryFilter comparator、版本对应、native permission方法体均未取得，实际游戏准确性缺口不能由微场景通过清除。

## Canonical stream与continuation

实际有伤害/弹体的simulation，stream observations.snapshot与既有完整Simulation.snapshot digest一致，events与完整事件列表digest一致。完整JSONL重读每项与immutable journal逐值相等，ID连续，计数与文件SHA一致。嵌套operand、Unicode、负零、None/bool/float及换行引号未丢。提交未来command不改当前snapshot，却改变包含scheduler/random/world的continuation_state；真实CP续跑两者observations相等。

这些结果只验证canonical值和continuation输入，不支持把5000events合成benchmark当真实整关内存改善或实际游戏正确证据。

## 旧runner真实身份漏洞与v2修复复核

旧runner分别SHA读取和decode读取。独立 `probe_stream_input_identity.py` 只用process-local Path.read_bytes替身模拟文件替换：磁盘seed71，SHA读取71，实际decode读取seed72，再末尾读回71。旧runner真实完成2leak、CP/replay相等，却reported passed=true/identity_stable=true，package SHA指71而program和reportedseed为72。

该反例保存于 `validation/campaign/m26_content_peer/stream_input_identity/`，包括原/实际fixture、完整runner报告/journal/checkpoint/replay、counterexample和旧runner source副本。旧source SHA `b789ac37fa597978f91dd6b1d7a15cb467cebfc88be6ef0573d9689aef330887`，未覆写旧工具或live来源。

Root新增 `run_campaign_streaming_runthrough_v2.py` 后，peer五个独立case实跑全部满足原期望：

1. 原seed71/原commands正常两leak、life99997、CP/replay/journal完整，passed/identity均true。
2. 同旧第二次读取换包攻击现只影响end检查，identity/pass均false。
3. actual decode第一次返回seed72时，报告package SHA和decoded_input_sha真实绑定72，program亦是72；末尾磁盘71使identity/pass false。
4. commands actual decode字节变更同样记录真实commands SHA，并因末尾漂移拒绝。
5. helper末尾字节变化使identity/pass false。

四个拒绝case均保存完整报告、journal、replay和CP结果，exit1，未仅抛出异常丢失证据。全部case core/runner/helper/peer真实字节前后相等；漂移是独立process-local read injection，原盘文件未修改。

v2报告 `validation/campaign/m26_content_peer/stream_v2/final.json` SHA `0a5f843e3286276156dc8ac0b11f9d98efd2fb89bb8033870f974e561b70ab6f`。此报告不重标旧runner证据、不证明完整1-11/1-12、不签promotion或formal/native receipt。当前新v2输入绑定范围内未发现进一步阻断。
