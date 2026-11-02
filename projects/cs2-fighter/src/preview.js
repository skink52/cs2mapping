// Browser preview front end for the shared Puppet Brawl core.
(() => {
  const cv = document.getElementById("cv");
  const ctx = cv.getContext("2d");
  const W = cv.width, H = cv.height;
  const FONT_D = '"Titan One", "Arial Rounded MT Bold", "Trebuchet MS", sans-serif';
  const FONT_B = '"Atkinson Hyperlegible", "Segoe UI", system-ui, sans-serif';
  let game = null;
  let mode = "attract";            // attract | play
  let twoP = false;
  let galleryKind = null;
  const query = new URLSearchParams(location.search);

  function newGame() {
    const g = new Game({ seed: (Date.now() & 0xffff) + 1, halfWidth: 380, cfg: { cpuLevel: +document.getElementById("lvl").value } });
    window.__game = g;
    return g;
  }
  function startAttract() {
    mode = "attract";
    game = newGame();
    game.cfg.needHuman = false; game.forceCpuMatch = true;
    game.addCpu(0); game.addCpu(1);
    game.forceStart();
    setTwoP(false, true);
  }
  function startPlay() {
    if (mode === "play") return;
    mode = "play";
    game = newGame();
    game.seatHuman(0, "local1", "You");
    if (twoP) game.seatHuman(1, "local2", "Player 2");
    cv.focus();
  }
  function setTwoP(on, silent) {
    twoP = on;
    const b = document.getElementById("b2p");
    b.setAttribute("aria-pressed", String(on));
    if (silent || mode !== "play") return;
    if (on) { if (game.seats[1].kind) game.unseat(1); game.seatHuman(1, "local2", "Player 2"); }
    else if (game.seats[1].kind === "human") game.unseat(1);
  }

  // ------------------------------------------------------------------ input
  const keys = new Set();
  const pressedSince = [0, 0];
  const mouse = { 0: false, 2: false };
  const map1 = { KeyA: IN.LEFT, KeyD: IN.RIGHT, KeyW: IN.UP, Space: IN.UP, KeyS: IN.DOWN, ShiftLeft: IN.BLOCK, KeyR: IN.SPECIAL, KeyF: IN.THROW, KeyJ: IN.PUNCH, KeyK: IN.KICK, KeyL: IN.BLOCK };
  const map2 = { ArrowLeft: IN.LEFT, ArrowRight: IN.RIGHT, ArrowUp: IN.UP, ArrowDown: IN.DOWN, Period: IN.PUNCH, Slash: IN.KICK, ShiftRight: IN.BLOCK, Semicolon: IN.SPECIAL, Quote: IN.THROW, Numpad1: IN.PUNCH, Numpad2: IN.KICK, Numpad3: IN.BLOCK, Numpad4: IN.SPECIAL, Numpad5: IN.THROW };
  function stageHasFocus() { return document.activeElement === cv; }
  addEventListener("keydown", (e) => {
    if (!stageHasFocus()) return;
    if (mode === "attract" && !galleryKind) { startPlay(); }
    if (map1[e.code] !== undefined || map2[e.code] !== undefined) e.preventDefault();
    if (!keys.has(e.code)) {
      if (map1[e.code] !== undefined) pressedSince[0] |= map1[e.code];
      if (map2[e.code] !== undefined) pressedSince[1] |= map2[e.code];
    }
    keys.add(e.code);
  });
  addEventListener("keyup", (e) => keys.delete(e.code));
  addEventListener("blur", () => { keys.clear(); mouse[0] = mouse[2] = false; });
  cv.addEventListener("contextmenu", (e) => e.preventDefault());
  cv.addEventListener("mousedown", (e) => {
    cv.focus();
    if (galleryKind) return;
    if (mode === "attract") { startPlay(); return; }
    if (e.button === 0) { mouse[0] = true; pressedSince[0] |= IN.PUNCH; }
    if (e.button === 2) { mouse[2] = true; pressedSince[0] |= IN.KICK; }
  });
  addEventListener("mouseup", (e) => { if (e.button === 0) mouse[0] = false; if (e.button === 2) mouse[2] = false; });
  function heldFor(map, p) {
    let h = 0;
    for (const code of keys) if (map[code] !== undefined) h |= map[code];
    if (p === 0) { if (mouse[0]) h |= IN.PUNCH; if (mouse[2]) h |= IN.KICK; }
    return h;
  }

  // ------------------------------------------------------------------ buttons
  const $ = (id) => document.getElementById(id);
  $("bPlay").onclick = () => { galleryOff(); mode = "attract"; startPlay(); };
  $("bWatch").onclick = () => { galleryOff(); startAttract(); };
  $("bMode").onclick = () => { if (mode === "attract") startPlay(); game.cycleMode(); };
  $("bCpu").onclick = () => { if (mode === "attract") startPlay(); game.addCpu(); };
  $("bCpuOff").onclick = () => { if (mode === "play") game.removeCpu(); };
  $("b2p").onclick = () => { if (mode === "attract") startPlay(); setTwoP(!twoP); };
  $("lvl").onchange = (e) => { const v = +e.target.value; game.cfg.cpuLevel = v; for (const s of game.seats) if (s.brain) s.brain.L = AI_LEVELS[v]; };
  const kinds = ["base", "normals", "specials"];
  $("bGallery").onclick = () => {
    galleryKind = galleryKind === null ? "base" : kinds[kinds.indexOf(galleryKind) + 1] || null;
    $("bGallery").setAttribute("aria-pressed", String(!!galleryKind));
    $("bGallery").textContent = galleryKind ? "Gallery: " + galleryKind + " (next)" : "Pose gallery";
  };
  function galleryOff() { galleryKind = null; $("bGallery").setAttribute("aria-pressed", "false"); $("bGallery").textContent = "Pose gallery"; }

  // ------------------------------------------------------------------ programme content from the engine data
  function buildCast() {
    const el = $("cast");
    const hex = (c) => `rgb(${c.r},${c.g},${c.b})`;
    el.innerHTML = "";
    for (const ch of CHARACTERS) {
      const art = document.createElement("article");
      art.className = "fighter";
      const sp = ch.specials.map((id, i) => {
        const m = MOVES[id];
        const how = ["R", "toward + R", "down + R"][i];
        return `<li><span class="in">${how}</span><span>${m.name}</span><span class="mo">${m.motion.join(",")}+${m.btn}</span></li>`;
      }).join("");
      art.innerHTML = `<header><span class="bead" style="background:${hex(ch.accent)}"></span><b>${ch.name}</b><span class="stats">HP ${ch.stats.hp} · walk ${ch.stats.walkF}</span></header><p>${ch.tag}</p><ul>${sp}</ul>`;
      el.appendChild(art);
    }
  }
  function buildFrames() {
    const rows = [
      ["jab", "P"], ["straight", "toward + P"], ["uppercut", "down + P"], ["kickMid", "K"], ["longKick", "toward + K"],
      ["roundhouse", "back + K"], ["sweep", "down + K"], ["airPunch", "P in the air"], ["airKick", "K in the air"],
    ];
    let html = '<thead><tr><th>Move</th><th>Input</th><th class="num">Startup</th><th class="num">Active</th><th class="num">Total</th><th class="num">Damage</th><th>Hits</th><th>Effect</th></tr></thead><tbody>';
    for (const [id, input] of rows) {
      const m = MOVES[id], h = m.hits[0];
      const effect = h.kd || h.launch ? "knockdown" : h.airKd ? "knocks down airborne" : m.cancel ? "cancels into specials" : "";
      html += `<tr><td>${m.name}</td><td><code>${input}</code></td><td class="num">${h.from}</td><td class="num">${h.to - h.from + 1}</td><td class="num">${m.total}</td><td class="num">${h.dmg}</td><td>${h.level}</td><td>${effect}</td></tr>`;
    }
    html += `<tr><td>Throw</td><td><code>F or toward + P, close</code></td><td class="num">1</td><td class="num">-</td><td class="num">${MOVES.throw.total}</td><td class="num">${MOVES.throw.dmg}</td><td>unblockable</td><td>tap P or F to break</td></tr></tbody>`;
    $("frameTable").innerHTML = html;
  }

  // ------------------------------------------------------------------ drawing helpers
  const rgb = (c, k = 1, a = 1) => `rgba(${Math.round(clamp(c.r * k, 0, 255))},${Math.round(clamp(c.g * k, 0, 255))},${Math.round(clamp(c.b * k, 0, 255))},${a})`;
  let view = { cx: 0, cy: 52, scale: 2.6, ox: W / 2, oy: H * 0.56 };
  function setView(cam) {
    const scale = W / (2 * cam.half);
    const jx = cam.shake ? (Math.random() - 0.5) * cam.shake : 0, jy = cam.shake ? (Math.random() - 0.5) * cam.shake : 0;
    view = { cx: cam.cx + jx, cy: cam.cy + jy, scale, ox: W / 2, oy: H * 0.56 };
  }
  const kd = (d) => 1 + d * 0.0022;
  function sx(x, d = 0) { return view.ox + (x - view.cx) * view.scale * kd(d); }
  function sy(y, d = 0) { return view.oy + (view.cy - y) * view.scale * kd(d) - d * 0.55 * view.scale; }
  function sk(d) { return view.scale * kd(d); }

  function drawPart(q) {
    if (q.hidden) return;
    const s = sk(q.depth), x = sx(q.x, q.depth), y = sy(q.y, q.depth);
    const dim = q.depth < -30 ? 0.62 : 1;
    if (q.model === "ball") {
      const r = Math.max(0.5, q.r * s);
      const gr = ctx.createRadialGradient(x - r * 0.35, y - r * 0.4, r * 0.1, x, y, r);
      gr.addColorStop(0, rgb(q.color, 1.25 * dim)); gr.addColorStop(1, rgb(q.color, 0.7 * dim));
      ctx.fillStyle = gr; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill();
      return;
    }
    const len = q.len * s;
    ctx.save(); ctx.translate(x, y); ctx.rotate(-q.ang * DEG);
    if (q.model === "block") {
      const k = len / 16, r0 = 3.6 * k, r1 = 4.6 * k, c = Math.min(r0, r1) * 0.6;
      const grd = ctx.createLinearGradient(0, -r1, 0, r1);
      grd.addColorStop(0, rgb(q.color, 1.2 * dim)); grd.addColorStop(1, rgb(q.color, 0.72 * dim));
      ctx.fillStyle = grd; ctx.beginPath();
      ctx.moveTo(-c * 0.6, -r0); ctx.lineTo(len, -r1); ctx.quadraticCurveTo(len + c, -r1, len + c, -r1 + c);
      ctx.lineTo(len + c, r1 - c); ctx.quadraticCurveTo(len + c, r1, len, r1); ctx.lineTo(-c * 0.6, r0);
      ctx.quadraticCurveTo(-c * 1.6, r0, -c * 1.6, r0 - c); ctx.lineTo(-c * 1.6, -r0 + c); ctx.quadraticCurveTo(-c * 1.6, -r0, -c * 0.6, -r0);
      ctx.fill();
    } else {
      const r = Math.max(0.8, len * LIMB_RADIUS_K);
      ctx.lineCap = "round";
      ctx.strokeStyle = rgb(q.color, 0.74 * dim); ctx.lineWidth = r * 2;
      ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(len, 0); ctx.stroke();
      ctx.strokeStyle = rgb(q.color, 1.18 * dim); ctx.lineWidth = r * 0.9;
      ctx.beginPath(); ctx.moveTo(0, -r * 0.35); ctx.lineTo(len, -r * 0.35); ctx.stroke();
    }
    ctx.restore();
  }

  function drawStage(halfW) {
    const floorY = sy(0);
    const back = ctx.createLinearGradient(0, 0, 0, floorY);
    back.addColorStop(0, "#1b1424"); back.addColorStop(1, "#3a2734");
    ctx.fillStyle = back; ctx.fillRect(0, 0, W, floorY);
    // spotlight pool
    const spot = ctx.createRadialGradient(sx(view.cx), floorY - 40, 10, sx(view.cx), floorY - 40, W * 0.55);
    spot.addColorStop(0, "rgba(255,226,170,0.16)"); spot.addColorStop(1, "rgba(255,226,170,0)");
    ctx.fillStyle = spot; ctx.fillRect(0, 0, W, floorY);
    const lx = sx(-halfW - 6), rx = sx(halfW + 6);
    ctx.fillStyle = "#5e1626"; ctx.fillRect(0, 0, Math.max(0, lx), floorY); ctx.fillRect(rx, 0, W - rx, floorY);
    ctx.fillStyle = "rgba(0,0,0,.25)";
    for (let i = 0; i < 6; i++) { ctx.fillRect(Math.max(0, lx) - 14 - i * 26, 0, 6, floorY); ctx.fillRect(rx + 10 + i * 26, 0, 6, floorY); }
    const fl = ctx.createLinearGradient(0, floorY, 0, H);
    fl.addColorStop(0, "#6b4a2e"); fl.addColorStop(1, "#24170e");
    ctx.fillStyle = fl; ctx.fillRect(0, floorY, W, H - floorY);
    ctx.strokeStyle = "rgba(0,0,0,.25)"; ctx.lineWidth = 1;
    for (let i = -10; i <= 10; i++) { const x = sx(i * 60); ctx.beginPath(); ctx.moveTo(x, floorY); ctx.lineTo(view.ox + (x - view.ox) * 1.6, H); ctx.stroke(); }
    ctx.fillStyle = "rgba(216,164,69,.35)"; ctx.fillRect(lx, floorY - 1, rx - lx, 2);
  }

  function drawWorld(state) {
    const all = [];
    for (const f of state.fighters) {
      if (!f.onStage) continue;
      for (const q of f.parts) if (!q.hidden) all.push(q);
      const d = f.depthBase;
      ctx.fillStyle = "rgba(0,0,0,.3)";
      ctx.beginPath(); ctx.ellipse(sx(f.x, d), sy(0, d) + 2, 24 * sk(d), 5 * sk(d), 0, 0, Math.PI * 2); ctx.fill();
    }
    all.sort((a, b) => a.depth - b.depth);
    for (const q of all) drawPart(q);
    for (const pr of state.projectiles) {
      const x = sx(pr.x), y = sy(pr.y), r = pr.r * view.scale;
      ctx.save(); ctx.shadowColor = rgb(pr.color); ctx.shadowBlur = 18;
      ctx.fillStyle = rgb(pr.color, 1.15); ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill(); ctx.restore();
    }
    for (const s of state.sparks) {
      if (s.life <= 0) continue;
      const k = 1 - s.life / s.max, x = sx(s.x, 8), y = sy(s.y, 8), r = s.size * view.scale * (0.5 + k * 0.9);
      ctx.save(); ctx.globalAlpha = 1 - k * 0.8; ctx.strokeStyle = rgb(s.color); ctx.lineWidth = 3;
      for (let i = 0; i < 8; i++) { const a = i * Math.PI / 4 + k; ctx.beginPath(); ctx.moveTo(x + Math.cos(a) * r * 0.3, y + Math.sin(a) * r * 0.3); ctx.lineTo(x + Math.cos(a) * r, y + Math.sin(a) * r); ctx.stroke(); }
      ctx.restore();
    }
  }

  // ------------------------------------------------------------------ HUD (canvas copy of the Panorama layout)
  const CARD_COLORS = ["#e83e3a", "#2884e8", "#40b254", "#f6c428", "#ff8434", "#28c4d6"];
  function text(str, x, y, font, color, align = "left", stroke = 0) {
    ctx.font = font; ctx.textAlign = align; ctx.textBaseline = "middle";
    if (stroke) { ctx.lineWidth = stroke; ctx.strokeStyle = "rgba(0,0,0,.75)"; ctx.lineJoin = "round"; ctx.strokeText(str, x, y); }
    ctx.fillStyle = color; ctx.fillText(str, x, y);
  }
  function drawHud(hud) {
    const cardW = 420, cardH = 58;
    for (let c = 0; c < 4; c++) {
      const card = hud.cards[c];
      if (!card.show) continue;
      const row = c >> 1, right = c % 2 === 1;
      const x = right ? W - 20 - cardW : 20, y = 16 + row * (cardH + 10);
      ctx.globalAlpha = card.ko ? 0.5 : 1;
      ctx.fillStyle = "rgba(11,12,16,.8)"; ctx.fillRect(x, y, cardW, cardH);
      ctx.fillStyle = CARD_COLORS[card.color] || "#fff"; ctx.fillRect(right ? x + cardW - 5 : x, y, 5, cardH);
      const tx = right ? x + cardW - 16 : x + 16, al = right ? "right" : "left";
      text(card.name.toUpperCase(), tx, y + 15, `700 16px ${FONT_B}`, CARD_COLORS[card.color], al);
      const nameW = ctx.measureText(card.name.toUpperCase()).width;
      text(card.fighter, right ? tx - nameW - 10 : tx + nameW + 10, y + 15, `14px ${FONT_B}`, "#d8d2c4", al);
      if (card.combo) text(card.combo, right ? x + 16 : x + cardW - 16, y + 15, `16px ${FONT_D}`, "#ffd84a", right ? "left" : "right");
      const bx = x + 16, bw = cardW - 32, by = y + 28, bh = 14;
      ctx.fillStyle = "#3c0e0e"; ctx.fillRect(bx, by, bw, bh);
      const fw = bw * card.hp / 100;
      const g = ctx.createLinearGradient(0, by, 0, by + bh);
      if (card.hp > 25) { g.addColorStop(0, "#ffe773"); g.addColorStop(1, "#e8a21c"); } else { g.addColorStop(0, "#ff7a5a"); g.addColorStop(1, "#d42a1a"); }
      ctx.fillStyle = g;
      if (right) ctx.fillRect(bx + bw - fw, by, fw, bh); else ctx.fillRect(bx, by, fw, bh);
      for (let p = 0; p < card.need; p++) {
        ctx.fillStyle = p < card.wins ? "#ffd84a" : "rgba(255,255,255,.18)";
        const px = right ? x + cardW - 22 - p * 16 : x + 22 + p * 16;
        ctx.beginPath(); ctx.arc(px, y + 50, 4.5, 0, Math.PI * 2); ctx.fill();
      }
      ctx.globalAlpha = 1;
    }
    if (hud.timer) text(hud.timer, W / 2, 46, `44px ${FONT_D}`, +hud.timer <= 10 ? "#ff5a3c" : "#fff", "center", 6);
    if (hud.queue) text(hud.queue, W / 2, 84, `600 14px ${FONT_B}`, "#f1ebdd", "center", 4);
    const A = hud.announce;
    if (A.show && A.text) {
      const size = A.style === "ko" ? 120 : A.style === "big" || A.style === "fight" ? 76 : A.style === "win" ? 58 : 32;
      const y = A.style === "sub" ? H * 0.46 : H * 0.36;
      text(A.text, W / 2, y, `${size}px ${FONT_D}`, A.style === "ko" ? "#ff4a3a" : A.style === "fight" ? "#ffd84a" : "#fff", "center", 10);
    }
    if (hud.inLobby) {
      const L = hud.lobby, bx = W / 2 - 360;
      ctx.fillStyle = "rgba(8,9,13,.84)"; ctx.fillRect(bx, 70, 720, 262);
      text(L.title, W / 2, 106, `40px ${FONT_D}`, "#ffd84a", "center");
      text(L.mode, W / 2, 142, `600 16px ${FONT_B}`, "#fff", "center");
      L.lines.forEach((ln, i) => {
        const taken = !!game.seats[i].kind, ready = taken && game.seats[i].ready;
        text(ln, bx + 34, 176 + i * 25, `${i === 0 && mode === "play" ? 700 : 400} 16px ${FONT_B}`, ready ? "#8cf08c" : taken ? "#f4efe4" : "#8b8780");
      });
      text(L.count, W / 2, 290, `700 17px ${FONT_B}`, "#ffd84a", "center");
      text(L.hint, W / 2, 314, `13px ${FONT_B}`, "#bdb7aa", "center");
      const me = hud.seat[0];
      if (me.me && mode === "play") {
        ctx.fillStyle = "rgba(8,9,13,.78)"; ctx.fillRect(W / 2 - 440, H - 124, 880, 82);
        text(me.me, W / 2, H - 106, `700 14px ${FONT_B}`, "#fff", "center");
        text(me.moves, W / 2, H - 86, `13px ${FONT_B}`, "#e3dccc", "center");
        text(me.motions, W / 2, H - 70, `12px ${FONT_B}`, "#aaa396", "center");
        text(me.status, W / 2, H - 52, `700 14px ${FONT_B}`, "#ffd84a", "center");
      }
    }
    text(hud.footer, W / 2, H - 14, `12px ${FONT_B}`, "rgba(255,255,255,.62)", "center");
    if (mode === "attract") {
      const pulse = 0.65 + 0.35 * Math.sin(performance.now() / 380);
      ctx.globalAlpha = pulse;
      text("CLICK TO PLAY", W / 2, H - 52, `30px ${FONT_D}`, "#ffd84a", "center", 8);
      ctx.globalAlpha = 1;
    }
  }

  // ------------------------------------------------------------------ pose gallery
  function drawGallery(kind) {
    const cols = [];
    const add = (label, fn) => cols.push({ label, fn });
    if (kind === "base") {
      for (const n of ["stance", "crouch", "block", "cblock", "air", "hitHigh", "hitMid", "down", "kneel", "dashF", "waiting"]) add(n, (ch) => ch.poses[n]);
      add("victory", (ch) => ch.poses[ch.victory]);
    } else if (kind === "normals") {
      for (const id of ["jab", "straight", "uppercut", "kickMid", "longKick", "roundhouse", "sweep", "airPunch", "airKick", "throw"]) {
        const m = MOVES[id];
        const hitF = m.hits && m.hits.length ? m.hits[0].from : (m.release || 10);
        add(m.name, (ch) => { const mv = ch.moves[id]; const p = newPose(); sampleKeys(mv.keys, Math.round(hitF * (ch.stats.frame || 1)), p, ch); return p; });
      }
    } else {
      for (let k = 0; k < 3; k++) for (const f of [0.3, 0.6]) add("special " + (k + 1) + " · " + Math.round(f * 100) + "%", (ch) => { const mv = ch.moves[ch.specials[k]]; const p = newPose(); sampleKeys(mv.keys, Math.round(mv.total * f), p, ch); return p; });
    }
    const top = 44, cellW = (W - 20) / cols.length, cellH = (H - top - 10) / CHARACTERS.length;
    ctx.fillStyle = "#1b1418"; ctx.fillRect(0, 0, W, H);
    const g = new Game({ halfWidth: 4000 });
    CHARACTERS.forEach((ch, row) => {
      cols.forEach((col, ci) => {
        const f = new Fighter(g, row);
        f.setCharacter(row); f.onStage = true; f.facing = 1; f.x = 0; f.y = 0; f.color = PLAYER_COLORS[row];
        copyPose(col.fn(ch), f.pose);
        f.buildRender();
        const cx = 10 + ci * cellW, cy = top + row * cellH;
        view = { cx: 0, cy: 48, scale: Math.min(cellW / 82, cellH / 118), ox: cx + cellW / 2, oy: cy + cellH * 0.5 };
        ctx.fillStyle = "rgba(255,255,255,.04)"; ctx.fillRect(cx + 2, cy + 2, cellW - 4, cellH - 4);
        ctx.strokeStyle = "rgba(216,164,69,.35)"; ctx.beginPath(); ctx.moveTo(cx + 6, sy(0)); ctx.lineTo(cx + cellW - 6, sy(0)); ctx.stroke();
        for (const q of f.parts.filter((q) => !q.hidden).sort((a, b) => a.depth - b.depth)) drawPart(q);
        if (row === 0) text(col.label, cx + cellW / 2, 24, `600 12px ${FONT_B}`, "#d8d2c4", "center");
      });
      text(ch.name, 16, top + row * cellH + 14, `13px ${FONT_D}`, "#d8a445");
    });
  }

  // ------------------------------------------------------------------ main loop
  let acc = 0, last = performance.now();
  function frame(now) {
    acc += Math.min(0.1, (now - last) / 1000); last = now;
    if (galleryKind) {
      drawGallery(galleryKind);
      $("status").textContent = "pose gallery: " + galleryKind;
      requestAnimationFrame(frame);
      return;
    }
    while (acc >= DT) {
      acc -= DT;
      if (mode === "play") {
        game.fighters[0].setInput(heldFor(map1, 0), pressedSince[0]); pressedSince[0] = 0;
        if (twoP && game.seats[1].kind === "human") { game.fighters[1].setInput(heldFor(map2, 1), pressedSince[1]); pressedSince[1] = 0; }
      }
      game.step();
      game.events.length = 0;
      if (mode === "attract" && game.phase === "lobby") { game.forceStart(); }
    }
    setView(game.cam);
    ctx.clearRect(0, 0, W, H);
    drawStage(game.halfW);
    drawWorld(game.renderState());
    drawHud(game.hud);
    $("status").textContent = (mode === "attract" ? "attract mode · " : "") + MODE_LABEL[game.mode] + " · " + game.phase;
    requestAnimationFrame(frame);
  }

  buildCast();
  buildFrames();
  startAttract();
  if (query.has("gallery")) galleryKind = query.get("gallery") || "base";
  requestAnimationFrame(frame);
})();
