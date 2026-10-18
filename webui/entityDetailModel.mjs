/** Desktop-style detail projection. Presentation only: never reads memory or changes a payload.
 * Last-known values are scoped to one entity/session/policy and retain original frame evidence.
 * A public API value absent because of policy/capability is not reconstructed from defaults.
 */
import {createDetailEvidence,combineEvidence,summarizeFrames} from './entityDetailEvidence.mjs';
// Same enumeration order as game_structs.ABNORMAL_FLAG_DEFS; future slots stay
// visible by numeric index instead of being silently dropped or relabeled.
const abnormalNames=['眩晕','停止技力回复','不可选中','不可阻挡','隐藏','无敌','不会死亡','禁止治疗','失衡免疫','隐形',
  '保留状态1','缴械','沉默','不可移动','保留状态2','友方不可选中','冻结','迷彩','强制缴械','眩晕（不增伤）',
  '禁止战斗','免疫全部元素损伤','不可移动（私有）','寒冷','技能不可激活','浮空','禁锢','不可撤退','离地','停止技力修改',
  '抵抗可抵抗状态','战斗缴械','塔不可选中','恐惧','异常中可激活技能','移动目标不可选中','强制浮空',
  '可被防御取消的Buff','防御可取消Buff','麻痹','麻痹中','吸引','恐惧（私有）','昏睡','传送','地面束缚'];
const attributes = ['最大生命','攻击','防御','法术抗性','部署费用','阻挡数','移动速度','攻击速度','基础攻击间隔',
  null,null,null,null,'每秒生命恢复','每秒技力恢复','技能范围前向延伸','最大部署数','物理穿透比例','法抗穿透比例',
  '按最大生命每秒恢复','嘲讽等级','再部署时间','最大卡组堆叠数','重量等级','基础力度等级','固定物理穿透',
  '一减状态抗性','固定法抗穿透','损伤条上限','每秒损伤恢复','技力恢复倍率','元素损伤减免','元素抗性',
  '物理伤害命中倍率','法术伤害命中倍率','元素爆发恢复速度','减速倍率','阻挡半径倍率'];
const labels = {name:'名称',key:'内部键',value:'数值',value_str:'文本值',class:'运行类',description:'说明',
  ready:'已就绪',casting:'施放中',wait_for_end:'技能持续中',trigger_count:'触发次数',cooldown_period:'总冷却',
  cooldown_remaining:'剩余冷却',enabled:'启用',valid:'有效',finished:'已结束',source:'来源',
  max_charge:'最大充能',cost:'技力消耗',init_sp:'初始技力',duration:'持续时间',type:'类型',
  addition:'基础加算',multiplier:'倍率加算',final_addition:'最终加算',final_scaler:'最终倍率',
  skill_id:'技能 ID',prefab_key:'预制键',level:'等级',runtime:'运行时',blackboard:'参数',
  source_name:'来源阵营',target_count:'目标数',applies_to_selected:'作用当前单位',
  life_time:'总持续时间',remaining_time:'剩余时间',existing_time:'已存在时间',priority:'优先级',
  stack_count:'当前层数',max_valid_stack_count:'最大有效层数',ability_class:'能力类',
  required_potential:'需求潜能',parent_modes:'模式',mode_count:'模式数',range_id:'范围 ID',
  name_en:'英文名',instance_uid:'实例 UID',effect_key:'特效键',override_key:'覆盖键',
  attribute_modifiers:'属性修改',abnormal_flags:'赋予状态',abnormal_immunes:'免疫',abnormal_antis:'反制',
  abnormal_combos:'组合状态',abnormal_combo_immunes:'组合免疫',has_shield:'有护盾',shield_mask:'护盾类型掩码',
  custom_shield_value:'特殊护盾值',custom_shield_mask:'特殊护盾类型',source_category:'来源分类',
  template_key:'模板键',buff_key:'效果键',remaining:'剩余冷却',period:'总冷却',
  displayDescription:'效果说明',displayBuffDefinitions:'生成 Buff',
  atk:'攻击',def:'防御',attack_speed:'攻击速度',respawn_time:'再部署时间',interval:'间隔',
  sp:'技力',hp:'生命',max_hp:'最大生命',max_sp:'最大技力',early_finished:'技能提前结束',overloaded:'过载',
  min_sp:'最小技力',max_triggers:'最大触发次数',cast_start_frame:'施放起始帧',attached:'已挂载',finish_reason:'结束原因',
  life_time_type:'生命周期类型',trigger_life_type:'触发计时类型',trigger_interval:'触发间隔',
  max_stack_count:'最大层数',override_type:'覆盖类型',disable_override:'禁止覆盖',load_from_db:'来自数据库',
  durable:'持久',damage_missable:'伤害可闪避',silenceable:'可沉默',stunnable:'可眩晕',freezable:'可冻结',
  levitatable:'可浮空',ground_boundable:'可地面束缚',status_resistable:'受状态抗性影响',
  independent_character_source:'独立单位来源',ep_break_buff:'元素爆发 Buff',definition:'静态定义'};
