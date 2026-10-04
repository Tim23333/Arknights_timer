# Campaign runner 独立交叉复核

2026-10-02，复核对象为 `tools/campaign_progress.py`、其进度测试和四组独立完整性复现。
本轮只读检查 root 工具及 V2 源码，运行已有测试，并新增本报告。
没有批准转换收据，没有生成正式关卡内容，没有提升十二人可运行状态或主线胜利状态。

复核结论：此前四组问题的原始复现现已被拒绝或通过持久性门。
独立 integrity 14项加既有 progress 5项，收尾重跑 **19/19通过，0.53秒**。
当前runner字节SHA-256：`02acccc8f74bb1ffe6dfc082e56b40baa9276fa98c4f3dd5b70b97b03ec02bd6`。
独立integrity测试SHA-256：`cb4dfdf8bfda1034750d333ae090fa42b93c74de694abe0e6ad48f34c7e72bef`。
运行命令为：

```powershell
..\.venv\Scripts\python.exe -m pytest tests_v2/test_campaign_runner_integrity.py tests_v2/test_campaign_progress.py -q
```

| 原问题 | 本轮检查和实测 | 结论 |
|---|---|---|
| 固定配置未锁定 | 等级、精英阶段、专精/技能索引、信赖、潜能、装备六组漂移保持frozen不变，全部抛ValueError | 原复现拒绝；完整roster与profile身份另进入case input identity |
| 原始来源和解析器失效未降级 | 不存在binary、错误binary/helper/FB helper/extractor哈希五组均降stale；正常核心数据还重新canonical_core对照 | 原复现拒绝，结果不再只相信record中的core_exact_equal布尔值 |
| 假metadata能运行 | 实际Compiler仍可编译十二个假单位/技能和35个假敌人，但run_case先要求外部独立receipt；不存在receipt时抛ValueError | 包内native标记与passed自述不能替代外部review批准 |
| 单一progress覆盖证据/整批才保存 | 独立save_case_result保存完整replay；原子提交中断保留旧文件字节；dryrefresh保留历史引用，旧program/runtime/input不作为当前passed | 原复现通过；每case执行后保存结果，不再只把replay内嵌唯一总报告 |

只读核对的关键入口：

- `fixed_roster`（campaign_progress.py:23）：强制E2/70/M3/潜一/信赖100/无装备，并核对frozen字节身份。
- `audit_recovery`（:41）：核对output、binary与三个解析工具身份，reference字节及canonical_core实际比较。
- `atomic_json`（:112）、`save_case_result`（:129）：同目录临时文件写完并fsync后os.replace；旧结果归档，当前结果独立于progress保存。
- `case_inputs`（:144）、`review_gate`（:155）：外部收据绑定content、commands、完整roster、profile、V2实现和native来源；核对review检查、执行测试artifact和测试源码身份。
- `run_case`（:190）：先过外部receipt门，再编译和执行；胜利、出生守恒、无非法命令、检查点续跑及回放分别检查。
- 历史复用（:276）：只有当前输入/review相符、原模型状态与续跑/回放通过时才尝试复用；再用当前Compiler与Engine核对program/runtime身份。
- `main`（:338）：进度manifest也采用原子写入。

外部review receipt是独立审查产物，其可信内容仍须由实际复核过程生成。
本报告仅证明“无receipt的包内假声明不可执行”以及已有拒绝/持久性门，不证明尚不存在的
approved receipt所涵盖的十二人属性、技能、天赋或任何原生关卡行为已正确。
不以构造自签receipt、任意passed JSON或测试引用字符串充当未来转换验收。

当前重新构建的只读库存计数为36目标、36解码、36核心参考对照通过，
**正式V2内容0、模型通过0、accepted0、client verified0**。
来源核心对照仍不能代替完整根字段/预定义/控制/敌人/技能的转换与执行验收。
0-1旧或新模型证据是独立基线，不替代这三十六关；本次19项runner测试也不验证0-1模型。

收尾时已修复低优先级状态显示细节：dryrefresh成功复用相符模型证据后，不再把case.status覆盖为
awaiting_execution_gate，保留与model_status一致的passed_pending_review显示。
上述当前SHA和19项重跑结果对应这次两行显示修复后的runner；没有新增功能或扩大审阅范围。
