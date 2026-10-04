# 受控Spine读取与原生动画绑定

`tools/extract_campaign_animation_bindings.py` 提取雷蛇、夜莺、凯尔希的确定动画绑定，输出
`packages/campaign/animation_bindings.reference.json`。状态为 **offline_source_bindings_only**，
runnable=false、conversion_approved=false。没有修改site-packages、共享effect_frames.json、
原始资产或生产运行时，也没有把来源恢复升级为客户端/正式主线通过。

## 读取控制与身份

本地spine_asset.utils.SkeletonBinaryReader.read_float32原本使用`<f`。
实际Spine 3.8.99资产的这些浮点字节为big-endian：例如0.2的原始字节按旧函数读成约-428443584，
而正确读取为float32的0.20000000298023224。

提取器创建私有reader子类，只重写float32为`>f`；用FunctionType复制可信parser入口函数的globals，
将其SkeletonBinaryReader符号绑定到这个私有子类。没有替换模块或类上的原方法，
因此同一进程里的其他调用仍见到原reader，安装文件也保持原始字节身份。

当前仅接受经过本批实际检查的 **Spine 3.8.99、author FPS30**；
float必须有限且绝对值不超过1e8、动画duration须在0..120秒、事件须在动画duration范围内，
事件帧和值数量一致，并且reader须消费全部TextAsset Script payload。
未知版本、截断、尾随字节和越界时间明确拒绝，不做“解析失败就用缓存”降级。

reference保留：

- charpack、chararts和projectile CAB路径、字节数、SHA-256；
- 六个确切front/back TextAsset的原始Script bytes（base64）、完整payload hash、Unity包装hash和解析结果；
- Animator、SkeletonRenderer、SkeletonDataAsset、TextAsset之间精确PPtr链，Mono组件scriptPathID和raw字段；
- 安装spine_asset全部Python源文件的hash、原reader与parser入口源身份，以及受控提取器自身hash；
- current IL2CPP dump的相关类声明片段和来源hash，作为字段布局佐证。方法body为空，不能当作原生逻辑证明。

## 浮点时间与作者帧

同时保留source_seconds_float32与可供模型使用的seconds/frame。
仅当`float32(round(time*FPS)/FPS)`的位模式与源float32完全相同时，才认定为整数作者帧。
例如1/30在float32中稍大于1/30，直接给double时钟ceil可能错误落到tick2；
重新编码证明它来自frame1后使用1/30，仍保存原始0.03333333507180214。
分数帧没有这个位相等证明时原样保留，不采用任意“最近帧”猜测。

## 确定绑定

| 角色与模式 | 精确来源链 | 确定事件 |
|---|---|---|
| 雷蛇base mode0 | ability.animKey为空；同GameObject的ThreePartOneshotAnimation.oneshotAnim=Attack；chararts Animator映射Attack→Attack_Loop；front/back renderer分别指向其实际SkeletonDataAsset/TextAsset | Attack_Loop.OnAttack=frame1；duration36帧 |
| 雷蛇三段动画begin | 同一ThreePart组件beginAnim=Attack_Begin、onlyPlayBeginWhenFirstAttack=1，Animator有对应行 | begin duration10帧；完整协程交接/缩放尚未转换 |
| 夜莺base mode0 | ability Attack_A→chararts Animator行animName=Attack | front/back OnAttack=frame27（0.9秒） |
| 夜莺S3 mode1 | ability Attack_C→chararts Animator行animName=Attack | front/back同样OnAttack=frame27 |
| 凯尔希base mode0 | ability Attack→chararts Animator显式Attack行 | front/back OnAttack=frame13 |

雷蛇TextAsset实际名是 `char_107_liskarm.skel`，不是按角色ID拼出的liskam文件名。
提取器用Renderer→DataAsset→TextAsset引用取资产，避免此命名差异导致遗漏。
夜莺Attack_A/B/C到Attack的映射是实际序列化`_animations`行，不是缺名字后退回通用Attack。
缺失或重复alias行会拒绝；也不会让缺失动画名字自动变成现有Attack。

雷蛇base attack的空animKey也不能当作instant。
同GO的ThreePart组件给出begin/oneshot/end和onlyFirst标志，提取器保留这个阶段来源。
当前没有从空dump coroutine body猜出首攻击是否要额外等待begin总时长、如何重基next_attack或缩放。
Loop事件与begin时长已经确定；完整原生状态交接仍pending，后续模式接口必须分别记录模型政策和客户端验证。

## 凯尔希弹道

base RangedHeal的原始_projectileKey为 **projectile_chr_kalts**。
精确匹配该GameObject的movement组件，pathID=-4397858936411173260，给出：
speed5、raiseHeight≈0.3、onlyReachedInTime0、delayTime0、noRaiseHeightThreshold≈1.3。
已保存整个该GO组件组及source CAB身份；没有用前缀匹配把kalts2、token或graphic variant混进来。

因此“缓存没有速度”不能解释成即时治疗。本批已经恢复确切movement参数。
同时，没有把存在speed5推导成原生Heal必定在何种Projectile.Event结算：
RangedHeal.GetProjectileActions、NewHealNode及ParacurveMovement类的声明存在，但dump没有方法实现。
精确hit/reached回调次序、弧线/追踪和travel公式仍pending。
`instant_or_visual_only_proven=false`明确拒绝无证据的instant/visual-only结论。

## 消费接口与验证

root converter可读取：

- `operators[character_id].modes[index].bindings_by_face[front/back]`
- 每个binding的`mapping`、`animation_name`、`events`、`duration`；
- `face_sources`的确切PPtr链和`skeleton_assets[payload_sha256]`原始bytes；
- `three_part_animation_source`与pending，不能丢掉begin/loop来源；
- `projectiles.projectile_chr_kalts.speed/components/pending`。

build和--check成功，**16项定向测试通过，2.34秒**，覆盖重建/字节身份、六payload重解析、
原reader与安装文件不被修改、精确alias/PPtr链、未知名字不fallback、精确float32作者帧证明、
未知版本/尾随数据/坏Unity包拒绝，以及实际speed5不被宣称instant。

```powershell
..\.venv\Scripts\python.exe tools/extract_campaign_animation_bindings.py
..\.venv\Scripts\python.exe tools/extract_campaign_animation_bindings.py --check
..\.venv\Scripts\python.exe -m pytest tests_v2/test_campaign_animation_bindings.py -q
```

这些是确定来源绑定和受控读取证据。源版本对应、动态播放速度、状态交接、曲线弹道和客户端逐帧对照
保持明确pending，不生成模型批准收据，也不改写旧共享帧表为“新版本已通过”。
