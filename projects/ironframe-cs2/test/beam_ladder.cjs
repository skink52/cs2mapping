// The beam ladder (src/cs2/30_render.js beamPick + models.json#fx beam_c_* / beam_r_*, built by tools/fx.py): for every shot length
// and width tier the picked rung, scaled, is exactly as long as the shot and its width stays within x1.19 of the wanted width.
// The code under test is cut out of the adapter source, so this tests what the build ships.   usage: node test/beam_ladder.cjs
const fs = require('fs'), path = require('path');
const root = path.join(__dirname, '..');
const src = fs.readFileSync(path.join(root, 'src/cs2/30_render.js'), 'utf8');
const a = src.indexOf('const BEAM_W_MAX'), b = src.indexOf('function renderProjectiles()');
if (a < 0 || b < a) { console.log('FAIL: beam code not found in 30_render.js'); process.exit(1); }
const MODELS = JSON.parse(fs.readFileSync(path.join(root, 'out/addon/_gen/models.json'), 'utf8'));
const mod = new Function('FX_MODELS', src.slice(a, b) + '\nreturn { BEAM_LADDERS, beamPick, BEAM_W_MAX, BEAM_TAIL_W };')(MODELS.fx || {});
let fails = 0, checks = 0;
const ok = (cond, msg) => { checks++; if (!cond) { fails++; if (fails < 20) console.log('FAIL: ' + msg); } };

for (const c of ['c', 'r']) {
  const lad = mod.BEAM_LADDERS[c];
  ok(lad.length >= 12, 'ladder ' + c + ' has ' + lad.length + ' rungs');
  for (let i = 1; i < lad.length; i++) ok(lad[i].len / lad[i - 1].len < 1.45 && lad[i].len > lad[i - 1].len, 'rung step ' + lad[i - 1].len + ' -> ' + lad[i].len);
  for (const r of lad) ok(fs.existsSync(path.join(root, 'out/addon', r.model)), 'model file ' + r.model);
  const lo = lad[0].len, hi = lad[lad.length - 1].len;
  const tol = Math.pow(2, 0.25) * 1.012;                    // half a x1.41 step, plus the rounding of the rung lengths
  for (const w of [mod.BEAM_TAIL_W, 1, 1.2, 1.4, mod.BEAM_W_MAX]) {
    let worst = 1;
    for (let l = 20; l <= 13800; l = Math.ceil(l * 1.013)) {
      const pk = mod.beamPick(lad, l, w);
      const rung = lad.find((r) => r.model === pk.model);
      ok(!!rung && typeof pk.model === 'string', 'a rung for l ' + l);
      const inside = l / w >= lo / tol && l / w <= hi * tol;       // the ladder covers this length at this width
      if (l >= lo * 0.5 && l <= hi * 1.8) ok(Math.abs(pk.scale * rung.len - l) < 0.01 * l + 0.5, 'length: l ' + l + ' w ' + w + ' drawn ' + (pk.scale * rung.len).toFixed(1));
      if (inside) { const k = pk.scale / w; worst = Math.max(worst, k, 1 / k); ok(k <= tol && k >= 1 / tol, 'width: l ' + l + ' w ' + w + ' scale ' + pk.scale.toFixed(3)); }
      ok(pk.scale >= 0.5 && pk.scale <= 1.8, 'scale clamp at l ' + l);
    }
    console.log('ladder ' + c + ' width tier ' + w + ': worst width error x' + worst.toFixed(3) + ' (limit x' + tol.toFixed(3) + ')');
  }
  // the old bar for comparison: width factor l / 180, length 100 * l / 180
  const pk = mod.beamPick(lad, 2600, 1);
  console.log('  2600 u shot: rung ' + lad.find((r) => r.model === pk.model).len + ' x ' + pk.scale.toFixed(2) + ' (the old bar: x' + (2600 / 180).toFixed(1) + ' wide, ' + Math.round(100 * 2600 / 180) + ' u long)');
}
console.log((fails ? 'FAILED ' + fails + ' of ' : 'ok ') + checks + ' checks');
process.exit(fails ? 1 : 0);
