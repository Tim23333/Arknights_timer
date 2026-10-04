# 中途轨迹导出与比较入口

当前工具纯离线运行，不连接设备。标准化客户端轨迹的实际采集与字段适配尚未完成；仓库中的示例expected明确为synthetic测试预期。

## 模型导出

模型侧入口 `tools/export_campaign_model_trace.py` 接收明确runtime/core、包、命令与导出计划。计划包含schema `ark-sim/model-trace-export-plan/v1`、两个输入SHA、seed、comparison_identity、model_frames及fields。身份中content_identity必须等于实际program fingerprint。

字段读取类型如下：

| kind | 必需参数 | 结果 |
|---|---|---|
| entity_component | entity实例引用、path组件键序列 | 当前World深只读视图的实际值，缺路径报错 |
| resource | entity、resource | 实际当前资源值 |
| battle_state | path | 当前系统状态值，缺路径报错 |
| random_state | 无 | 完整模型随机状态，不能冒充原生RNG状态 |

以真实小场景为例，已执行：

```powershell
..\.venv\Scripts\python.exe tools/export_campaign_model_trace.py `
  --runtime-root ..\unpack_work\campaign_m26_decision_eligibility_candidate `
  --expected-core 7aa11610867291a2274d31a7ae2ec69fb8acc03e808314a8cde29fdedd88aabe `
  --package validation/campaign/trace_comparison/export_fixture.json `
  --commands validation/campaign/trace_comparison/empty_commands.json `
  --plan validation/campaign/trace_comparison/export_plan.json `
  --output validation/campaign/trace_comparison/exported_model.json
```

## 比较合同

trace schema为 `ark-sim/intermediate-trace/v1`，包含origin、identity和samples。每个sample必须有frame、frame_before、frame_after、complete与values；前后帧必须与frame精确一致。values是显式字段名到原始值的映射。

比较合同 schema为 `ark-sim/intermediate-comparison-contract/v1`，包含：

- identity：stage_id/game_build/platform/content_identity/roster_identity/commands_identity/episode_identity。
- time_mapping：两边origin、正整数numerator/denominator及evidence。模型帧=`(原生帧-native_origin)*numerator/denominator+model_origin`；不可表示时记录缺口，不取整。
- native_frames：明确覆盖的有序不重复帧列表。
- fields：name/native_key/model_key/mode。exact递归严格类型比较；absolute_tolerance只用于明确连续数值，必须逐字段给semantic_type/tolerance/evidence。
- uncovered_requirements：未覆盖的实际准确性要求。

相同示例已执行：

```powershell
..\.venv\Scripts\python.exe tools/compare_campaign_trace.py `
  --native validation/campaign/trace_comparison/synthetic_expected.json `
  --model validation/campaign/trace_comparison/exported_model.json `
  --contract validation/campaign/trace_comparison/contract.json `
  --output validation/campaign/trace_comparison/exported_comparison.json
```

比较通过返回exit0，存在差异返回exit1；错误身份/格式直接拒绝。输出保存输入和工具起止SHA、覆盖项、全部差异及第一次分歧。当前入口不签独立来源收据，也不提升actual_game_accuracy_verified。真实原始采集、标准化器、实例映射、时间映射和覆盖审阅仍必须完成。
