# Run once current-content independent admission has passed.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$pythonPath = Join-Path (Split-Path $projectRoot -Parent) '.venv\Scripts\python.exe'
Push-Location -LiteralPath $projectRoot
try {
    & $pythonPath tools/run_campaign_disk_runthrough_v20.py `
      --runtime-root ../unpack_work/campaign_c9_finale_joint_v1_candidate `
      --package packages/campaign/chapter09_stage_models/level_main_09-17.native_draft.v3.life99999.finite_run_v1.json `
      --commands scenarios/campaign/chapter09/level_main_09-17/public_plan_v2_finite/commands.json `
      --output validation/campaign/runthrough/09_19_cd873_source_v3_finite_v1.json `
      --expected-core cd873dbff6ef66d9a17605ab6b02b6cc5a427090156577bd87dedd5bab428e18 `
      --evidence-helper tools/candidates/m77_event_storage/campaign_streaming_evidence_v14.py `
      --helper-sha256 2029677af14d702ef917522be3dd2d348b906366759905af41e6562399df29e9 `
      --providers-module tools/chapter09_stage919_assembly_v1/providers_v3.py `
      --providers-sha256 dc06aa864bea78ea2856d24264a50741e5712269a47bd33961e1bc9fa890d04f `
      --public-dialogue-driver --checkpoint-at 700 --max-ticks 30000
    $runExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $runExitCode
