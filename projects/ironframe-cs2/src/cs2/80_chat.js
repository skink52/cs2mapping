// ===================================================================================================================
// IRONFRAME CS2 adapter, part 8: chat commands (! or /). Replies are per-player HUD lines, not say (the host's chat is
// rate limited and visible to all).
// ===================================================================================================================
// !help: pages of the two-row message line, shown one after another (each used to replace the last, so only the commands showed)
// (10 Nov 2026 evening: !help also puts the controls card up; the pages are in gold and never cut short by other messages)
const HELP_LINES = [
  'WASD move, Shift boost, Ctrl quick boost, Space jump / hover. Mouse 1 / 2 fire the arms, R / E the shoulders',
  'Keep an enemy inside the ring to lock on; F switches target. Missiles track once the bracket is red',
  'Gold bar full: hold Space + R + E for the overdrive blast. Dead: Ctrl or F opens the garage',
  'Chat: !garage !loadout 1-6 !spec !back !afk !vote !mode !pilot !od',
];
/** a message to one player on the HUD line (three rows; longer text continues on a second page). queue = after what is showing, in order.
 *  prio 0 ambient (shown only when the line is free) | 1 normal | 2 important (gold, cuts in). Without one it is ranked by the core event being
 *  handled (45_features.js replyCtx): news about other pilots is ambient, a pilot's own rewards and anything outside an event (chat replies,
 *  warnings) are important. 10 Nov 2026 evening playtest: every message used to replace the one on screen at once. */
