"""A boundary calculation cannot change trace reuse after checkpoint restore."""
from ark_sim import Compiler,Engine
from ark_sim.tools.replay import replay
from tools.campaign_ordered_checkpoint import write_ordered,load_bound


def package():
    return {'schemaVersion':2,'manifest':{'requires':['preset/ark_standard']},
        'entities':[{'id':'unit/boundary/probe','kind':'entity','components':{
            'attributes':{'base':{'atk':37,'max_hp':101}},
            'resources':{'hp':{'initial':101,'capacity_attribute':'max_hp','role':'health'}},
            'spatial':{},'lifecycle':{'policy':'policy/ark_lifecycle'}}}],
        'scenarioDraft':{'id':'scene/boundary/cache','ruleset':'ruleset/ark_standard',
            'map':{'rows':1,'cols':1},'objectives':{},'initialEntities':[
                {'definition':'unit/boundary/probe','instanceAlias':'probe','position':{'row':0,'col':0}}]}}


def test_boundary_observer_cache_and_restore_exact_trace(tmp_path):
    p=Compiler().compile(package());s=Engine.create(p)
    def observe(session):
        assert s.ctx.attributes.value('probe','max_hp')==101
    s.session.add_boundary_system(observe)
    s.advance(3);file=tmp_path/'boundary3.json';pin=write_ordered(file,s.checkpoint())
    # Restore's systems must match the same external registered observer.
    r=Engine.create(p)
    r.session.add_boundary_system(lambda session:r.ctx.attributes.value('probe','max_hp'))
    r.session.restore(load_bound(file,pin)['kernel'])
    s.advance(4);r.advance(4)
    assert s.checkpoint()==r.checkpoint()


def test_segmented_and_continuous_boundaries_have_identical_calculations():
    p=Compiler().compile(package());s=Engine.create(p);r=Engine.create(p)
    s.session.add_boundary_system(lambda session:s.ctx.attributes.value('probe','max_hp'))
    r.session.add_boundary_system(lambda session:r.ctx.attributes.value('probe','max_hp'))
    s.advance(8)
    for _ in range(8):r.advance(1)
    assert s.checkpoint()==r.checkpoint()
