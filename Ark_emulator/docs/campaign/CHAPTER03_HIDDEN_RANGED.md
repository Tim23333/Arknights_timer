# Three hidden enemy producers share M49 without sharing their stats

New content package `packages/campaign/chapter03_visibility/three_hidden_sensor.model.json` SHA256 `32263bd62eae9f3c4d738a219f5e1a172ad87d2d16922e7290d70817497d7ceb` adds two exact source units to frozen Lurker/Sensor `939ab55dea20624639a37d8a63c38cc015c2b8d9c214c0cdf6a3380f22821fe1`. It does not modify M49 core or that parent package. New generator `tools/build_chapter03_hidden_ranged.py` passed `--check`.

Source inventory is the frozen actual `chapter03_sources/native.reference.json` SHA256 `d6a1d5294e1419d6ee41022efa1ef93a0ad44b6effb80c4bdfcf7fc3e7cd1e35`; all source locks are reread. Exact variants are `enemy_1019_jshoot@0/057fe36d73900a6f` and `enemy_1023_jmage@0/607486c1c102444f`. Their raw ToggleablePassiveBuffAbility points to a checker with initial1, disableWhenBlocked1, restoreDelay3, **disableWhenAttack0**. Lurker's corresponding attack switch is1. Consequently the new two controller recipes have no attack-pulse subscriptions. Their ordinary firing does not expose them; only blocking and its release affect visibility. The underlying flag is INVISIBLE9, distinct from CAMOUFLAGE17.

| Source unit | HP | ATK | DEF | RES | Interval | Range | Attack clock | Projectile | Combat |
|---|---:|---:|---:|---:|---:|---:|---|---|---|
| jshoot | 1800 | 260 | 100 | 20 | 2.7 | 2.2 | f16 | crossbow_big, speed10/lifetime5 | actual MeleeAttack physical/f16 |
| jmage | 2200 | 350 | 80 | 50 | 4 | 2 | f19 | magic_ball, speed10/lifetime10 | actual MeleeAttack arts/f19 |

Both are source WALK units with mass1, blockVolume1, born0, no HP/SP recovery and no stun immunity. Their actual mover fields are8/10. Source RangedAttack and MeleeAttack have their own exact Animator/PPtr/frame records; no Lurker frame/HP substitution is used.

Each unit owns separate normal and combat abilities. Unblocked ordinary targeting uses the exact source selector options and fixed DB radius; blocked combat uses `blocked_only` candidates and requires an actual source blocked relation. The pure decision reads that relation and its declared cast groups. This structural candidate restriction makes another actor's taunt magnitude irrelevant to combat primary choice; no finite blocked priority weight is introduced. The producer's invisibility is a candidate-side permission rule and does not prevent it from selecting a visible hero or launching attacks.

Fresh six cases passed in21.54 seconds under actual frozen M49 `e6d05494938ef71a20091b287475fc3e297b9831366a030b349b319a7df515a4`. One-cell ranged packets hit at19/22, respectively, for160 physical against DEF100 and262.5 arts against RES25. Hidden9 remains through firing and a hero's direct targeting attempt is refused. True blocking removes9; combat uses direct source f16/f19, then release restores after90 ticks without an attack pulse. Each source also becomes normally targetable through actual Sensor immunity9 while its underlying hidden Buff persists. Every battle case has recorded commands, ordered disk checkpoint continuation and replay equality.

Report `validation/campaign/chapter03_hidden/final.json` SHA256 `3d9471bee88b961b3b2691250e093a4f6d6d7c379dfa54b13a6ad76577dea618` records source/package/helper/core bytes identical before/after and actual serialized fixture inputs with seeds. The package includes the existing partial Sensor, so terrain/card/predefine integration remains separate. Exact checker dispatch/native getter correspondence and user client feedback remain explicit; no whole stage, promotion or formal receipt is asserted.
