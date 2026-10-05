# Run only after the V5 source, prefix and independent admission gates pass.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$pythonPath = Join-Path (Split-Path $projectRoot -Parent) '.venv\Scripts\python.exe'
Push-Location -LiteralPath $projectRoot
try {
    & $pythonPath tools/run_campaign_disk_runthrough_v20.py `
      --runtime-root ../unpack_work/campaign_c9_duspfr_v1_candidate `
      --package packages/campaign/chapter09_stage_models/level_main_09-16.native_draft.v5.life99999.finite_run_v1.json `
      --commands scenarios/campaign/chapter09/level_main_09-16/public_plan_v1_finite/commands.json `
      --output validation/campaign/runthrough/09_18_2c38_ruin_v5_finite_v1.json `
      --expected-core 2c385c9c4a9e383988a3ff8d8d96827f0e473dde0630a3d6d92aa35c5f0dccb0 `
      --evidence-helper tools/candidates/m77_event_storage/campaign_streaming_evidence_v14.py `
      --helper-sha256 2029677af14d702ef917522be3dd2d348b906366759905af41e6562399df29e9 `
      --providers-module tools/chapter09_stage_assembly_v1/providers_v5.py `
      --providers-sha256 4dc978504ec3da22bb2dc42c6117dbc41f91ed653856343db0f2f77c72ea5c39 `
      --public-dialogue-driver --checkpoint-at 700 --max-ticks 30000
    $runExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $runExitCode
