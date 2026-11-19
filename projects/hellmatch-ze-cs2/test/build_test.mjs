// Test build: concatenates a src tree the way tools/build.mjs does, but from fixture data, so the game code can be
// tested before (or without) the pipeline's out/addon. Writes into test/out/ (gitignored).
//   node test/build_test.mjs [--src <dir with core/ and cs2/>] [--levels <levels.json>] [--consts <file>] [--name <base>]
//   --fixture: use the FreeDM fixture levels even when the pipeline's out/addon/_gen/levels.json exists
// Outputs test/out/<name>_core.cjs (Node module for sim/audit) and test/out/<name>.js (the CS2 point_script).
// Defaults: this project's src, the pipeline's out/addon/_gen/levels.json when present, else
// test/fixtures/fdm/levels_dm01_dm02.json + test/fixtures/ze/*.json sidecars; consts = test/fixtures/fdm/consts.js
// (SPRITE_MODELS, HUD_STRING_INDEX, HUD_GLYPH_W, MUSIC_TRACKS from the Hellmatch build).
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..');
const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const src = path.resolve(arg('src', path.join(root, 'src')));
const name = arg('name', 'hellescape');
const pipeLevels = path.join(root, 'out/addon/_gen/levels.json');
// --fixture: the FreeDM fixture levels + test/fixtures/ze sidecars even when the pipeline's levels exist
const levelsFile = arg('levels', fs.existsSync(pipeLevels) && !process.argv.includes('--fixture') ? pipeLevels : path.join(here, 'fixtures/fdm/levels_dm01_dm02.json'));
const constsFile = arg('consts', path.join(here, 'fixtures/fdm/consts.js'));
const read = (d) => fs.readdirSync(d).filter((f) => f.endsWith('.js')).sort().map((f) => `// ---- ${f}\n` + fs.readFileSync(path.join(d, f), 'utf8')).join('\n');
const core = read(path.join(src, 'core'));
let levels = JSON.parse(fs.readFileSync(levelsFile, 'utf8'));
// fixture ZE levels: test/fixtures/ze/<id>.json = { base: "<level id in the levels file>", ze: {sidecar} } -> two placements
// (<id>t, <id>c) of that level, as the pipeline will emit them (Contract in docs/STATUS.md)
const zeDir = path.join(here, 'fixtures/ze');
if (!arg('levels') && levelsFile !== pipeLevels && fs.existsSync(zeDir) && !process.argv.includes('--noze')) {
  for (const f of fs.readdirSync(zeDir).filter((x) => x.endsWith('.json'))) {
    const fx = JSON.parse(fs.readFileSync(path.join(zeDir, f), 'utf8'));
    const L = levels.find((l) => l.id === fx.base);
    if (!L) throw new Error(f + ': no level ' + fx.base);
    const id = f.replace(/\.json$/, '');
    for (const side of ['t', 'c']) levels.push({ ...L, id: id + side, base: id, side, ze: fx.ze, title: fx.ze.title || L.title, author: fx.ze.author_credit || '', off: side === 't' ? L.off : [L.off[0], L.off[1], L.off[2] + 4096] });
  }
}
const lv = JSON.stringify(levels);
const outDir = path.join(here, 'out');
fs.mkdirSync(outDir, { recursive: true });
const exportsLine = `module.exports = { LEVELS, Arena, RoundManager, DEFAULT_CFG, MT, STATES, SN, MOBJINFO, BT_ATTACK, BT_USE, arenaSizes, botThink, cycleWeapon, selectSlot, checkPositionProbe, ` +
  `checkSight: typeof checkSight === 'function' ? checkSight : undefined, MF_SOLID, MF_SHOOTABLE, MF_PICKUP, ` +
  `ZeRound: typeof ZeRound === 'function' ? ZeRound : undefined, ZeArena: typeof ZeArena === 'function' ? ZeArena : undefined, ZeDirector: typeof ZeDirector === 'function' ? ZeDirector : undefined, ZE: typeof ZE === 'object' ? ZE : undefined, ZCLASS: typeof ZCLASS === 'object' ? ZCLASS : undefined, WEAPON_ACTIONS, damageMobj, buildNav: typeof buildNav === 'function' ? buildNav : undefined, teleportMove: typeof teleportMove === 'function' ? teleportMove : undefined, navNext: typeof navNext === 'function' ? navNext : undefined, get TM() { return TM; }, get G() { return G; } };\n`;
fs.writeFileSync(path.join(outDir, name + '_core.cjs'), core + `\nconst LEVELS = ${lv};\n` + exportsLine);
const cs2 = path.join(src, 'cs2');
if (fs.existsSync(cs2)) {
  const imports = read(cs2);
  const usesNew = /\b(Entities|Console|GameRules)\./.test(imports);
  const head = `import { Instance, ${usesNew ? 'Entities, Console, GameRules, ' : ''}CSInputs, CSPlayerPawn, CSPlayerController, BaseModelEntity, PointTemplate, CustomHudLayout, CSDamageFlags, CSDamageTypes, CustomCameraMode, CSMoveType, CSRoundEndReason, Entity } from "cs_script/point_script";\n`;
  const consts = fs.readFileSync(constsFile, 'utf8');
  fs.writeFileSync(path.join(outDir, name + '.js'), head + core + `\nconst LEVELS = ${lv};\n` + consts + '\n' + imports);
}
console.log(`built test/out/${name}.js + ${name}_core.cjs from ${path.relative(root, src) || '.'} with ${levels.length} levels (${path.relative(root, levelsFile)})`);
