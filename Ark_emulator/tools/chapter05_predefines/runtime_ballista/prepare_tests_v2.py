"""Preserve first failure fixture, create precise API/explicit-base-tile revision."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def main():
 here=Path(__file__).parent;source=here/'test_consumer.py';dest=here/'test_consumer_v2.py'
 if dest.exists():raise ValueError('Preserve tests')
 text=source.read_text(encoding='utf8');assert text.count('module.reference.json')==1;text=text.replace('module.reference.json','module.v2.reference.json',1);assert text.count("s.ctx.lifecycle.activate(")==1;text=text.replace("s.ctx.lifecycle.activate(","s.ctx.lifecycle.activate_predefined(",1)
 anchor="'map':{'rows':3,'cols':9},'seed'";assert text.count(anchor)==1;text=text.replace(anchor,"'map':{'rows':3,'cols':9,'tiles':[{'tileKey':'tile_road','buildableType':1,'passableMask':3} for _ in range(27)]},'seed'",1);dest.write_text(text,encoding='utf8',newline='');print(str(dest))
if __name__=='__main__':main()