const at = (value, path) => path.split('.').reduce((item,key) => item!=null && Object.hasOwn(item,key)?item[key]:undefined, value);
const column = (key,label,width=170) => ({key,label,width});
const pairColumns = [column('name','项目',200),column('value','数值 / 说明',600)];

export function formatDetailValue(value) {
  if (value === null || value === undefined) return '不可用';
  if (typeof value === 'boolean') return value ? '是' : '否';
  if (typeof value === 'number') return Number.isFinite(value) ? (Number.isInteger(value) ? String(value) : String(Number(value.toFixed(6)))) : '不可用';
  if (Array.isArray(value)) return value.length ? value.map(formatDetailValue).join('；') : '无';
  if (typeof value === 'object') return Object.entries(value).map(([key,item]) => `${Object.hasOwn(labels,key)?labels[key]:key}：${formatDetailValue(item)}`).join('；') || '无';
  return String(value).replace(/<@[^>]*>|<\/>/g,'') || '-';
}
const text = value => ({text:formatDetailValue(value),freshness:'',title:formatDetailValue(value)});
const mapped = (cell, value) => ({...cell,value,text:formatDetailValue(value)});
function ratio(current,maximum) {
  if(current.value===undefined) return current;
  return {...combineEvidence(current,[current,maximum]),text:`${current.text} / ${maximum.text}`,
    title:`当前：${current.title}；上限：${maximum.title}`};
}
const buffNames={common_silence_immue:'沉默免疫',common_silence_immune:'沉默免疫',common_disarmed_immune:'缴械免疫',
  disarmed_immune:'缴械免疫（关卡效果）','damage_scale[type]':'指定伤害类型抗性',reduce_cost_by_interval:'部署费用周期降低'};
function buffTitle(value) {
  if(value.displayName) return value.displayName;
  if(value.name) return value.name;
  if(value.custom_shield_value>0) return '特殊屏障（分段）';
  if(Object.hasOwn(buffNames,value.key)) return buffNames[value.key];
  if(value.abnormal_immunes?.length) return value.abnormal_immunes.join('、')+'免疫';
  if(value.abnormal_flags?.length) return value.abnormal_flags.join('、')+'状态';
  if(value.attribute_modifiers?.length) return value.attribute_modifiers.map(item=>item.name || item.key || '属性').join('、')+'调整';
  if(value.has_shield) return '伤害护盾';
  return value.key || value.class;
}

