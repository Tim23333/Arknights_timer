"""Bounded immutable payload sharing. Hash collisions never imply equality.

This is storage only: order/types/signed-zero are preserved, no trace is cut.
The byte budget deliberately sums whole descendant sizes per entry (including
aliases repeatedly), thus overcounts sharing. OrderedDict bookkeeping is bounded
separately by entry count; allocator/RSS are not a byte-budget promise.
"""
from collections import OrderedDict
from collections.abc import Mapping
import hashlib
import struct
import sys
from ark_sim.contracts.models import FrozenMapping,FrozenTuple,freeze

def exact_equal(left,right):
    if left is right:return True
    if type(left) is not type(right):return False
    if type(left) is float:return struct.pack('>d',left)==struct.pack('>d',right)
    if isinstance(left,Mapping):
        return len(left)==len(right) and all(ka==kb and exact_equal(va,vb) for (ka,va),(kb,vb) in zip(left.items(),right.items()))
    if isinstance(left,tuple):return len(left)==len(right) and all(exact_equal(a,b) for a,b in zip(left,right))
    return left==right

class PayloadInterner:
    def __init__(self,max_entries=65536,max_weight=32*1024*1024):
        if type(max_entries) is not int or max_entries<0 or type(max_weight) is not int or max_weight<0:raise ValueError('intern cache bounds must be nonnegative integers')
        self.max_entries=max_entries;self.max_weight=max_weight;self._entries=OrderedDict();self.weight=0;self.hits=0;self.misses=0;self.collisions=0;self.evictions=0
    def clear(self):
        self._entries.clear();self.weight=0
    def _fingerprint(self,kind,parts):
        digest=hashlib.sha256(kind)
        for part in parts:digest.update(struct.pack('>Q',len(part)));digest.update(part)
        return digest.digest()
    def _reuse(self,key,value,deep_size):
        existing=self._entries.get(key)
        if existing is not None:
            if exact_equal(existing[0],value):
                self.hits+=1;self._entries.move_to_end(key);return existing[0]
            self.collisions+=1;self.weight-=existing[1];del self._entries[key]
        self.misses+=1
        # Include retained key/entry tuple and a conservative per-slot allowance.
        weight=deep_size+sys.getsizeof(key)+sys.getsizeof((value,0))+128
        if not self.max_entries or weight>self.max_weight:return value
        while self._entries and (len(self._entries)>=self.max_entries or self.weight+weight>self.max_weight):
            _,entry=self._entries.popitem(last=False);self.weight-=entry[1];self.evictions+=1
        self._entries[key]=(value,weight);self.weight+=weight;return value
    def intern(self,value):
        """Only accept a fully validated/frozen payload from EventLog boundary."""
        memo={}
        def node(v):
            kind=type(v)
            if kind is FrozenMapping or kind is FrozenTuple:
                ident=id(v)
                if ident in memo:return memo[ident]
                if kind is FrozenMapping:
                    items={};parts=[];deep=sys.getsizeof(v)+sys.getsizeof(v._data)+(sys.getsizeof({})+128*len(v))
                    unchanged=True
                    for key,child in v.items():
                        new_key,key_hash,key_size=node(key);new_child,child_hash,child_size=node(child);items[new_key]=new_child;parts.extend((key_hash,child_hash));deep+=key_size+child_size;unchanged=unchanged and new_key is key and new_child is child
                    candidate=v if unchanged else freeze(items);fingerprint=self._fingerprint(b'map',parts)
                else:
                    children=[];parts=[];deep=sys.getsizeof(v);unchanged=True
                    for child in v:
                        canonical,child_hash,child_size=node(child);children.append(canonical);parts.append(child_hash);deep+=child_size;unchanged=unchanged and canonical is child
                    candidate=v if unchanged else freeze(children);fingerprint=self._fingerprint(b'array',parts)
                result=(self._reuse(fingerprint,candidate,deep),fingerprint,deep);memo[ident]=result;return result
            if kind is str:parts=[v.encode('utf8','surrogatepass')];tag=b'str'
            elif kind is float:parts=[struct.pack('>d',v)];tag=b'float'
            elif kind is int:parts=[str(v).encode('ascii')];tag=b'int'
            elif kind is bool:parts=[b'1' if v else b'0'];tag=b'bool'
            elif v is None:parts=[];tag=b'null'
            else:raise ValueError('payload interning requires validated primitive/frozen nodes')
            fingerprint=self._fingerprint(tag,parts);deep=sys.getsizeof(v)
            return (self._reuse(fingerprint,v,deep),fingerprint,deep)
        return node(value)[0]
    def statistics(self):
        return {'entries':len(self._entries),'weighted_deep_byte_upper_estimate':self.weight,'max_entries':self.max_entries,'max_weight':self.max_weight,'hits':self.hits,'misses':self.misses,'hash_collisions_checked':self.collisions,'evictions':self.evictions}
