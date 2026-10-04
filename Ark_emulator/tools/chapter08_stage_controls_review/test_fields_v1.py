from copy import deepcopy
import pytest
from tools.chapter08_stage_controls_review.audit_fields_v3 import audit,ROOT,read
STAGE=ROOT/'packages/campaign/chapter08_stage_models/level_main_08-17.native_draft.v2.json'
OVERLAY=ROOT/'packages/campaign/chapter08_stage_models/level_main_08-17.native_draft.v2.life99999.v1.json'
def test_original_raw_story_Opera_stage_allfields_source_admission():assert audit()['native_births']==44
@pytest.mark.parametrize('field',['hp','clock','DP','route','birth','RuneOption','roster'])
def test_onlylife_goal_cannot_authorize_other_source_edits(field):
 p=read(STAGE);q=read(OVERLAY)
 if field=='hp':next(d for d in p['definitions'] if d['id']=='unit/ch8/bsnake/cadb87696bef4de2')['components']['resources']['hp']['initial']=49999
 elif field=='clock':next(d for d in p['definitions'] if d['id']=='ability/ch8/bsnake/normal/phase0')['duration_seconds']=.1
 elif field=='DP':p['scenarioDraft']['resources']['dp']['initial']=16
 elif field=='route':next(a for w in p['scenarioDraft']['timeline']['waves'] for f in w['fragments'] for a in f['actions'] if a['kind']=='spawn')['spawn']['route']['checkpoints'][0]['time']=1
 elif field=='birth':next(a for w in p['scenarioDraft']['timeline']['waves'] for f in w['fragments'] for a in f['actions'] if a['kind']=='spawn')['count']+=1
 elif field=='RuneOption':p['scenarioDraft']['metadata']['native_options']['moveMultiplier']=1
 else:p['scenarioDraft']['roster'].pop()
 with pytest.raises(AssertionError):audit(p,q)
