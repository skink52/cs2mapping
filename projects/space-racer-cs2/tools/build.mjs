// Concatenates the game into (1) a Node test module and (2) the CS2 point_script.
import fs from 'node:fs';
import path from 'node:path';
const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const NAME = process.env.SPR_NAME || 'space_racer';
const cat = (dir) => fs.readdirSync(dir).filter((f) => f.endsWith('.js')).sort().map((f) => `// ---- ${f}\n` + fs.readFileSync(path.join(dir, f), 'utf8')).join('\n');
const core = cat(path.join(root, 'src/core'));
const tracks = fs.readFileSync(path.join(root, 'out/addon/_gen/tracks.json'), 'utf8');
fs.mkdirSync(path.join(root, 'build'), { recursive: true });
const testMod = core + `\nconst TRACKS = ${tracks};\nmodule.exports = { TRACKS, Track, Car, Arena, RoundManager, ballotRandom, DEFAULT_CFG, CARS, CAR_KEYS, RULES, TICRATE, DT, arenaSizes, splitShares, layoutFor, LAYOUTS, makeBot, botThink, seedRandom, rnd, collideCars };\n`;
fs.writeFileSync(path.join(root, 'build/core_test.cjs'), testMod);
console.log('test module', (testMod.length / 1024).toFixed(0), 'KB');
const adapterDir = path.join(root, 'src/cs2');
const carModels = path.join(root, 'out/addon/_gen/car_models.json');
if (fs.existsSync(adapterDir) && fs.existsSync(carModels)) {
  const adapter = cat(adapterDir);
  const head = `import { Instance, CSInputs, CSPlayerPawn, CSPlayerController, BaseModelEntity, PointTemplate, CustomHudLayout, CSDamageFlags, CSDamageTypes, CustomCameraMode, CSMoveType, CSRoundEndReason, Entity } from "cs_script/point_script";\n`;
  const models = fs.readFileSync(carModels, 'utf8');
  const hudTextPath = path.join(root, 'out/addon/_gen/hud_text.json');
  const hudText = fs.existsSync(hudTextPath) ? fs.readFileSync(hudTextPath, 'utf8') : '{"slots":{},"charset":""}';
  const musicPath = path.join(root, 'out/addon/_gen/music.json');
  const music = fs.existsSync(musicPath) ? fs.readFileSync(musicPath, 'utf8') : '{}';
  const out = head + core + `\nconst TRACKS = ${tracks};\nconst CAR_MODELS = ${models};\nconst HUD_TEXT = ${hudText};\nconst MUSIC_LEN = ${music};\nconst GAME_THEME = '${process.env.SPR_THEME || 'space'}';\n` + adapter;
  fs.mkdirSync(path.join(root, 'out/addon/maps/scripts'), { recursive: true });
  fs.writeFileSync(path.join(root, `out/addon/maps/scripts/${NAME}.js`), out);
  console.log('cs2 script', (out.length / 1024).toFixed(0), 'KB ->', `maps/scripts/${NAME}.js`);
}
