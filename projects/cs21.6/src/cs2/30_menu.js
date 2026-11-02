// ---------------------------------------------------------------- menus: the 1.6 buy menu and class menu
// One menu box with ten rows (Buttons cs_mb0..cs_mb9). Each row shows "<key> <name>" and a price; hovering a row shows
// its picture and the 1.6 weapon information on the right (CSS :hover, no script needed). The script fills the rows for
// the page the player is on. Clicking needs CS2's cursor mode (SetInputCaptureEnabled); without it (CONFIG.MENU_MOUSE
// false) the rows are picked with W / S and E, and R goes back.

const MENU_ROWS = 10;
const HUD_TEXT = typeof HUD_JSON === 'object' && HUD_JSON ? HUD_JSON : { items: {}, cats: {}, classes: {}, titles: {} };
function itemLabel(id) {
  const t = HUD_TEXT.items[id];
  if (t && t.label) return t.label;
  if (WEAPONS[id]) return WEAPONS[id].name.toUpperCase();
  if (EQUIP[id]) return EQUIP[id].name.toUpperCase();
  return id.toUpperCase();
}
function itemInfo(id) { const t = HUD_TEXT.items[id]; return t && t.info ? t.info : ''; }
function itemPrice(id) {
  if (WEAPONS[id]) return WEAPONS[id].price;
  if (EQUIP[id]) return EQUIP[id].price;
  return 0;
}
const CAT_LABEL = { pistol: 'HANDGUN', shotgun: 'SHOTGUN', smg: 'SUB-MACHINE GUN', rifle: 'RIFLE', mg: 'MACHINE GUN',
  ammo1: 'PRIMARY AMMO', ammo2: 'SECONDARY AMMO', equip: 'EQUIPMENT' };
function catLabel(id) { return (HUD_TEXT.cats && HUD_TEXT.cats[id]) || CAT_LABEL[id] || id.toUpperCase(); }
function title(key, fallback) { return (HUD_TEXT.titles && HUD_TEXT.titles[key]) || fallback; }

// ---------------------------------------------------------------- pages
function catItems(cat, team) {
  const c = BUY_MENU.find((x) => x.id === cat);
  if (!c) return [];
  const list = c.items || (team === TEAM_T ? c.itemsT : c.itemsCT) || [];
  return list.filter((id) => {
    const w = WEAPONS[id] || EQUIP[id];
    return !w || !w.team || w.team === team;
  });
}

function buildPage(rec) {
  const m = rec.menu;
  const rows = [];
  const cancel = { key: '0', text: title('cancel', 'CANCEL'), act: () => closeMenu(rec) };
  if (m.kind === 'class') {
    m.title = title('class_' + rec.team, rec.team === TEAM_T ? 'Select Your Appearance (Terrorist)' : 'Select Your Appearance (Counter-Terrorist)');
    CLASSES[rec.team].forEach((c, i) => {
      const t = HUD_TEXT.classes[c.id] || {};
      rows.push({ key: String(i + 1), text: (t.label || c.name).toUpperCase(), pic: 'pic_' + c.id, info: t.info || '', act: () => chooseClass(rec, c.id) });
    });
    rows.push({ key: '5', text: title('auto', 'AUTO-SELECT'), pic: rec.team === TEAM_T ? 'pic_t_random' : 'pic_ct_random', info: '', act: () => chooseClass(rec, null) });
  } else if (m.page === 'main') {
    m.title = title('buy', 'Buy Menu');
    BUY_MENU.forEach((c, i) => {
      if (c.action) rows.push({ key: String(i + 1), text: catLabel(c.id), act: () => { buy(rec, c.action); closeMenu(rec); } });
      else rows.push({ key: String(i + 1), text: catLabel(c.id), act: () => { m.page = c.id; m.sel = 0; buildPage(rec); } });
    });
    if (rec.lastBuys.length) rows.push({ key: 'R', text: title('rebuy', 'RE-BUY PREVIOUS'), act: () => { rebuy(rec); closeMenu(rec); } });
    rows.push(cancel);
  } else {
    m.title = catLabel(m.page);
    catItems(m.page, rec.team).forEach((id, i) => {
      const unavailable = !!(EQUIP[id] && EQUIP[id].unavailable);
      rows.push({ key: String(i + 1), text: itemLabel(id), price: unavailable ? '' : '$' + itemPrice(id), pic: 'pic_' + (unavailable ? 'not_available' : id),
        info: itemInfo(id), item: id, disabled: unavailable, act: () => { if (buy(rec, id)) closeMenu(rec); } });
    });
    rows.push(cancel);
  }
  m.rows = rows.slice(0, MENU_ROWS);
  if (m.sel >= m.rows.length) m.sel = 0;
}

