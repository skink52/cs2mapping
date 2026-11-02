// Concatenates the playsim into (1) a Node test module and (2) the CS2 point_script.
import fs from 'node:fs';
import path from 'node:path';
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const coreDir = path.join(root, 'src/core');
const core = fs.readdirSync(coreDir).filter((f) => f.endsWith('.js')).sort().map((f) => `// ---- ${f}\n` + fs.readFileSync(path.join(coreDir, f), 'utf8')).join('\n');
const levels = fs.readFileSync(path.join(root, 'out/addon/_gen/levels.json'), 'utf8');
fs.mkdirSync(path.join(root, 'build'), { recursive: true });
const testMod = core + `\nconst LEVELS = ${levels};\nmodule.exports = { LEVELS, Arena, RoundManager, DEFAULT_CFG, MT, STATES, SN, MOBJINFO, BT_ATTACK, BT_USE, arenaSizes, botThink, cycleWeapon, selectSlot, checkPositionProbe, checkSight: typeof checkSight === 'function' ? checkSight : undefined, MF_SOLID, MF_SHOOTABLE, MF_PICKUP, get TM() { return TM; }, get G() { return G; } };\n`;
fs.writeFileSync(path.join(root, 'build/core_test.cjs'), testMod);
const adapterDir = path.join(root, 'src/cs2');
if (fs.existsSync(adapterDir) && fs.existsSync(path.join(root, 'out/addon/_gen/sprite_models.json')) && fs.existsSync(path.join(root, 'build/hud_strings.json'))) {
  const adapter = fs.readdirSync(adapterDir).filter((f) => f.endsWith('.js')).sort().map((f) => `// ---- ${f}\n` + fs.readFileSync(path.join(adapterDir, f), 'utf8')).join('\n');
  const head = `import { Instance, CSInputs, CSPlayerPawn, CSPlayerController, BaseModelEntity, PointTemplate, CustomHudLayout, CSDamageFlags, CSDamageTypes, CustomCameraMode, CSMoveType, CSRoundEndReason, Entity } from "cs_script/point_script";\n`;
  const sprites = fs.readFileSync(path.join(root, 'out/addon/_gen/sprite_models.json'), 'utf8');
  const strings = fs.readFileSync(path.join(root, 'build/hud_strings.json'), 'utf8');
  const musicFile = path.join(root, 'out/addon/_gen/music.json');
  const music = fs.existsSync(musicFile) ? JSON.stringify(JSON.parse(fs.readFileSync(musicFile, 'utf8')).map((t) => ({ id: t.id, pool: t.pool, seconds: t.seconds, title: t.title }))) : '[]';
  const glyphFile = path.join(root, 'build/hud_glyph_w.json');
  const glyphs = fs.existsSync(glyphFile) ? fs.readFileSync(glyphFile, 'utf8') : '{}';
  const out = head + core + `\nconst LEVELS = ${levels};\nconst SPRITE_MODELS = ${sprites};\nconst HUD_STRING_INDEX = new Map(${strings}.map((s, i) => [s, i]));\nconst HUD_GLYPH_W = ${glyphs};\nconst MUSIC_TRACKS = ${music};\n` + adapter;
  fs.mkdirSync(path.join(root, 'out/addon/maps/scripts'), { recursive: true });
  fs.writeFileSync(path.join(root, 'out/addon/maps/scripts/freedm.js'), out);
  console.log('cs2 script', (out.length / 1024).toFixed(0), 'KB');
}
console.log('test module', (testMod.length / 1024).toFixed(0), 'KB');