function reply(slot, text, secs, queue, prio) { if (ifrHudLine) ifrHudLine(slot, text, secs || 4, queue, prio === undefined ? replyPrio(slot) : prio); }
function replyPrio(slot) {
  const ev = typeof replyCtx === 'object' ? replyCtx : null;
  if (!ev) return 2;
  switch (ev.t) {
    case 'bounty': case 'capture': return 0;
    case 'trait': return ev.phase === 'fire' ? 0 : 1;
    case 'crate': return ev.slot === slot ? 2 : ev.phase === 'take' ? 0 : 1;
    case 'overdrive': return ev.slot === slot ? 1 : 0;
    case 'streak': return ev.slot === slot ? 2 : ev.kind === 'ace' ? 0 : 1;
    case 'flag': return 2;
    default: return 1;
  }
}
// the answer to a customisation command: what changed, or why not
function chatCustom(pe, code, ok) { reply(pe.slot, code ? (DENY_TEXT[code] || 'denied') : ok, 5); }
function onChat(player, text) {
  if (!CONFIG.CHAT_COMMANDS || !player) return;
  let slot; try { slot = player.GetPlayerSlot(); } catch (err) { return; }
  const pe = person(slot); if (!pe) return;
  let t = String(text || '').trim().toLowerCase();
  if (t.startsWith('/')) t = '!' + t.slice(1);
  if (!t.startsWith('!')) return;
  const parts = t.split(/\s+/), word = parts[0], arg = parts[1], rest = t.slice(word.length).trim();
  dlog('chat command ' + t + ' from slot ' + slot);
  switch (word) {
    case '!help': case '!ironframe': case '!if': case '!controls': case '!keys':
      if (typeof ifrHudCard === 'function') ifrHudCard(slot, 'controls', 6 * HELP_LINES.length);
      HELP_LINES.forEach((l, i) => reply(slot, l, 6, i > 0, 2)); break;
    case '!garage': case '!mech': case '!loadouts':
      // short enough for one row; the line sits right of CS2's chat box down to 4:3 (10 Nov 2026 playtest: the old text was cut off)
      if (pe.status === 'mech') { reply(slot, 'In a mech: !spec first, or wait for your next death', 5); break; }
      garageOpen(pe, ''); break;
    case '!loadout': case '!l': {
      const k = parseInt(arg, 10);
      if (!(k >= 1 && k <= IF_Career.slots)) { reply(slot, 'Usage: !loadout 1-' + IF_Career.slots); break; }
      if (serverMode) { srvSend(slot, 'active', [k]); reply(slot, 'Loadout ' + k + ' will be used next life'); }
      else if (pe.garage) { pe.garage.slot = k; reply(slot, 'Loadout ' + k + ' selected'); }
      break;
    }
    // the camera distance is a preference that follows the pilot (the profile: 70_server.js srvCustom); !cam steps through the presets
    case '!cam': case '!camera': {
      const pr = srvProfile(pe), C = IF_Career.data.camera;
      if (!pr) { reply(slot, 'No pilot record yet'); break; }
      const want = C.find((c) => c.name.toLowerCase() === arg || (arg === 'near' && c.id === 1) || (arg === 'standard' && c.id === 0));
      const nx = want ? want.id : ((pr.prefs & IF_Career.PREF_CAM) + 1) % C.length;
      chatCustom(pe, srvCustom(pe, 'pref', (pr.prefs & ~IF_Career.PREF_CAM) | nx), 'Camera: ' + IF_Career.camera(nx).name + '  (' + C.map((c) => c.name.toLowerCase()).join(' | ') + ')'); break;
    }
    case '!hints': {
      const pr = srvProfile(pe); if (!pr) { reply(slot, 'No pilot record yet'); break; }
      const off = arg === 'off' ? true : arg === 'on' ? false : !(pr.prefs & IF_Career.PREF_HINTS_OFF);
      chatCustom(pe, srvCustom(pe, 'pref', off ? pr.prefs | IF_Career.PREF_HINTS_OFF : pr.prefs & ~IF_Career.PREF_HINTS_OFF), 'Hints ' + (off ? 'off' : 'on')); break;
    }
    case '!callsign': case '!cs': {
      const text = IF_Career.clean(rest, IF_Career.data.callsign_len);
      chatCustom(pe, srvCustom(pe, 'callsign', rest), text ? 'Callsign: ' + text : 'Callsign cleared'); break;
    }
    case '!name': case '!loadname': {
      const k = serverMode ? (pe.pilot ? pe.pilot.active : 1) : ((pe.garage && pe.garage.slot) || 1), kk = pe.garage && pe.garage.open ? pe.garage.slot : k;
      const text = IF_Career.clean(rest, IF_Career.data.name_len);
      chatCustom(pe, srvCustom(pe, 'name', kk, rest), text ? 'Loadout ' + kk + ' is now ' + text : 'Loadout ' + kk + ': name cleared'); break;
    }
    case '!title': case '!badge': {
      const kind = word.slice(1), pr = srvProfile(pe); if (!pr) { reply(slot, 'No pilot record yet'); break; }
      const mine = IF_Career.data.honours.filter((h) => h.kind === kind && pr.earned.has(h.id));
      if (!arg) { reply(slot, mine.length ? kind.toUpperCase() + 'S: ' + mine.map((h) => h.name).join(', ') + '.  !' + kind + ' <name> | none' : 'No ' + kind + ' earned yet: see the PILOT tab of the garage', 8); break; }
      const h = arg === 'none' || arg === 'off' ? null : IF_Career.data.honours.find((x) => x.kind === kind && x.name.toLowerCase().replace(/ /g, '') === rest.replace(/ /g, ''));
      if (!h && arg !== 'none' && arg !== 'off') { reply(slot, 'No ' + kind + ' called ' + rest); break; }
      chatCustom(pe, srvCustom(pe, kind, h ? h.id : 0), h ? kind.charAt(0).toUpperCase() + kind.slice(1) + ': ' + h.name : kind + ' off'); break;
    }
    case '!contracts': case '!daily': case '!dailies': {
      const pr = srvProfile(pe);
      if (!serverMode) { reply(slot, 'Stand-alone: daily contracts are on a server'); break; }
      if (!pr || !pr.daily.length) { reply(slot, 'No contracts today'); break; }
      pr.daily.forEach((d, i) => reply(slot, IF_Career.contractLabel(d.code) + ': ' + (d.progress >= d.goal ? 'DONE' : d.progress + ' / ' + d.goal) + '  +' + d.reward + ' CR', 6, i > 0)); break;
    }
    case '!top': case '!leaders': case '!leaderboard': {
      if (!serverMode || !srvBoard) { reply(slot, serverMode ? 'No leaderboard yet' : 'Stand-alone: the leaderboard is on a server'); break; }
      const pr = srvProfile(pe);
      srvBoard.rows.slice(0, 5).forEach((x, i) => reply(slot, (i + 1) + '  ' + x.name + '  R' + x.rank + '  ' + x.xp + ' XP', 6, i > 0));
      if (pr && pr.place) reply(slot, 'You: # ' + pr.place + ' of ' + srvBoard.total, 6, true); break;
    }
    case '!spec': case '!spectate': spectate(pe, 'you chose to watch; !back to return'); break;
    case '!afk': spectate(pe, 'AFK: !back when you return'); break;
    case '!back': case '!join': case '!play': if (pe.status === 'spec') { pe.status = 'dead'; pe.deathAt = 0; garageOpen(pe, 'Welcome back: pick a loadout and SORTIE'); } else reply(slot, 'You are already in the fight'); break;
    case '!vote': case '!v': guard('vote', () => { const r = game.vote(slot, arg); reply(slot, r || 'Vote noted'); }); break;
    case '!pilot': case '!rank': case '!stats': {
      if (!pe.pilot) { reply(slot, serverMode ? 'No pilot record yet' : 'Stand-alone: no career on this server'); break; }
      reply(slot, 'Rank ' + pe.pilot.rank + ', ' + pe.pilot.xp + ' XP, ' + pe.pilot.credits + ' credits, ' + pe.pilot.owned.size + ' parts', 6); break;
    }
    case '!od': case '!overdrive': featChatOd(slot); break;
    case '!mode': { const mt = game.matchFor(slot), nm = (typeof IFR_HUD_MODE_NAMES === 'object' && IFR_HUD_MODE_NAMES[mt.mode]) || mt.mode || '?';
      reply(slot, nm + ' (arena ' + (game.arenaIndexOf(slot) + 1) + ' of ' + game.list.filter((a) => a.active).length + '): T ' + ((mt.scores || {})[2] | 0) + ', CT ' + ((mt.scores || {})[3] | 0), 5); } break;
    case '!perf': reply(slot, perfText || 'no figures yet', 6); break;
    default: break;
  }
}
function spectate(pe, why) {
  if (pe.status === 'mech') guard('leave mech', () => game.leaveMech && game.leaveMech(pe.slot));
  garageClose(pe);
  pe.status = 'spec'; pe.specTarget = -1;
  if (pe.human) { revivePawn(pe); parkPawn(pe); pe.camKind = ''; pe.camSent = null; }   // out of the mech: hidden in the booth, the spectator camera takes over
  reply(pe.slot, why, 5);
}
