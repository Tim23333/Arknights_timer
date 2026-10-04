from pathlib import Path
p=Path(__file__).with_name('verify_ore_mine_joint_v3.py')
s=p.read_text().replace("ore_mine_joint_v3'","ore_mine_joint_v4'")
s=s.replace("'instanceAlias':'ore','position':{'row':3,'col':3}","'instanceAlias':'ore','position':{'row':3,'col':4}")
s=s.replace("s.session.advance(236)","s.session.advance(236);print('actual firstdown/ore boundary236 reached',flush=True)")
s=s.replace("s.session.advance(1570)","s.session.advance(1570);print('actual rebirth boundary1806 reached',flush=True)")
s=s.replace("h=replay(s.program,s.export_replay(),providers=registry)","print('actual live/restore1961 reached; starting public head',flush=True);h=replay(s.program,s.export_replay(),providers=registry)")
p.with_name('verify_ore_mine_joint_v4.py').write_text(s,encoding='utf-8',newline='')
