# 7-18 archived-proof head recovery V21

This tool runs only the missing public replay head. The completed original
forward and durable-checkpoint proofs are reused as historical evidence from
the fixed archived result SHA and the pause/closeout receipts. Original raw
journals were deleted under the user's policy; they cannot be read or freshly
restored here. The tool does not rerun forward or checkpoint continuation.

Preflight creates no Simulation. It authenticates the exact four archive pins,
all 28 original source guards, the frozen82 implementation, actual Compiler
program fingerprint, original public command file and replay submission order,
and original external ACK ledger. Actual new head runtime fingerprint is
checked when execution creates its real Engine, not synthesized in preflight.

The successful prepared receipt is:

`validation/campaign/chapter07_head_recovery_v21/preflight.v1.json`

SHA256: `621db25bffc26190b8928384e00879641ce6402b32342b500f77666cbf4062d3`

After Root checks this exact receipt and current guards, execute through the
automatic-cleanup wrapper. This command has **not** been started during tool
preparation:

```powershell
../.venv/Scripts/python.exe tools/run_with_log_cleanup.py --run-dir E:/ArkSimLogs/runs/chapter07_head_recovery_v21_actual_v1 -- ../.venv/Scripts/python.exe tools/chapter07_head_recovery_v21/recover_head.py --execute --preflight validation/campaign/chapter07_head_recovery_v21/preflight.v1.json --preflight-sha 621db25bffc26190b8928384e00879641ce6402b32342b500f77666cbf4062d3 --output validation/campaign/chapter07_head_recovery_v21/head.actual.v1.json
```

All new raw journals and event exports use `ARKSIM_RUN_DIR` under fixed E runs
with the wrapper's real PID lease. Success and failure both keep the compact
result and invoke cleanup. The head submits every saved command at its original
`submitted_at`, with original `at` and `order`, including original public ACKs.
It does not dynamically generate additional ACK commands.

Completion requires exact equality of **snapshot, events, event_count and
continuation_state** against the original persisted observations. It also
checks all actual public accepted/rejected command records, final driver state,
enemy population conservation, and every source guard. No cache/value/context
fields are filtered. The frozen PublicAckDriver protocol is checked through a
streaming reconstruction of its entire checkpoint; this avoids materializing
seven million complete event objects in RAM. It does not call a different driver
to alter submission times or fabricate acknowledgements.

The old checkpoint pointer and journal hashes are archival provenance, not new
readable raw artifacts. A successful preflight is not successful head execution,
whole-stage acceptance or client verification. All original reports and helpers
remain immutable.
