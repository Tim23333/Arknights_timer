# Ordered checkpoint revision over frozen M71

The M71 runtime core remains `15517b90969c61b15340929687092401b4a807b6a3f66d0d2135e780568c04aa`.
Existing v12, README, verification and benchmark evidence are preserved with
their original identity. This revision corrects the checkpoint **helper** only.

Actual reproduction uses Compiler/Engine/ResourceSystem from unchanged M71 and
the existing custom package with a controlled two-resource scenario. Resource
insertion order is `zeta, alpha`. After three ticks, v12 saved a sorted main
checkpoint, actual JSON reload changed that order to `alpha, zeta`, and 60 more
ticks produced 506 events with the first difference at
`/events/records/26/payload/trace/context/resource`: expected `zeta`, actual
`alpha`. The original helper, complete checkpoint and before/after full values
are retained in `validation/campaign/m71_event_storage/final_revision`.

Use `campaign_streaming_evidence_v13.write_checkpoint` and
`campaign_streaming_evidence_v13.load_checkpoint` for new durable checkpoints.
The writer calls the existing `tools.campaign_ordered_checkpoint.write_ordered`
against an exclusively reserved temporary path, verifies the actual bytes with
`load_bound`, and publishes the main file via an atomic exclusive `os.link` in
the same directory. An existing destination fails without overwriting it. A
publication race also preserves the winner's bytes. No unsupported filesystem
fallback silently replaces an existing file. Destination hard-link support is
required, and there is no fsync/crash-durability guarantee. Staging files are
removed on success/failure; independently sealed journal files may remain after
a later main-file publication failure and retain their complete evidence.

The consumer loads the actual published main-file bytes using its saved SHA
before Engine.restore. The sealed event journal still has its independently
bound path/SHA/count/size; M71 core restore verifies that file separately.
New ordered reload + 60 ticks preserves resource key order and complete events,
World, scheduler, RNG and snapshot values. Duplicate destination, race winner,
temporary cleanup and main-file tamper rejection were exercised.

`verify_revision.py` creates new evidence without overwriting previous reports.
Its start/end manifest includes every M68/M71 Python source, complete frozen
M71 JSON catalog, all storage helper/experiment Python files, actual consumed
custom package, ordered/canonical old helpers and the offline level JSON.
The new observation/export benchmark is executed inside those guards. The
derived controlled package and every resulting evidence file are separately
bound by SHA in the artifact manifest. This does not claim guards over unrelated
root packages or validation outputs concurrently written by other tasks.

Latest evidence is `final_revision/final_revision_guarded.json`. Earlier v12
failure and ordered-reload reports remain separate. This is a controlled real
ResourceSystem continuation test and small benchmark, not 36-stage completion,
fullstage performance or client accuracy.
