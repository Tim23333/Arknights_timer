"""Actual recursive source-file pins; recorded labels never authenticate themselves."""
import hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def verify(value):
    pins={}
    def walk(node):
        if isinstance(node,dict):
            locks=node.get('source_locks',{})
            if not isinstance(locks,dict):raise ValueError('Source locks must be a path/SHA mapping')
            for name,pin in locks.items():
                if type(name) is not str or not name or type(pin) is not str or len(pin)!=64:
                    raise ValueError('Source lock path and SHA required')
                path=Path(name);candidates=[path] if path.is_absolute() else [ROOT/path,ROOT.parent/path]
                found=[p.resolve() for p in candidates if p.is_file()]
                if not found:raise ValueError('Missing actual source lock '+name)
                for actual in found:
                    got=hashlib.sha256(actual.read_bytes()).hexdigest()
                    if got!=pin:raise ValueError('Source lock bytes differ '+name)
                    pins[str(actual)]=pin
            for key,item in node.items():
                if key!='source_locks':walk(item)
        elif isinstance(node,list):
            for item in node:walk(item)
    walk(value);return pins
