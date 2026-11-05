# Batch 1: 10 GMod player models (6 Nov 2026)

Source: Steam Workshop, Garry's Mod, tag Model, top rated (this week, pages 1-2). Converted with `pipeline.py catalog.json --compile`
(uniform scale, no stretching; arms and hands seated on CS2's pivots; wrist blend; torso recentred). Output: content addon
`gmod_playermodels`, `models/player/gmod/<slug>/<slug>.vmdl`. Every vmdl compiled with `resourcecompiler` (no warnings).
**Not yet tried in game** (CS2 `SetModel`, animations, ragdoll, first-person arms): that's the next check.

Rights: workshop authors keep theirs, and most of these are themselves ports of characters from films, TV and games. Local testing only
unless the author agrees ([gmod-playermodels.md, Rights](../../docs/creation/gmod-playermodels.md#rights)).

| slug | workshop item | model | tris | scale | worst limb joint vs CS2 (u) | torso moved back (u) | compile | notes |
|---|---|---|---|---|---|---|---|---|
| `gus_fring` | [[Breaking Bad] Gustavo Fring](https://steamcommunity.com/sharedfiles/filedetails/?id=3412497213) by Azkabath | `models/gustavo_fring/gustavo_suit.mdl` | 53714 | 1.038 | 2.5 | -2.5 | OK | ok |
| `gordon_restored` | [Gordon Freeman Restored (PM/NPC)](https://steamcommunity.com/sharedfiles/filedetails/?id=3320656757) by Gordon Freakman | `models/gfreakman/gordonf_highpoly.mdl` | 19929 | 1.038 | 2.5 | -1.0 | OK | lens glass2 made dark translucent glass (no texture in the item) |
| `caste_graffiti` | [CASTE Graffiti Playermodel + NPC](https://steamcommunity.com/sharedfiles/filedetails/?id=3673818635) by VHBC | `models/playermodels/caste_pm.mdl` | 4997 | 1.038 | 2.5 | -0.4 | OK | ok |
| `vart_agent` | [Valve Account Recovery Taskforce [PM]](https://steamcommunity.com/sharedfiles/filedetails/?id=3626678503) by Fozer_T89 | `models/fozer/v.a.r.t/valveaccountrecoverytaskforce_pm.mdl` | 98787 | 1.038 | 2.6 | -2.4 | OK | bulky torso: chest 5.2 u further forward than a stock agent; CS2 hand poses (two-handed weapons) will clip into it; hand_R inside the torso in the CS2 preview pose (chest surface 3.5 u in front of the wrist) |
| `gordon_promo` | [[PM+NPC] Promo Art Gordon Freeman](https://steamcommunity.com/sharedfiles/filedetails/?id=3361691203) by Vuthakral | `models/vuthakral/hl1/characters/gordon_promo.mdl` | 5512 | 1.038 | 2.5 | -1.1 | OK | ok |
| `thing_macready` | [The Thing (2002) Humans (Playermodels & Ragdolls)](https://steamcommunity.com/sharedfiles/filedetails/?id=3456405055) by Kapitano Krunchyman | `models/thething2002/pm_macready.mdl` | 1674 | 1.038 | 2.7 | -0.1 | OK | ok |
| `dr_house` | [House M.D: Dr Gregory House](https://steamcommunity.com/sharedfiles/filedetails/?id=3419019710) by Bunny | `models/bunny/doctor_house/doctor_house.mdl` | 37867 | 1.038 | 2.9 | -2.3 | OK | ok |
| `css_swat` | [CSS ENHANCED SPECIAL FORCES /// SEB & SWAT /// PLAYERMODEL](https://steamcommunity.com/sharedfiles/filedetails/?id=3387382988) by Gruchk | `models/css_seb_swat/css_swat.mdl` | 12546 | 1.038 | 2.6 | -3.7 | OK | bulky torso: chest 5.8 u further forward than a stock agent; CS2 hand poses (two-handed weapons) will clip into it; hand_R inside the torso in the CS2 preview pose (chest surface 3.8 u in front of the wrist); lens ct_urban_glass made dark translucent glass (no texture in the item) |
| `leon_re4` | [Resident Evil 4 (2005) Leon S. Kennedy Playermodel](https://steamcommunity.com/sharedfiles/filedetails/?id=3735230220) by acres | `models/re4/leon/leon_pm.mdl` | 8586 | 1.056 | 5.0 | -1.2 | OK | ok |
| `rotd_guard` | [Road of The Dead: Military](https://steamcommunity.com/sharedfiles/filedetails/?id=3415757440) by pvnished dej | `models/dejtriyev/rotd/ec_national_guard.mdl` | 10757 | 1.038 | 2.6 | -2.1 | OK | ok |

The two warnings are armour bulk: chests 5-6 u deeper than a stock agent's, so CS2's two-handed weapon poses put the right hand partly inside
the vest. Not fixable without reshaping the model; use them knowing that, or pick slimmer models.

Reviewed: contact sheet, every `_bind` / `_posed` picture and every `_hands` sheet (hands in CS2's pose, wrists bent back 60 degrees).
Minor: a slight poke where a hand bends back hard against a stiff cuff; MacReady's mitten-like hands are the 2002 source mesh.

## Looked at, not used

| id | item | why |
|---|---|---|
| 3621630161 | Christmas Sweater Citizens (Playermodel & Ragdoll) | face, eye and mouth textures are HL2 citizen textures not in the item (came out flat grey in batch 1 run 1) |
| 3374404008 | BAGGY JEANS SKELETON / Playermodel | materials come from base-game (HL2/GMod) content that is not in the item |
| 3682482439 | Resident Evil: Requiem - Former Umbrella Security Service (The Connections) [PMS] | 272k-308k vertices per model (680 MB item): too heavy without decimation |
| 3716275712 | Roscoe the Friendly Playermodel (and Ragdoll) | 43 u tall (head joint 32 u): would need 2.2x scale, not CS2-sized |
| 3698609418 | [Breaking Bad] Saul Goodman | spare: self-contained and CS2-sized, not needed for the first 10 |
| 3452810040 | Left 4 Dead styled soldier (Playermodel/Ragdoll) | spare: self-contained and CS2-sized, not needed for the first 10 |
| 3367031890 | [PM] H.E.V. MK-3 NEW | spare: self-contained and CS2-sized, not needed for the first 10 |
