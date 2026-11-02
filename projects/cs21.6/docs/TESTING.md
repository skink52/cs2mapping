# First CS2 test (mg_cs16 v0.1.0)

Not run in CS2 yet. After building the map: `map mg_cs16` with bots (`bot_quota 10` for one map, `bot_quota 30` for two,
`bot_quota 50` for three). The console shows `[cs16] v0.1.0 ready: de_dust2, de_train, de_nuke` when the script loads,
and `[cs16] script time: ...` once a minute. After changing the script or HUD, reload the map fully (`disconnect`, then `map`).

## Things only CS2 can answer (the script has a setting for each)

1. **Damage numbers.** `DEBUG_DAMAGE: true` prints every hit. An AK-47 body shot at close range on someone without
   armour should take 36, a headshot 144. If headshots take 4x too much (576), CS2 multiplies the returned damage by the
   hit group again: set `CS2_REAPPLIES_HITGROUP: true`.
2. **Round results.** The console prints `[cs16] CS2 round end: team N, reason R` after each round; a `WARNING: expected
   ...` on that line means CS2 read the script's result differently. Wins are sent as 9 (T) / 8 (CT). A draw tries 10,
   then 2 (`DRAW_REASONS`); if a draw gives the round to a side, swap them. `EXACT_END_REASONS: true` would send
   bombed / defused / saved (1 / 7 / 12) so CS2's own win panel names the reason; try it once wins work.
3. **Two bombs at once.** With two or three maps running, can a second map's bomb be planted while one is already
   planted? If not, the bomb rounds need a scripted bomb (tell me).
4. **Menu clicks.** Does F open the buy menu with a mouse cursor, and do clicks buy? Does hovering a row show the 1.6
   picture and description on the right? If clicks don't work: `MENU_MOUSE: false` (W / S / E / R instead).
   Does CS2's B key open anything (with "Nobody can buy" in the map)?
5. **Radio sounds** ("Go go go", "Terrorists win"): heard by you only, once, not by the whole server.
6. **Player models.** The map build compiles `models/player/cs16/*` (a hidden prop of each sits under the map). Pick
   each class in the class menu: the 1.6 model should stand, run, crouch and hold weapons with CS2's animations, with
   no stretched or missing parts; shots should hit where the body is. If a model shows as an error, open its `.vmdl`
   in ModelDoc and check the compile messages; `MODELS_16: false` goes back to CS2 agents.
   In first person the hands should be 1.6's (black fingerless gloves, bare forearms) gripping CS2's guns, fingers
   wrapped around the grip, and the forearm ending under a rolled-up sleeve at the elbow. Players with a glove skin
   equipped may see their CS2 gloves instead (CS2 swaps those in itself).
   The bomb carrier should wear the 1.6 bomb pack and CTs with a defuse kit the kit: the script swaps to a second copy
   of the model (`<class>_pack.vmdl`) when that changes. If the swap disturbs the player (a twitch, a weapon reset),
   set `PACKS_16: false`.
7. **cvars**: `sv_jump_impulse`, `sv_accelerate` and the `mp_` settings set by the script take (`sv_jump_impulse` in the
   console should say 268.33).
8. **Vis.** The build should spend much less time in vis than before: half of the surface vis works through (mostly sky
   hidden inside 1.6 sky brushes) and more than half of the Low hint volume are gone. Walk each map: nothing should pop in or out
   of view, and the sky should never show a hole or the wrong sky. If something does, note where: the Low hint boxes
   (`visibility_hint`, vis group `cs16_gen`) can be widened.
9. **1.6 sounds compile.** If Hammer's build log complains about a `sounds/cs16/*.wav`, the extra data block the
   file transfer adds at the end of each wav is the suspect (the sound itself is untouched).

## Checklist

- [ ] Spawns: everyone lands on their map's spawns (top line says which map); 2 or 3 maps with enough bots.
- [ ] 1.6 HUD: health, armour, timer (hidden after the bomb is planted), money with +/-, ammo with the ammo icon;
      buy zone / C4 / defuser icons; `!hud classic|raised|off`. Shown over CS2's HUD in a sensible place?
- [ ] Buy menu: categories, team-only weapons, prices, "insufficient funds", buy time message after 90 s, rebuy.
      A bought gun has one magazine; primary ammo fills it.
- [ ] Money: +300 kills, round rewards next round, loss bonus.
- [ ] Rounds: elimination, bomb, defuse, time up (CTs win); with several maps the round ends when all are decided and
      CS2's score goes to the side with more maps.
- [ ] Knife: slash 15/20, stab 65, 195 from behind. HE grenade up to ~100. Falls hurt from lower heights than CS2.
- [ ] Sounds: 1.6 guns, knife, grenades, C4 beeps / plant / defuse / explosion.
- [ ] Bots buy and plant.
- [ ] Doors open (train, nuke), ladders climb, crates break when the bomb goes off.
- [ ] Radar shows the map you play on; the loading screen shows the 1.6 pictures; the map icon in the map list.
