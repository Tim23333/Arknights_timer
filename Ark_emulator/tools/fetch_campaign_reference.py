"""Fetch immutable native campaign JSON through curl, with a checksum lock.

TLS validation remains enabled. Existing locked bytes are never silently
replaced. --refresh is the explicit operation for replacing an invalid cache.
No GitHub API or account/profile metadata is collected.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "56aee3d6c5a29c3a0d192456d70d14252cbb0804"
REPOSITORY = "ArknightsAssets/ArknightsGamedata"
LEVEL_ID = re.compile(r"level_main_\d{2}-\d{2}$")
BASE_URL = f"https://raw.githubusercontent.com/{REPOSITORY}/{COMMIT}/cn/gamedata/levels/obt/main/"


class FetchError(ValueError):
    pass


def source_url(level_id):
    if not isinstance(level_id,str) or not LEVEL_ID.fullmatch(level_id):
        raise FetchError(f"Invalid selected native level ID: {level_id!r}")
    return BASE_URL+level_id+'.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_native(data, level_id):
    source_url(level_id)
    try:
        value=json.loads(data.decode('utf-8-sig'))
    except (UnicodeDecodeError,json.JSONDecodeError) as exc:
        raise FetchError(f"{level_id}: downloaded body is not UTF-8 JSON") from exc
    if not isinstance(value,dict) or 'levelId' not in value:
        raise FetchError(f"{level_id}: native LevelData ID field missing")
    # Standard exports use levelId:null: the native identity is their immutable
    # asset path, not an internal string. Never fabricate that internal ID.
    if value['levelId'] not in (None,level_id):
        raise FetchError(f"{level_id}: native levelId mismatch {value['levelId']!r}")
    for key,kind in (('mapData',dict),('routes',list),('waves',list)):
        if not isinstance(value.get(key),kind):
            raise FetchError(f"{level_id}: invalid native LevelData {key}")
    grid=value['mapData'].get('map')
    if not isinstance(grid,list) or not grid or not all(isinstance(row,list) and row for row in grid):
        raise FetchError(f"{level_id}: invalid native map grid")
    if any(len(row)!=len(grid[0]) for row in grid):
        raise FetchError(f"{level_id}: nonrectangular native map grid")
    return value


def entry_for(data,level_id):
    native=validate_native(data,level_id)
    url=source_url(level_id)
    checksum=digest(data)
    return {'source_url':url,'commit':COMMIT,'sha256':checksum,'size':len(data),
            'cache_identity':digest((url+'\n'+checksum).encode('utf8')),
            'native_level_id':native['levelId'],
            'id_binding':'internal_id' if native['levelId'] else 'pinned_asset_url_and_filename'}


def validate_lock(entry,level_id):
    if not isinstance(entry,dict) or entry.get('source_url')!=source_url(level_id) or entry.get('commit')!=COMMIT:
        raise FetchError(f"{level_id}: manifest source URL/commit mismatch")
    checksum=entry.get('sha256')
    if not isinstance(checksum,str) or not re.fullmatch('[0-9a-f]{64}',checksum):
        raise FetchError(f"{level_id}: invalid manifest SHA256")
    if not isinstance(entry.get('size'),int) or entry['size']<=0:
        raise FetchError(f"{level_id}: invalid manifest size")
    if entry.get('cache_identity')!=digest((entry['source_url']+'\n'+checksum).encode('utf8')):
        raise FetchError(f"{level_id}: cache identity mismatch")


def curl_download(url,path):
    # Argument vector avoids shell interpolation; URL is built from a fixed pin.
    result=subprocess.run(['curl.exe','--fail','--location','--silent','--show-error',
                           '--proto','=https','--proto-redir','=https','--tlsv1.2',
                           '--connect-timeout','15','--max-time','60','--output',str(path),url],
                          capture_output=True,text=True,timeout=65)
    if result.returncode:
        raise FetchError(f"curl failed ({result.returncode}): {result.stderr.strip()[:400]}")


def fetch_one(level_id,directory,locked_entry=None,refresh=False,download=curl_download):
    url=source_url(level_id)
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    destination=directory/(level_id+'.json')
    if locked_entry is not None:
        validate_lock(locked_entry,level_id)
    if destination.exists() and locked_entry is not None and not refresh:
        data=destination.read_bytes()
        if digest(data)!=locked_entry['sha256'] or len(data)!=locked_entry['size']:
            raise FetchError(f"{level_id}: cache checksum mismatch; use explicit --refresh")
        actual=entry_for(data,level_id)
        if actual!=locked_entry:
            raise FetchError(f"{level_id}: cache metadata mismatch; use explicit --refresh")
        return actual,'verified_cache'
    descriptor,tmp_name=tempfile.mkstemp(prefix='.'+level_id+'.',suffix='.download',dir=directory)
    os.close(descriptor)
    temporary=Path(tmp_name)
    try:
        download(url,temporary)
        data=temporary.read_bytes()
        actual=entry_for(data,level_id)
        if locked_entry is not None and not refresh and actual!=locked_entry:
            raise FetchError(f"{level_id}: pinned download disagrees with lock; use explicit --refresh")
        if destination.exists() and not refresh and destination.read_bytes()!=data:
            raise FetchError(f"{level_id}: existing unlocked cache differs from pinned download; use explicit --refresh")
        os.replace(temporary,destination)
        return actual,'refreshed' if refresh else 'downloaded'
    finally:
        temporary.unlink(missing_ok=True)


def load_manifest(path):
    if not path.exists():
        return {'schema':'ark_sim.campaign_reference_manifest.v1','repository':REPOSITORY,'commit':COMMIT,'files':{}}
    manifest=json.loads(path.read_text(encoding='utf8'))
    if manifest.get('schema')!='ark_sim.campaign_reference_manifest.v1' or manifest.get('repository')!=REPOSITORY or manifest.get('commit')!=COMMIT:
        raise FetchError('Reference manifest identity mismatch')
    if not isinstance(manifest.get('files'),dict):
        raise FetchError('Reference manifest files must be an object')
    for name,entry in manifest['files'].items():
        validate_lock(entry,name)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog',type=Path,default=ROOT/'packages/campaign/mainline_catalog.json')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'packages/campaign/native_reference')
    parser.add_argument('--refresh',action='store_true')
    parser.add_argument('--jobs',type=int,default=4)
    args=parser.parse_args()
    if not 1<=args.jobs<=8:
        parser.error('--jobs must be between 1 and 8')
    manifest_path=args.output_dir/'reference.manifest.json'
    manifest=load_manifest(manifest_path)
    rows=json.loads(args.catalog.read_text(encoding='utf8'))['stages']
    ids=[r['level_id'] for r in rows if r['selected']]
    if len(ids)!=len(set(ids)):
        raise FetchError('Selected catalog has duplicate native level IDs')
    for lid in ids:
        source_url(lid)
    failures=[]
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures={pool.submit(fetch_one,lid,args.output_dir,manifest['files'].get(lid),args.refresh):lid for lid in ids}
        for future in as_completed(futures):
            lid=futures[future]
            try:
                entry,state=future.result()
                manifest['files'][lid]=entry
                print(f'{lid}: {state}',flush=True)
            except (FetchError,OSError,subprocess.TimeoutExpired) as exc:
                failures.append({'level_id':lid,'error':str(exc)})
                print(f'{lid}: FAILED {exc}',flush=True)
    # Manifest is written atomically only after all successful bodies passed
    # JSON/schema/identity validation. Failed entries retain their old locks.
    args.output_dir.mkdir(parents=True,exist_ok=True)
    descriptor,tmp_name=tempfile.mkstemp(prefix='.reference.manifest.',suffix='.tmp',dir=args.output_dir)
    os.close(descriptor)
    temporary=Path(tmp_name)
    try:
        manifest['files']=dict(sorted(manifest['files'].items()))
        temporary.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        os.replace(temporary,manifest_path)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps({'selected':len(ids),'locked':sum(lid in manifest['files'] for lid in ids),'failures':failures},ensure_ascii=False))
    return 1 if failures else 0


if __name__=='__main__':
    raise SystemExit(main())
