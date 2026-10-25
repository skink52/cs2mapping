import { Instance } from "cs_script/point_script";

const T = 2, CT = 3;
const LOADOUT = {
  [T]:  ["weapon_awp", "weapon_glock"],        // Gewehr 98 + Luger P08
  [CT]: ["weapon_ssg08", "weapon_hkp2000"],    // Lee-Enfield + Colt M1911
};
const TICK = 0.25;
const pending = new Set();

function enforce(pawn, want) {
  for (const gear of [0, 1]) {
    for (let i = 0; i < 4; i++) {
      const w = pawn.FindWeaponBySlot(gear);
      if (!w || want.includes(w.GetClassName())) break;
      pawn.DestroyWeapon(w);
    }
  }
}

Instance.OnActivate(() => Instance.SetNextThink(Instance.GetGameTime() + TICK));

Instance.SetThink(() => {
  for (let s = 0; s < 64; s++) {
    const pawn = Instance.GetPlayerController(s)?.GetPlayerPawn();
    if (!pawn || !pawn.IsValid() || !pawn.IsAlive()) continue;
    const want = LOADOUT[pawn.GetTeamNumber()];
    if (!want) continue;
    enforce(pawn, want);
    if (pending.has(s)) {
      pending.delete(s);
      for (let i = want.length - 1; i >= 0; i--) if (!pawn.FindWeapon(want[i])) pawn.GiveNamedItem(want[i], i === 0);
    }
  }
  Instance.SetNextThink(Instance.GetGameTime() + TICK);
});

Instance.OnPlayerReset(({ player }) => {
  const s = player.GetPlayerController()?.GetPlayerSlot();
  if (s !== undefined) pending.add(s);
});
Instance.OnRoundStart(() => { for (let s = 0; s < 64; s++) pending.add(s); });
