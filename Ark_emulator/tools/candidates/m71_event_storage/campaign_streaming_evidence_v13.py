"""Ordered, SHA-bound, exclusive checkpoint publishing over frozen M71.

Observation/export behavior delegates to preserved v12. Persisted execution
state must preserve mapping insertion order; canonical sorting is hash-only.
"""
from pathlib import Path
import importlib.util
import os
import uuid

from tools.campaign_ordered_checkpoint import write_ordered, load_bound

_spec = importlib.util.spec_from_file_location('m71_preserved_v12',
    Path(__file__).with_name('campaign_streaming_evidence_v12.py'))
_v12 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_v12)
observations = _v12.observations


def write_checkpoint(sim, path):
    """Publish an ordered complete JSON file at a new name, never replacing it.

    Stage in the destination directory, then os.link() atomically claims the
    final name. Existing final files are never truncated. Hard-link support on
    the destination filesystem is required; unsupported publication fails.
    The journal reference itself creates an independent exclusive sealed file.
    """
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(path)
    temporary = path.with_name('.'+path.name+'.tmp-'+uuid.uuid4().hex)
    with temporary.open('xb'):
        pass  # Reserve a unique owned staging path before invoking write_ordered.
    try:
        checkpoint = sim.checkpoint(event_reference=True)
        sha256 = write_ordered(temporary, checkpoint)
        # load_bound verifies actual persisted bytes before any publication.
        load_bound(temporary, sha256)
        os.link(temporary, path)  # Atomic create-if-absent; never os.replace().
        return {'path': str(path), 'sha256': sha256,
                'event_reference': checkpoint['kernel']['events']['reference'],
                'encoding': 'insertion-order UTF-8 JSON; complete checkpoint',
                'publication': 'exclusive atomic hard-link; no overwrite; no fsync guarantee'}
    finally:
        temporary.unlink(missing_ok=True)


def load_checkpoint(metadata):
    """Reload actual main-file bytes and verify their saved SHA before restore."""
    return load_bound(metadata['path'], metadata['sha256'])
