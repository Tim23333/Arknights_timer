"""Immutable reference download/cache gates, tested without network access."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('campaign_reference',ROOT/'tools/fetch_campaign_reference.py')
tool=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)
LID='level_main_00-10'


def body(level_id=None):
    return json.dumps({'levelId':level_id,'mapData':{'map':[[0,1]],'tiles':[]},
                       'routes':[],'waves':[]}).encode('utf8')


def downloader(data):
    def download(url,path):
        assert url==tool.source_url(LID)
        path.write_bytes(data)
    return download


@pytest.mark.parametrize('value',['../level_main_00-10','level_main_00-10?x=1','level_main_00-10#s',
                                  'level_easy_00-10','LEVEL_main_00-10','level_main_00-10/../x'])
def test_only_selected_asset_ids_can_form_urls(value):
    with pytest.raises(tool.FetchError,match='Invalid selected native'):
        tool.source_url(value)


def test_unlocked_file_is_download_verified_before_locking(tmp_path):
    content=body()
    destination=tmp_path/(LID+'.json')
    destination.write_bytes(content)
    entry,state=tool.fetch_one(LID,tmp_path,download=downloader(content))
    assert state=='downloaded'
    assert entry['sha256']==tool.digest(content)
    assert entry['size']==len(content)
    assert entry['native_level_id'] is None
    assert entry['id_binding']=='pinned_asset_url_and_filename'
    assert entry['commit']==tool.COMMIT


def test_cache_checksum_mismatch_refuses_network_and_replacement(tmp_path):
    content=body()
    entry=tool.entry_for(content,LID)
    destination=tmp_path/(LID+'.json')
    destination.write_bytes(b'tampered')
    def forbidden(*args):
        pytest.fail('Corrupt locked cache must fail before network access')
    with pytest.raises(tool.FetchError,match='checksum mismatch'):
        tool.fetch_one(LID,tmp_path,entry,download=forbidden)
    assert destination.read_bytes()==b'tampered'


def test_explicit_refresh_repairs_cache_after_valid_download(tmp_path):
    content=body()
    entry=tool.entry_for(content,LID)
    destination=tmp_path/(LID+'.json')
    destination.write_bytes(b'tampered')
    actual,state=tool.fetch_one(LID,tmp_path,entry,refresh=True,download=downloader(content))
    assert actual==entry and state=='refreshed'
    assert destination.read_bytes()==content


@pytest.mark.parametrize('bad_body',[b'<html>404</html>',body('level_main_00-11')])
def test_invalid_download_never_replaces_existing_bytes(tmp_path,bad_body):
    old=body()
    destination=tmp_path/(LID+'.json')
    destination.write_bytes(old)
    with pytest.raises(tool.FetchError):
        tool.fetch_one(LID,tmp_path,refresh=True,download=downloader(bad_body))
    assert destination.read_bytes()==old
    assert list(tmp_path.iterdir())==[destination]


def test_existing_unlocked_different_cache_requires_refresh(tmp_path):
    destination=tmp_path/(LID+'.json')
    destination.write_bytes(b'old unknown source')
    with pytest.raises(tool.FetchError,match='unlocked cache differs'):
        tool.fetch_one(LID,tmp_path,download=downloader(body()))
    assert destination.read_bytes()==b'old unknown source'


def test_missing_cache_download_must_match_recorded_sha(tmp_path):
    entry=tool.entry_for(body(),LID)
    other=body(LID)  # Valid identity/schema but changed immutable body.
    with pytest.raises(tool.FetchError,match='disagrees with lock'):
        tool.fetch_one(LID,tmp_path,entry,download=downloader(other))
    assert not (tmp_path/(LID+'.json')).exists()


def test_manifest_url_and_commit_are_pinned(tmp_path):
    entry=tool.entry_for(body(),LID)
    entry['source_url']=entry['source_url'].replace(tool.COMMIT,'master')
    with pytest.raises(tool.FetchError,match='URL/commit mismatch'):
        tool.validate_lock(entry,LID)


def test_curl_preserves_tls_verification_and_https_redirects(monkeypatch,tmp_path):
    calls=[]
    def run(arguments,**kwargs):
        calls.append((arguments,kwargs))
        return SimpleNamespace(returncode=0,stderr='')
    monkeypatch.setattr(tool.subprocess,'run',run)
    tool.curl_download(tool.source_url(LID),tmp_path/'body')
    arguments,kwargs=calls[0]
    assert arguments[0]=='curl.exe'
    assert '--insecure' not in arguments and '-k' not in arguments
    assert arguments[arguments.index('--proto')+1]=='=https'
    assert arguments[arguments.index('--proto-redir')+1]=='=https'
    assert arguments[-1]==tool.source_url(LID)
    assert not kwargs.get('shell',False)


def test_actual_manifest_covers_selected_files_and_exact_hashes():
    directory=ROOT/'packages/campaign/native_reference'
    manifest=tool.load_manifest(directory/'reference.manifest.json')
    catalog=json.loads((ROOT/'packages/campaign/mainline_catalog.json').read_text(encoding='utf8'))
    selected={r['level_id'] for r in catalog['stages'] if r['selected']}
    assert set(manifest['files'])==selected
    assert len(selected)==36
    for lid in selected:
        assert tool.entry_for((directory/(lid+'.json')).read_bytes(),lid)==manifest['files'][lid]