function openMenu(rec, kind, page) {
  if (rec.menu && rec.menu.kind === kind && kind === 'buy' && rec.menu.page === (page || 'main')) return;
  rec.menu = { kind, page: page || 'main', sel: 0, opened: now(), rows: [], title: '' };
  buildPage(rec);
  setCapture(rec, true);
}
function closeMenu(rec) {
  if (!rec.menu) return;
  rec.menu = null;
  setCapture(rec, false);
}
function setCapture(rec, on) {
  if (!CONFIG.MENU_MOUSE) on = false;
  if (rec.capture === on) return;
  const h = hud();
  if (!h) return;
  guard('capture', () => h.SetInputCaptureEnabled(rec.slot, on));
  rec.capture = on;
}

function menuClick(rec, buttonId) {
  const m = rec.menu;
  if (!m) return;
  const i = /^cs_mb(\d)$/.exec(buttonId);
  if (!i) return;
  const row = m.rows[+i[1]];
  if (!row || row.disabled) return;
  if (now() - m.opened < 0.15) return;          // the click that opened it (cursor mode) is not a pick
  guard('menu', row.act);
}

// keyboard picking (no cursor mode): W / S move, E picks, R goes back a page (or closes)
function menuKeys(rec, pawn) {
  const m = rec.menu;
  if (!m || rec.capture) return;
  if (pawn.WasInputJustPressed(CSInputs.FORWARD)) m.sel = (m.sel + m.rows.length - 1) % m.rows.length;
  else if (pawn.WasInputJustPressed(CSInputs.BACK)) m.sel = (m.sel + 1) % m.rows.length;
  else if (pawn.WasInputJustPressed(CSInputs.USE)) { const row = m.rows[m.sel]; if (row && !row.disabled) guard('menu', row.act); }
  else if (pawn.WasInputJustPressed(CSInputs.RELOAD)) {
    if (m.kind === 'buy' && m.page !== 'main') { m.page = 'main'; m.sel = 0; buildPage(rec); } else if (m.kind === 'buy') closeMenu(rec);
  }
}

function drawMenu(rec) {
  const s = rec.slot, m = rec.menu;
  hudFlag(s, 'cs_root', 'stMenu', !!m);
  hudFlag(s, 'cs_root', 'stKeys', !!m && !rec.capture);
  if (!m) return;
  hudVar(s, 'cs_mtitle', m.title);
  if (m.kind === 'buy') hudVar(s, 'cs_mfoot', '$' + rec.money);
  else hudVar(s, 'cs_mfoot', '');
  for (let i = 0; i < MENU_ROWS; i++) {
    const row = m.rows[i];
    const b = 'cs_mb' + i;
    hudFlag(s, b, 'on', !!row);
    if (!row) continue;
    const cantAfford = !!row.item && itemPrice(row.item) > rec.money;
    hudFlag(s, b, 'dis', !!row.disabled || cantAfford);
    hudFlag(s, b, 'sel', !rec.capture && i === m.sel);
    hudVar(s, 'cs_ml' + i, row.key + '  ' + row.text);
    hudVar(s, 'cs_mp' + i, row.price || '');
    hudCls(s, 'cs_mpic' + i, 'p', row.pic || null);
    hudVar(s, 'cs_mi' + i, row.info || '');
  }
}

// ---------------------------------------------------------------- the class menu (player models)
function chooseClass(rec, id) {
  const list = CLASSES[rec.team];
  if (!list) { closeMenu(rec); return; }
  rec.cls = id || pick(list).id;
  rec.clsTeam = rec.team;
  closeMenu(rec);
  if (rec.helpPending) { rec.helpPending = false; message(rec, CONFIG.HELP_LINE, 8); }
  const pawn = pawnOf(rec.slot);
  if (pawn && rec.alive) applyModel(rec, pawn);
}
function applyModel(rec, pawn) {
  if (!CONFIG.SET_MODELS || !rec.cls || rec.clsTeam !== rec.team) return;
  let mdl = CLASS_MODELS[rec.cls];
  if (!mdl) return;
  // 1.6: the bomb carrier wears the bomb pack, a CT with a defuse kit wears the kit (a second copy of the model)
  rec.packShown = packWanted(rec);
  if (rec.packShown) mdl = mdl.replace('.vmdl', '_pack.vmdl');
  guard('model', () => pawn.SetModel(mdl));
}
function packWanted(rec) {
  if (!CONFIG.MODELS_16 || !CONFIG.PACKS_16 || !rec.alive) return false;
  return rec.team === TEAM_T ? rec.hasC4 : rec.team === TEAM_CT ? rec.hasDefuser : false;
}
