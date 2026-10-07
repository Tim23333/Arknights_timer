"""Independent typed native inputs audit; no simulation or whole approval."""
import copy,hashlib,json,sys,traceback
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.chapter10_stage_source_peer_v1.source_preflight import exact,leaf_types
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def main():
 out=ROOT/'validation/campaign/chapter0_stage_input_peer_v1';out.mkdir(parents=True,exist_ok=True)
 planpath=ROOT/'packages/campaign/chapter0_source_prepare/source.plan.v3.json';plan=load(planpath)
 enemyfile=ROOT/'packages/campaign/chapter0_consumers/enemies.module.v2.json';enemy=load(enemyfile);rosterfile=ROOT/'packages/campaign/roster/fixed12.m26.reference_module.json';roster=load(rosterfile);storiesfile=ROOT/'packages/campaign/chapter0_source_prepare/stories.native.v1.json';stories=load(storiesfile)['stories'];paths=[Path(__file__),planpath,enemyfile,rosterfile,storiesfile];results=[]
 pins=['5acc0854ba4d6efa386268cf0234379cc7d0d36dad54223506ceb24bd5a6881d','c681ffd833f1530d93ba8bc307c3f4a13f11c538b1a7ce1cb75ae223492be4c3']
 for stage,pin,births,popups in zip(['level_main_00-10','level_main_00-11'],pins,[35,37],[3,2]):
  facts={}
  try:
   p=ROOT/'packages/campaign/chapter0_stage_models'/f'{stage}.source.v2.json';paths.append(p);assert sha(p)==pin;d=load(p);meta=d['manifest']['metadata'];n=plan['stages'][stage]['native_document'];s=d['scenarioDraft'];defs={x['id']:x for x in d['definitions']};exact(meta['native_document'],n);exact(meta['native_action_records'],plan['stages'][stage]['actions']);leaf_types(n)
   for path,h in meta['source_locks'].items():assert sha(path)==h;paths.append(Path(path))
   assert meta['required_runtime']=='08b6eee3fff37f6f665da5154b204c29feadc1ad0c1cef5d1640ce56940c1878';assert sha(enemyfile)=='15f7c0e7ec22e7cd39d861895e8bcc0986f6912000db4bff3b25c56817bdbf3f'
   rows=len(n['mapData']['map']);cols=len(n['mapData']['map'][0]);tiles=[]
   for row in n['mapData']['map']:
    for index in row:
     raw=n['mapData']['tiles'][index];tiles.append({'tileKey':raw['tileKey'],'buildableType':{'NONE':0,'MELEE':1,'RANGED':2,'ALL':3}[raw['buildableType']],'passableMask':{'NONE':0,'WALK_ONLY':1,'FLY_ONLY':2,'ALL':3}[raw['passableMask']],'heightType':raw['heightType'],'blackboard':raw.get('blackboard'),'effects':raw.get('effects')})
   exact(s['map'],{'rows':rows,'cols':cols,'tiles':tiles,'tile_mechanics':{}});exact(s['metadata']['native_options'],n['options']);assert n['options']['moveMultiplier']==.5;exact(s['resources'],{'dp':{'initial':n['options']['initialCost'],'capacity':n['options']['maxCost'],'recovery_rate':1/n['options']['costIncreaseTime'],'recovery':{'mode':'periodic','interval_seconds':n['options']['costIncreaseTime']}},'life':{'initial':99999,'capacity':99999}});assert s['resources']['dp']['initial']==10;exact(s['parameters'],{'deploy_capacity':8});exact(s['roster'],roster['manifest']['metadata']['roster']);assert len(s['roster'])==12;exact(s['rules'],roster['manifest']['metadata']['stage_rules']);assert s['seed']==n['randomSeed']
   for bucket in ['entities','abilities','buffs','selectors','rules']:
    for original in roster.get(bucket,[]):
     if original['id'] in defs:exact(defs[original['id']],original)
   for bucket in ['entities','abilities','selectors','rules']:
    for original in enemy.get(bucket,[]):
     if original['id'] in defs:exact(defs[original['id']],original)
   assert all(x in defs for x in s['roster']);summons=[x for x in ['unit/campaign_weedy_cannon','unit/support_night_bird','unit/mon3tr'] if x in defs];facts['ally_entities']=[x for x in defs if x.startswith('unit/') and not x.startswith('unit/ch0/')]
   assert len(facts['ally_entities'])==15
   waves=[];count=0;ack=0;routes=[]
   for wi,w in enumerate(n['waves']):
    ow={'pre_delay_seconds':w['preDelay'],'post_delay_seconds':w['postDelay'],'max_wait_seconds':w['maxTimeWaitingForNextWave'],'fragments':[]}
    assert not w['advancedWaveTag']
    for fi,f in enumerate(w['fragments']):
     of={'pre_delay_seconds':f['preDelay'],'actions':[]}
     for ai,a in enumerate(f['actions']):
      m={'native_wave':wi,'native_fragment':fi,'native_action_index':ai,'native_action':a};c={'count':a['count'],'delay_seconds':a['preDelay'],'interval_seconds':a['interval'],'managed':a['managedByScheduler'],'blocks_wave':not a['dontBlockWave'],'blocks_fragment':a['blockFragment'],'metadata':m}
      assert a['randomType']==a['refreshType']=='ALWAYS' and not any(a.get(k) for k in ['hiddenGroup','randomSpawnGroupKey','randomSpawnGroupPackKey','forceBlockWaveInBranch','isUnharmfulAndAlwaysCountAsKilled'])
      if a['actionType']=='SPAWN':
       b=meta['native_enemy_bindings'][a['key']];r=copy.deepcopy(n['routes'][a['routeIndex']]);r['checkpoints']=r['checkpoints'] or []
       for pos in [r['startPosition'],r['endPosition'],*[x['position'] for x in r['checkpoints'] if x.get('position') is not None]]:pos['row']=rows-1-pos['row']
       if r['motionMode']=='E_NUM':r['motionMode']=b['motion']
       assert not any(any((x.get('reachOffset') or {}).values()) for x in r['checkpoints']) and not any(x['type'] in ['DISAPPEAR','APPEAR_AT_POS'] for x in r['checkpoints'])
       spawn={'definition':b['unit'],'route':r,'position':r['startPosition'],'instanceAlias':f'{stage}/w{wi}/f{fi}/a{ai}','parameters':{'native_wave':wi,'native_fragment':fi,'native_action_index':ai,'native_route_index':a['routeIndex']},'placement':{'rule':'rule/m7_spawn_rectangle','stream':'spawn','sample_axes':['col','row'],'sample_zero_range':False,'offset':{'row':-r['spawnOffset']['y'],'col':r['spawnOffset']['x']},'random_range':{'row':r['spawnRandomRange']['y'],'col':r['spawnRandomRange']['x']}}};of['actions'].append({'kind':'spawn','spawn':spawn,**c});count+=a['count'];routes.append(a['routeIndex'])
      else:
       actual=s['timeline']['waves'][wi]['fragments'][fi]['actions'][ai];assert actual['kind']=='control';ctl=defs[actual['definition']];of['actions'].append({'kind':'control','definition':ctl['id'],**c})
       if a['actionType']=='STORY':
        st=stories[a['key']];exact(ctl['metadata']['native_commands'],st['commands']);exact(ctl['metadata']['native_story_source'],st['source']);assert ctl['metadata']['native_script']==st['script'];steps=[]
        for node in st['commands']:
         steps.append({'kind':'effects','effects':[{'op':'emit','target':'battle','event':'reference.story.node','payload':{'native_story_key':a['key'],'native_node':node,'external_reference_only':True}}]})
         if node['command']=='PopupDialog':steps.append({'kind':'ack','key':a['key']+'/line/'+str(node['line'])});ack+=1
         elif node['command']=='Blocker':assert node['parameters']=='fadetime=0.3, block=true, a=0';steps.append({'kind':'delay','seconds':.3})
         else:assert node['command']=='HEADER'
        exact(ctl['steps'],steps);assert ctl['clock_policy']=='logical' and ctl['ack_policy']=='external';exact(ctl['on_start'],[{'op':'input_lock','target':'battle','parameters':{'key':'story','enabled':True}}])
       else:assert a['actionType']=='DISPLAY_ENEMY_INFO';exact(ctl['metadata']['native_action'],a);assert ctl['ack_policy']=='immediate'
     ow['fragments'].append(of)
    waves.append(ow)
   exact(s['timeline'],{'policy':'managed_clear','negative_timeout_policy':'wait_for_clear','waves':waves});assert count==births==meta['source_births'] and ack==popups;assert not n['branches'] and not any(n['predefines'].values()) and not n.get('hardPredefines');exact([x['raw'] for x in s['metadata']['rune_policy']],n['runes']);assert not any(x['active'] for x in s['metadata']['rune_policy'])
   facts.update({'births':count,'external_ACK_nodes':ack,'native_routes':len(n['routes']),'used_route_indices':sorted(set(routes)),'native_typed_leaves':len(leaf_types(n)),'source_sha':pin});results.append({'stage':stage,'passed':True,'facts':facts})
  except Exception as e:results.append({'stage':stage,'passed':False,'facts':facts,'error':str(e),'traceback':traceback.format_exc()})
 guards={str(p):sha(p) for p in set(paths)};report={'schema':'ark-sim/chapter0-stage-input-static-peer/v1','source_input_approved':all(x['passed'] for x in results),'results':results,'current_source_guards':guards,'simulation_executed':False,'whole_or_model_approved':False,'reference_boundaries':['Logical clock continues during story ACK; native UI/combat pause and click dwell method bodies not recovered. Blocker .3 is declared logical reference delay.','DISPLAY info immediate observation is not UI rendering proof.','Source attack timing cap/from ASPD divisor remains explicitly replaceable reference implementation, raw float32 cap retained.','Native docs and all action raw fields retained; unconverted optional metadata is not proof of client getter semantics.','Finite public deployment plan and actual ACK/prefix/whole acceptance require separate evidence.']};dest=out/'source.review.v1.json';assert not dest.exists();dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'approved':report['source_input_approved'],'results':results,'sha':sha(dest)}));return 0 if report['source_input_approved'] else 1
if __name__=='__main__':raise SystemExit(main())
