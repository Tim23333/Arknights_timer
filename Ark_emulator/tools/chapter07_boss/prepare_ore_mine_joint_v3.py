from pathlib import Path
p=Path(__file__).with_name('verify_ore_mine_joint_v2.py')
s=p.read_text().replace("ore_mine_joint_v2'","ore_mine_joint_v3'")
s=s.replace("'activation':{'mode':'manual','blocks_attacks':False}","'activation':{'mode':'manual'}")
p.with_name('verify_ore_mine_joint_v3.py').write_text(s,encoding='utf-8',newline='')
