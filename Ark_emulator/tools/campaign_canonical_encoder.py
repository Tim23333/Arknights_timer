"""Bounded canonical encoding cache for immutable shared event subtrees.

Every output byte matches the original streaming canonical encoder. Mutable
containers are never cached. Keys retain the object to prevent id reuse; LRU
bytes/entries and individual cache item size are explicit upper bounds.
"""
from collections import OrderedDict
from collections.abc import Mapping
import json
from types import MappingProxyType

class CanonicalEncoder:
    def __init__(self,max_entries=8192,max_bytes=8*1024*1024,max_item_bytes=32768):
        for value in (max_entries,max_bytes,max_item_bytes):
            if type(value) is not int or value<0:raise ValueError('Encoder cache bounds must be nonnegative integers')
        self.max_entries=max_entries;self.max_bytes=max_bytes;self.max_item_bytes=max_item_bytes
        self.cache=OrderedDict();self.retained_bytes=0;self.hits=0;self.misses=0
        # Runner selects its runtime before constructing an encoder. Importing
        # ark_sim at module load would accidentally bind the primary checkout.
        from ark_sim.contracts.models import FrozenMapping,FrozenTuple
        self.immutable_types=(FrozenMapping,FrozenTuple)

    def detach(self,value,memo=None,active=None):
        """Own container backing; public Frozen wrappers are still untrusted."""
        memo={} if memo is None else memo;active=set() if active is None else active
        kind=type(value)
        if kind in (str,bool,int,float,type(None)):return value
        if not isinstance(value,(Mapping,list,tuple)):raise ValueError('Canonical JSON requires JSON containers and scalars')
        key=id(value)
        if key in active:raise ValueError('Canonical JSON cannot contain a cycle')
        if key in memo:return memo[key]
        active.add(key)
        try:
            if isinstance(value,Mapping):
                if any(type(k) is not str for k in value):raise ValueError('Canonical JSON requires string object keys')
                result=self.immutable_types[0]({k:self.detach(v,memo,active) for k,v in value.items()})
            else:result=self.immutable_types[1]([self.detach(v,memo,active) for v in value])
            memo[key]=result;return result
        finally:active.remove(key)

    def _deep_immutable(self,value,active=None,memo=None):
        active=set() if active is None else active;memo={} if memo is None else memo
        kind=type(value)
        if kind in (str,int,float,bool,type(None)):return True
        if kind not in self.immutable_types:return False
        if isinstance(value,Mapping) and type(getattr(value,'_data',None)) is not MappingProxyType:
            return False
        key=id(value)
        if key in active:raise ValueError('Canonical JSON cannot contain a cycle')
        if key in memo:return memo[key]
        active.add(key)
        try:
            valid=all(type(k) is str and self._deep_immutable(v,active,memo) for k,v in value.items()) if isinstance(value,Mapping) else all(self._deep_immutable(v,active,memo) for v in value)
            # A large event stream must not retain an unbounded validation
            # index. Clearing changes traversal cost only, never trust rules.
            if len(memo)>=self.max_entries:memo.clear()
            if self.max_entries:memo[key]=valid
            return valid
        finally:active.remove(key)

    def _remember(self,key,value,encoded):
        weight=len(encoded)
        if not self.max_entries or weight>self.max_bytes:return
        while self.cache and (len(self.cache)>=self.max_entries or self.retained_bytes+weight>self.max_bytes):
            _,(_,old)=self.cache.popitem(last=False);self.retained_bytes-=len(old)
        self.cache[key]=(value,encoded);self.retained_bytes+=weight

    def chunks(self,value):
        # Validation memo lasts one top-level encoding only. A subsequent call
        # rechecks malformed public wrappers and observes mutable descendants.
        # Public MappingProxyType wrappers can retain externally writable dicts;
        # never carry encoded identity entries across separate API calls.
        self.cache.clear();self.retained_bytes=0
        # Generic values retain the original bounded streaming behavior. The
        # optimized owned snapshot boundary is limited to one journal record.
        from tools.campaign_streaming_evidence import chunks
        for part in chunks(value):yield part.encode('utf8')

    def records(self,records):
        """One synchronous export call; retain bounded cache between records."""
        self.cache.clear();self.retained_bytes=0
        for value in records:
            yield from self._chunks(self.detach(value),{})
            yield b'\n'

    def _chunks(self,value,validation_memo):
        # Public wrappers can be constructed with tuple.__new__ or their
        # backing manipulated. Exact outer type alone is not deep immutability.
        immutable=type(value) in self.immutable_types and self._deep_immutable(value,memo=validation_memo)
        key=id(value)
        entry=self.cache.get(key) if immutable else None
        if entry is not None and entry[0] is value:
            self.hits+=1;self.cache.move_to_end(key);yield entry[1];return
        if immutable:self.misses+=1
        pending=[];size=0;can_cache=immutable and bool(self.max_entries and self.max_bytes and self.max_item_bytes)
        for part in self._raw(value,validation_memo):
            if can_cache:
                size+=len(part)
                if size>self.max_item_bytes:can_cache=False;pending.clear()
                else:pending.append(part)
            yield part
        if can_cache:self._remember(key,value,b''.join(pending))

    def _raw(self,value,validation_memo):
        if isinstance(value,Mapping):
            if any(type(key) is not str for key in value):raise ValueError('Canonical JSON requires string object keys')
            yield b'{'
            for index,key in enumerate(sorted(value)):
                if index:yield b','
                yield json.dumps(key,ensure_ascii=False,allow_nan=False).encode('utf8');yield b':'
                yield from self._chunks(value[key],validation_memo)
            yield b'}'
        elif isinstance(value,(list,tuple)):
            yield b'['
            for index,item in enumerate(value):
                if index:yield b','
                yield from self._chunks(item,validation_memo)
            yield b']'
        else:
            yield json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf8')

    def statistics(self):
        return {'entries':len(self.cache),'encoded_bytes':self.retained_bytes,
            'max_entries':self.max_entries,'max_bytes':self.max_bytes,'max_item_bytes':self.max_item_bytes,
            'hits':self.hits,'misses':self.misses,
            'scope':'Encoded byte storage bound; Python object overhead is bounded by entries, not an RSS guarantee'}