export function createEntityDetailModel(kind, id) {
  const evidence=createDetailEvidence(kind,id);
  return {project(input) {
    const {basic,detail,basicMeta={},detailMeta={},policy={generation:0,fields:[]},historical=false,connected=true} = input;
    const {basicData,detailData,read:resolve,localDiagnostics}=evidence.project(input);
    function read(source,path,key,options) {
      const cell=resolve(source,path,key,options);
      return cell.value===undefined?cell:{...cell,text:formatDetailValue(cell.value)};
    }
    const b = (path,key=path) => read('basic',path,key);
    const d = (path,key=path) => read('detail',path,key);
    const rows = [];
    const fact = (key,label,cell) => rows.push({id:key,name:text(label),value:cell});
    for(const entry of localDiagnostics()) fact(`local.${entry.key}`,entry.label,{...entry,text:formatDetailValue(entry.value)});
    const name = b('name');
    fact('name','名称',name); fact('publicId','公开实体 ID',text(id));
    fact('unitId',kind==='enemy'?'敌人 ID':'干员 ID',b(kind==='enemy'?'enemyId':'characterId',kind==='enemy'?'eid':'cid'));
    if (kind==='enemy') {
      fact('code','敌人编号',b('code'));
      const life = b('lifecycle','life_status');
      fact('lifecycle','生存状态',life.value===undefined?life:mapped(life,({active:'场上',pending:'未出场',departed:'已离场'})[life.value] || life.value));
      for(const [key,label] of [['spawnOrder','预定出怪顺序'],['spawnKind','出场方式'],['spawnSource','触发来源'],['spawnEta','距离出场（秒）'],['spawnCondition','出场条件']]) fact(key,label,b(key,'spawn_wait'));
      for(const [key,label] of [['wave_index','配置波次索引'],['fragment_index','片段索引'],['action_index','行动索引'],['spawn_index','行动内序号索引'],['route_index','路线索引']]) fact(`spawnContext.${key}`,label,b(`spawnContext.${key}`,'spawn_wait'));
    } else {
      const unitKind=b('kind'); fact('kind','单位类别',unitKind.value===undefined?unitKind:mapped(unitKind,({operator:'干员',token:'召唤物 / 装置'})[unitKind.value] || unitKind.value));
      const profession=b('profession'); fact('profession','职业',profession.value===undefined?profession:mapped(profession,({1:'近卫',2:'狙击',4:'重装',8:'医疗',16:'辅助',32:'术师',64:'特种',128:'召唤物',256:'装置',512:'先锋'})[profession.value] || `枚举 ${profession.value}`));
      const level=b('level'); fact('level','精英化 / 等级',level.value?mapped(level,`E${level.value.elite ?? '—'} Lv.${level.value.level ?? '—'}`):level);
      for(const [key,label] of [['unique_id','实例 UID'],['tmpl_id','模板 ID'],['alias','别名'],['name_en','英文名'],
        ['rarity','稀有度枚举'],['potential_rank','潜能等级'],['favor_phase','信赖阶段'],['is_assist','助战'],
        ['is_predefined','预定义单位'],['is_hidden','隐藏单位'],['team_key','队伍键'],['nation_id','国家'],
        ['group_id','阵营'],['team_id','小队'],['token_or_host_key','召唤 / 宿主键'],['token_or_host_uid','召唤 / 宿主 UID']]) fact(`identity.${key}`,label,b(`identity.${key}`,'identity'));
      for(const [key,label,field] of [['alive','存活','alive'],['finishReason','离场原因枚举','deployment'],
        ['direction','朝向枚举','direction'],['blockedCount','阻挡敌人数','blocked'],['blockedVolume','阻挡敌人体积','blocked'],
        ['buffCount','Buff 数量','buff_count'],['deployment.deploy_cost_this_time','本次部署费用','deployment'],
        ['deployment.card_uid','卡片 UID','deployment']]) fact(key,label,b(key,field));
    }
    const hp=b('hp'); const maxHp=b('maxHp','hp');
    fact('hp','生命',ratio(hp,maxHp));
    if (kind==='character') fact('sp','技力',ratio(b('sp'),b('maxSp','sp')));
    const position=b('position','pos');
    fact('position','位置（列 / 行）',position.value?mapped(position,`(${formatDetailValue(position.value.x ?? position.value.col)}, ${formatDetailValue(position.value.y ?? position.value.row)})`):position);
    if (kind==='enemy') fact('precise','精确坐标',b('precisePosition','precise_pos'));
    fact('shield','伤害护盾',b('shield')); fact('elementShield','元素护盾',b('elementShield','es'));
    if(kind==='enemy') fact('specialShield','特殊护盾',d('specialShield'));
    if(kind==='enemy') {
      for(const [key,label] of [['blockedPosition','阻挡位置'],['spawnPosition','出生格（列 / 行）'],['direction','朝向枚举']]) fact(key,label,b(key,'coordinates_extra'));
      const mask=d('specialShieldMask','specialShield');
      fact('specialShieldMask','特殊护盾类型',mask.value===undefined?mask:mapped(mask,
        Object.entries({2:'物理',4:'法术',8:'真实',16:'治疗',32:'元素'}).filter(([bit])=>mask.value & Number(bit)).map(([,name])=>name).join(' / ') || '无'));
      const regular=b('shield'), special=d('specialShield');
      const total=Number.isFinite(regular.value) && Number.isFinite(special.value)
        ? combineEvidence(mapped(regular,Math.max(0,regular.value)+Math.max(0,special.value)),[regular,special]):text('不可用');
      if(total.value!==undefined) total.title=`通用护盾：${regular.title}；特殊护盾：${special.title}`;
      fact('totalShield','伤害护盾合计',total);
    }
    const countdown=b('action','remaining_time');
    if(countdown.value) {
      const {remaining_frames:frames,remaining:seconds,remaining_kind:condition}=countdown.value, parts=[];
      if(Number.isInteger(frames) && frames>=0) parts.push(`${frames} 帧`);
      if(Number.isFinite(seconds) && seconds>=0) parts.push(`${seconds.toFixed(2)} 秒`);
      fact('action.countdown','剩余帧/时间',mapped(countdown,parts.length?parts.join(' / ')+(condition?`（${condition}）`:''):condition || '条件驱动'));
    } else fact('action.countdown','剩余帧/时间',countdown);
    for (const [key,label,field] of [['state_name','行为状态','action_state'],['name','动作阶段','action_phase'],
      ['detail','动作说明','action_phase'],['remaining_kind','剩余帧 / 时间条件','remaining_time'],
      ['next_action','下一动作','next_action'],['next_action_detail','下一动作依据','next_action'],
      ['next_action_rule','下一动作（Boss 规则）','next_action'],['next_action_rule_detail','Boss 规则依据','next_action'],
      ['remaining','剩余时间（秒）','remaining_time'],['remaining_frames','剩余逻辑帧','remaining_time'],
      ['clock_source','倒计时来源','action_phase'],['current_frame','动作逻辑帧','action_phase'],
      ['elapsed_frames','动作已进行帧数','action_phase'],['animation_exact','精确动画计时','action_phase'],
      ['animation_track_name','当前动画','action_phase'],['animation_key','动画键','action_phase'],
      ['animation_track_speed','动画播放速度','action_phase'],['animation_speed','动画基础速度','action_phase'],
      ['animation_track_time','动画已播放时间','action_phase'],['animation_loop','循环动画','action_phase'],
      ['skill_name','当前技能','action_phase'],['ready_skills','已就绪技能','action_phase'],
      ['next_action_confidence','下一动作可信度','next_action'],['next_action_rule_confidence','Boss 规则可信度','next_action']]) {
      if (kind==='character' && key.includes('rule')) continue;
      let cell=read('basic',`action.${key}`,field,{optional:true});
      const boss=key==='next_action_rule_confidence';
      const confidence={confirmed:'游戏已写入',unselected:'游戏尚未预选',
        ...(kind==='enemy'?(boss?{
          inferred:'按敌人原始代码推断',rule_calculated:'按敌人原始代码计算（未加入当前CD）',
          rule_snapshot:'按敌人原始代码计算当前快照（未加入当前CD）',
          rule_candidates:'敌人原始代码得到候选组（战斗 RNG 择一）',rule_partial:'敌人原始代码仍有 Search/Lua/关卡条件待执行',
        }:{inferred:'按游戏判据推断（CD/触发次数/优先级）',rule_calculated:'按客户端原始规则计算（当前判据唯一）',
          rule_snapshot:'按客户端原始规则计算当前快照（动作结束时会重算）',
          rule_candidates:'按客户端原始规则得到候选组（战斗 RNG 择一）',rule_partial:'按客户端原始规则计算，但仍有 Search/Lua/关卡条件待执行'}):{})};
      if(cell.absent && cell.accepted) {
        const condition=read('basic','action.remaining_kind','remaining_time',{optional:true});
        if(['remaining','remaining_frames'].includes(key) && condition.value && condition.sourceFrame===cell.sourceFrame) {
          cell=combineEvidence(mapped(cell,`不适用（${condition.value}）`),[cell,condition]);
        } else if(key==='animation_exact') cell=mapped(cell,'否/不适用');
        else if(key==='animation_track_name' || key==='animation_track_speed') {
          const fallback=read('basic',`action.${key==='animation_track_name'?'animation_key':'animation_speed'}`,field,{optional:true});
          cell=fallback.value!=null?fallback:mapped(cell,'-');
        } else cell=mapped(cell,'-');
      }
      if(key==='animation_exact' && typeof cell.value==='boolean') cell=mapped(cell,cell.value?'是（当前速度且未被中断）':'否/不适用');
      if(key==='ready_skills' && Array.isArray(cell.value)) cell=mapped(cell,cell.value.join('、') || '-');
      fact(`action.${key}`,label,key.endsWith('_confidence') && cell.value!==undefined?mapped(cell,confidence[cell.value] || cell.value):cell);
    }
    if (kind==='enemy') for (const [key,label] of [['intent_end','意图终点'],['current_route','当前路线'],
      ['next_waypoint','下一路点'],['next_checkpoint','下一检查点'],['checkpoint_countdown','检查点倒计时']]) fact(key,label,b(`columns.${key}`,key));
    const tabs = [{id:'overview',label:'概览',columns:pairColumns,rows}];
    const finals=d('attributes'), raws=d('rawAttributes');
    const definitionCell=read('detail','attributeDefinitions','attributes',{staticValue:true});
    const definitions=new Map((definitionCell.value || []).map(([index,internal,label])=>[String(index),{internal,label}]));
    const attrIds=new Set(attributes.flatMap((name,index)=>name?[String(index)]:[]));
    for (const key of Object.keys(finals.value || {})) attrIds.add(key);
    for (const key of Object.keys(raws.value || {})) attrIds.add(key);
    const attrs=[...attrIds].sort((a,b)=>Number(a)-Number(b)).map(key=>{
      let finalValue=finals.value?.[key]; const rawValue=raws.value?.[key];
      let final=finalValue===undefined?{...finals,value:undefined,text:'不可用'}:mapped(finals,finalValue);
      const raw=rawValue===undefined?{...raws,value:undefined,text:'不可用'}:mapped(raws,rawValue);
      // Preserve disabled/capability explanations instead of a misleading dash.
      if (finals.value===undefined) final.text=finals.text;
      if (raws.value===undefined) raw.text=raws.text;
      if (finals.freshness!=='not_collected') {
        const basicValue=b(`attributes.${key}`,`attr_${key}`);
        const fresher=basicValue.value!==undefined && ['current','static','historical'].includes(basicValue.freshness)
          && Number.isInteger(basicValue.sourceFrame) && (final.sourceFrame==null || basicValue.sourceFrame>final.sourceFrame);
        if ((finalValue===undefined && (basicValue.value!==undefined || basicValue.freshness==='not_collected')) || fresher) {
          final=basicValue;finalValue=basicValue.value;
        }
      }
      if(kind==='enemy' && key==='28') {
        const capacity=b('elementRemaining.0','ep_capacity');
        if(capacity.value>Math.max(0,finalValue || 0)) {final=capacity;finalValue=capacity.value;}
      }
      const sameFrame=raws.sourceFrame!==null && raws.sourceFrame===final.sourceFrame;
      const delta=Number.isFinite(finalValue) && Number.isFinite(rawValue)
        ? (sameFrame?combineEvidence(mapped(final,finalValue-rawValue),[final,raw]):text('来源帧不同')):text('不可比较');
      let label=attributes[key] || (Number(key)>=9 && Number(key)<=12?`保留属性槽 ${key}`:`未知属性槽 ${key}`);
      if(key==='26' && Number.isFinite(finalValue)) label+=`（实际抗性 ${formatDetailValue(1-finalValue)}）`;
      return {id:key,name:text(label),slot:text(key),internal:mapped(definitionCell,definitions.get(key)?.internal),raw,final,delta};
    });
    tabs.push({id:'attributes',label:'属性',columns:[column('name','属性',210),column('slot','属性槽',85),column('internal','内部属性名',230),
      column('raw','原始值'),column('final','最终值'),column('delta','变化')],rows:attrs,
      note:'详情与 PySide6 一样不继承主表隐藏列；采集开关、详情分组展示开关仍生效。缺失值不补零，仅同一来源帧计算变化。'});
    if (kind==='character') {
      const damage=[['damageTotal','累计伤害','damage_total'],['healingTotal','累计治疗','healing_total'],
        ['globalDamageSummary','全局总伤（共享值）','global_total_damage'],
        ['damageByType.physical','物理伤害','damage_physical'],['damageByType.magical','法术伤害','damage_magical'],
        ['damageByType.pure','真实伤害','damage_pure'],['damageByType.element','元素类型直接伤害','damage_element']];
      const damageRows=damage.map(([path,label,key])=>({id:path,name:text(label),value:b(path,key)}));
      for(const [key,label,field] of [['damageRange.min','单次输出最小绝对值','damage_range'],['damageRange.max','单次输出最大绝对值','damage_range'],['elementOutputTotal','元素损伤输出合计','element_output_total'],['unattributedDamage','未归属伤害','unattributed_damage']]) damageRows.push({id:key,name:text(label),value:b(key,field)});
      for(const [index,label] of ['神经','侵蚀','灼燃','凋亡','狂躁'].entries()) {
        for(const [key,suffix,field] of [['elementOutputByType','损伤累计','element_output_by_type'],['elementBreakCount','爆发次数','element_break_count']]) {
          const path=`${key}.${index+1}`; damageRows.push({id:path,name:text(label+suffix),value:b(path,field)});
        }
      }
      tabs.push({id:'damage',label:'伤害统计',columns:pairColumns,rows:damageRows});
    }
    const skills=d('skills');
    const skillsRows=(Array.isArray(skills.value)?skills.value:[]).map((skill,index)=>{
      if (Array.isArray(skill)) return {id:String(index),name:mapped(skills,skill[0]),priority:text('接口未提供'),remaining:mapped(skills,skill[1]),period:mapped(skills,skill[2]),state:mapped(skills,Number.isFinite(skill[1])?(skill[1]<=0?'就绪':'冷却中'):'不可用')};
      return {id:String(index),name:mapped(skills,skill.name ?? skill.skill_id),priority:mapped(skills,skill.priority),remaining:mapped(skills,skill.remaining ?? skill.runtime?.cooldown_remaining),period:mapped(skills,skill.period ?? skill.runtime?.cooldown_period),state:mapped(skills,skill.ready ?? (Number.isFinite(skill.remaining)?skill.remaining<=0:undefined))};
    });
    if (kind==='character') {
      const skill=Array.isArray(skills.value)?skills.value[0]:undefined;
      const skillFacts=[];
      const addSkill=(path,label,value,category='基础')=>{
        let cell=mapped(skills,value);
        if(path==='current_sp') cell=b('sp');
        else if(path==='max_sp') cell=b('maxSp','sp');
        else if(path==='ready' || (path.startsWith('runtime.') && !['runtime.class','runtime.ability_class'].includes(path))) {
          const current=b(`skill.${path}`,'skill');
          if(current.value!==undefined) cell=current;
        }
        skillFacts.push({id:path,category:text(category),name:text(label),value:cell});
      };
      if (skill) {
        for (const [path,label] of [['name','名称'],['skill_id','技能 ID'],['level','技能等级'],
          ['duration','标称持续时间（秒）'],['current_sp','当前技力'],['max_sp','最大技力'],['ready','已就绪']]) addSkill(path,label,at(skill,path));
        addSkill('type','技能类型',({0:'被动',1:'手动触发',2:'自动触发'})[skill.type] ?? skill.type);
        addSkill('duration_type','持续类型',({0:'普通',1:'弹药'})[skill.duration_type] ?? skill.duration_type);
        for(const [section,category] of [['sp','技力'],['runtime','运行时']]) {
          for(const [key,value] of Object.entries(skill[section] || {})) {
            if(key==='blackboard') continue;
            const shown=section==='sp' && key==='type'
              ? ({0:'无',1:'自动回复',2:'攻击回复',4:'受击回复',6:'攻击或受击回复',7:'全部方式'})[value] ?? value:value;
            addSkill(`${section}.${key}`,Object.hasOwn(labels,key)?labels[key]:`参数 ${key}`,shown,category);
          }
        }
        if(Number(skill.runtime?.cooldown_period)>=3600) {
          for(const fact of skillFacts.filter(row=>['runtime.cooldown_period','runtime.cooldown_remaining'].includes(row.id))) fact.value=mapped(fact.value,'持续 / 无限');
        }
        for(const [path,category] of [['blackboard','静态参数'],['runtime.blackboard','运行时参数'],['runtime.ability_blackboard','能力参数']]) {
          const values=at(skill,path);
          if(Array.isArray(values)) values.forEach((item,index)=>addSkill(`${path}.${index}`,
            `${Object.hasOwn(labels,item.key)?labels[item.key]:'参数'}（${item.key}）`,item.value_str || item.value,category));
        }
        const description=String(skill.description || '').replace(/\{([\w.]+)\}/g,(match,key)=>{
          const value=skill.blackboard?.find(item=>item.key===key)?.value;
          return value===undefined?match:formatDetailValue(value);
        });
        addSkill('description','技能说明',description || undefined);
      }
      tabs.push({id:'skills',label:'主技能',columns:[column('category','类别',120),column('name','项目',230),column('value','值',550)],rows:skillFacts,
        note:skills.value===undefined?skills.text:'',empty:'无技能'});
    } else tabs.push({id:'skills',label:'技能',columns:[column('name','技能',220),column('priority','优先级',100),column('remaining','剩余 CD（秒）'),column('period','总 CD（秒）'),column('state','就绪状态')],rows:skillsRows,note:skills.value===undefined?skills.text:'',empty:'无技能'});
    const statuses=[{id:'abnormalStatus',name:text('当前异常状态'),value:b('abnormalStatus','abnormal_status')}];
    const statusDefinitions=path=>{
      const primary=read('basic',path,'abnormal_status',{staticValue:true});
      return primary.freshness==='not_collected'?read('basic',path,'immune_status',{staticValue:true}):primary;
    };
    const flagDefinitions=statusDefinitions('statusDefinitions'), comboDefinitions=statusDefinitions('comboDefinitions');
    const flagNames=new Map(flagDefinitions.value || []), comboNames=new Map(comboDefinitions.value || []);
    for(const [path,label,names,field] of [['abnormalFlags','状态计数',abnormalNames,'abnormal_status'],['abnormalCombos','组合状态计数',['睡眠','庇护'],'abnormal_status'],['abnormalImmunes','免疫计数',abnormalNames,'immune_status'],['abnormalAntis','反制计数',abnormalNames,'immune_status'],['abnormalComboImmunes','组合免疫计数',['睡眠','庇护'],'immune_status']]) {
      const cell=b(path,field);
      if(Array.isArray(cell.value) && cell.value.every(value=>typeof value==='number')) {
        cell.value.forEach((count,index)=>statuses.push({id:`${path}.${index}`,name:text(`${label} · ${names[index] || `未知状态槽 ${index}`}`),
          internal:mapped(path.includes('Combo')?comboDefinitions:flagDefinitions,(path.includes('Combo')?comboNames:flagNames).get(index)),value:mapped(cell,count)}));
      } else statuses.push({id:path,name:text(label),value:cell});
    }
    const timers=b('statusTimers','abnormal_status');
    for(const [key,timer] of Object.entries(timers.value || {})) {
      const [type,index]=key.split(':'); const label=type==='flag'?abnormalNames[index]:['睡眠','庇护'][index];
      statuses.push({id:`timer.${key}`,name:text(`${label || key} · 剩余时间`),value:mapped(timers,timer.infinite?'无限':timer.remaining)});
    }
    tabs.push({id:'statuses',label:'状态与免疫',columns:[column('name','项目',250),column('internal','内部状态名',250),column('value','数值 / 说明',400)],rows:statuses});
    for (const [key,label,empty] of [['buffs','当前 Buff','无当前 Buff'],['globalBuffs','关卡效果','无关卡效果'],
      ...(kind==='character'?[['talents','天赋','无天赋'],['dynamicAbilities','动态能力','无动态能力'],['equipment','模组设置','无模组设置']]:[])]) {
      const group=d(key), values=Array.isArray(group.value)?group.value:[];
      const groupRows=values.map((entry,index)=>{
        const value=entry && typeof entry==='object'?entry:{value:entry};
        const title=key==='talents'?(value.name || '-'):(buffTitle(value) || `${label} ${index+1}`);
        const parameters=Object.fromEntries(Object.entries(value).filter(([name])=>!['name','displayName','key','source','source_category','fieldStates'].includes(name)));
        return {id:String(index),name:mapped(group,title),key:mapped(group,value.key ?? value.prefab_key ?? value.class),
          sourceCategory:mapped(group,value.source_category),source:mapped(group,value.source ?? value.source_name),
          time:mapped(group,value.life_time===undefined?undefined:value.life_time<0?`无限；已存在 ${formatDetailValue(value.existing_time)} 秒`:`剩余 ${formatDetailValue(value.remaining_time)} / 总计 ${formatDetailValue(value.life_time)} 秒`),
          stacks:mapped(group,value.stack_count===undefined?undefined:`${value.stack_count} / ${value.max_valid_stack_count ?? '—'}`),
          description:mapped(group,parameters)};
      });
      tabs.push({id:key,label,columns:[column('name','名称 / 效果',190),column('key','内部键',220),column('sourceCategory','来源分类',230),column('source','来源',200),
        column('time','持续时间',240),column('stacks','层数',120),column('description','效果、运行信息与参数',460)],
        rows:groupRows,note:group.value===undefined?group.text:'',empty});
    }
    const elements=Array.from({length:5},(_,index)=>{
      // ElementType.NONE=0 is capacity, not the first concrete damage type.
      const value=b(`elementRemaining.${index+1}`,'ep_'+['sanity','water','fire','dark','anger'][index]);
      const maxAttr=attrs.find(row=>row.id==='28')?.final || b('attributes.28','attr_28');
      const capacity=b('elementRemaining.0','ep_capacity');
      const maximum=kind==='enemy' && capacity.value>0?capacity:maxAttr;
      if(kind==='character' && Number.isFinite(value.value) && Number.isFinite(maximum.value)) {
        Object.assign(value,mapped(value,Math.min(Math.max(0,maximum.value),Math.max(0,value.value))));
      }
      const damage=Number.isFinite(maximum.value) && Number.isFinite(value.value)?mapped(value,Math.max(0,maximum.value-value.value)):text('不可用');
      if(maximum.freshness==='last_known') damage.freshness='last_known';
      const percent=Number.isFinite(damage.value) && maximum.value>0?mapped(damage,`${formatDetailValue(damage.value/maximum.value*100)}%`):text('不可用');
      const remainingPercent=Number.isFinite(value.value) && maximum.value>0?mapped(value,`${formatDetailValue(value.value/maximum.value*100)}%`):text('不可用');
      const broken=Number.isFinite(value.value) && Number.isFinite(maximum.value)?mapped(value,maximum.value>0 && value.value<=0):text('不可用');
      for(const cell of [damage,percent,remainingPercent,broken]) if(cell.value!==undefined) Object.assign(cell,combineEvidence(cell,[value,maximum]));
      return {id:String(index),name:text(['神经损伤','侵蚀损伤','灼燃损伤','凋亡损伤','狂躁损伤'][index]),value,maximum,damage,percent,remainingPercent,broken,recovery:b('elementBreakRecovery','ep_break')};
    });
    tabs.push({id:'elements',label:kind==='enemy'?'损伤条':'元素损伤',columns:[column('name','元素类型'),column('damage','累积损伤'),column('value','剩余容量'),column('maximum','上限'),column('percent','累积比例'),column('remainingPercent','剩余比例'),column('broken','元素爆发'),column('recovery','爆发恢复中')],rows:elements,
      note:'复用游戏属性及运行时容量；缺失输入不补零。各输入保留自己的来源帧。'});
    if (kind==='character') {
      const effects=tabs.filter(tab=>['globalBuffs','dynamicAbilities','equipment'].includes(tab.id));
      const effectRows=effects.flatMap(tab=>tab.rows.map(row=>({...row,id:`${tab.id}-${row.id}`,category:text(tab.label)})));
      const deck=d('deckBuffBlackboard','equipment');
      effectRows.push({id:'deckBuffBlackboard',category:text('编队 Buff'),name:text('DeckBuff Blackboard'),key:text('deckBuffBlackboard'),description:deck});
      tabs.splice(0,tabs.length,...tabs.filter(tab=>!effects.includes(tab)));
      tabs.push({id:'effects',label:'其他效果',rows:effectRows,
        columns:[column('category','类别',130),column('name','名称 / 效果',180),column('key','内部键',220),
          column('sourceCategory','来源分类',230),column('source','来源',200),column('time','持续时间',240),
          column('stacks','层数',120),column('description','效果、运行信息与参数',460)],
        note:effects.filter(tab=>tab.note).map(tab=>`${tab.label}：${tab.note}`).join('；'),empty:'无其他效果'});
    }
    const frames=d('effectFrames');
    tabs.push({id:'frames',label:'生效帧',columns:(frames.value?.columns || []).map((label,index)=>column(String(index),label,220)),
      rows:(frames.value?.rows || []).map((values,index)=>({id:String(index),...Object.fromEntries(values.map((value,slot)=>[String(slot),mapped(frames,value)]))})),
      note:frames.value?(frames.value.rows?.length?'本地提取的静态动作资料，与 PySide6 共用；不是当前逻辑帧的实时观测。':'本地静态资料未提取到此单位的生效帧。'):frames.text,empty:'未提取到此单位的生效帧资料'});
    tabs.push({id:'raw',label:'原始数据',rows:[]});
    const order=kind==='character'?['overview','attributes','damage','skills','statuses','buffs','talents','elements','effects','frames','raw']
      :['overview','attributes','elements','statuses','buffs','globalBuffs','skills','frames','raw'];
    tabs.sort((a,b)=>order.indexOf(a.id)-order.indexOf(b.id));
    // Heterogeneous sections (e.g. a status summary or deck Blackboard row)
    // have structurally inapplicable columns, not JS "undefined" game values.
    for(const tab of tabs) for(const row of tab.rows) for(const {key} of tab.columns || []) {
      if(!Object.hasOwn(row,key)) row[key]={...text('-'),title:'此行不适用'};
    }
    const framesSummary={basic:summarizeFrames(tabs,'basic',basicMeta.sourceFrame),detail:summarizeFrames(tabs,'detail',detailMeta.sourceFrame)};
    return {title:name.value || (kind==='enemy'?'敌人详情':'干员详情'),tabs,
      status:historical?'本局历史快照 · 非实时 · 不读取离场对象':connected?'基础数据与异步详情独立更新':'后端连接中断 · 显示最后已知值',
      sourceFrame:framesSummary.basic.sourceFrame,detailFrame:framesSummary.detail.sourceFrame,frames:framesSummary,
      raw:{basic:basicData,detail:detailData,basicMeta,detailMeta}};
  }};
}
