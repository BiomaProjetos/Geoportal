/* Geoportal Bioma — interface (desktop e celular) */
(() => {
"use strict";
const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
const fmt = (v, d = 2) => v == null || isNaN(v) ? "—" : Number(v).toLocaleString("pt-BR", {minimumFractionDigits: d, maximumFractionDigits: d});
const brl = v => v == null ? "—" : Number(v).toLocaleString("pt-BR", {style: "currency", currency: "BRL", maximumFractionDigits: 0});
const dataBR = s => s ? new Date(s).toLocaleString("pt-BR", {dateStyle: "short", timeStyle: "short"}) : "—";
const normCar = s => String(s || "").replace(/\s+/g, "").toUpperCase();
const guardar = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };
const ler = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };

function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("show"); clearTimeout(toast.h); toast.h = setTimeout(() => t.classList.remove("show"), 4000); }

async function api(path, opts = {}) {
  const o = {credentials: "same-origin", ...opts};
  if (o.body && !(o.body instanceof FormData) && typeof o.body !== "string") { o.body = JSON.stringify(o.body); o.headers = {"Content-Type": "application/json", ...(o.headers || {})}; }
  const r = await fetch(path, o);
  if (r.status === 401 && !path.startsWith("/api/login")) { location.href = "/login.html"; throw new Error("Sessão expirada"); }
  let d = null; try { d = await r.json(); } catch (e) {}
  if (!r.ok) throw new Error((d && d.erro) || `Erro ${r.status}`);
  return d;
}

const IC = {
  shield: '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6l-8-3z"/>', ban: '<circle cx="12" cy="12" r="9"/><path d="m6 6 12 12"/>',
  tree: '<path d="M12 22v-6M7 16h10l-3-4h2l-4-5-4 5h2z"/>', flame: '<path d="M12 22a7 7 0 0 0 7-7c0-4-3-6-4-10-2 2-2 4-3 5-1-1-2-2-2-4-3 3-5 6-5 9a7 7 0 0 0 7 7z"/>',
  map: '<path d="M9 3 3 6v15l6-3 6 3 6-3V3l-6 3-6-3z"/><path d="M9 3v15M15 6v15"/>', bank: '<path d="M3 10h18L12 4zM5 10v8M9 10v8M15 10v8M19 10v8M3 20h18"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2 20c0-3.5 3-6 7-6s7 2.5 7 6M16 4.5a3.5 3.5 0 0 1 0 7M18 14c2.5.6 4 2.8 4 6"/>', check: '<path d="M5 12.5 10 17 19 7"/>',
  file: '<path d="M14 3H6v18h12V7z"/><path d="M14 3v4h4M9 13h6M9 17h6"/>', layers: '<path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/>',
  alert: '<path d="M12 4 2 20h20z"/><path d="M12 10v4M12 17v.5"/>', leaf: '<path d="M7 20c8 0 13-6 13-16C10 4 5 9 5 16c0 1 .1 2 .3 3"/><path d="M5 20 15 10"/>',
  refresh: '<path d="M20 11a8 8 0 1 0-2 5.3M20 4v7h-7"/>', upload: '<path d="M12 15V3M7 8l5-5 5 5M4 15v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/>', pin: '<path d="M12 21s7-6 7-12a7 7 0 0 0-14 0c0 6 7 12 7 12z"/><circle cx="12" cy="9" r="2.5"/>'
};
const icon = (k, s = 18, w = 2) => `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${IC[k] || IC.alert}</svg>`;
const LV = {critico: {bg: "var(--t-red)", fg: "var(--bad)"}, atencao: {bg: "var(--t-amber)", fg: "var(--warn)"}, ok: {bg: "var(--t-green)", fg: "var(--ok)"}, info: {bg: "var(--t-blue)", fg: "var(--info)"}};
const SITU = {"Em análise": "p-blue", "Enviado": "p-blue", "Aguardando complementação": "p-amber", "Aguardando análise": "p-violet", "Aprovado": "p-green", "Prospecção": "p-violet", "Distribuído": "p-teal", "Arquivado": "p-teal"};
const IM_STY = {
  ATP: {color: "#44e38a", weight: 3, fill: false}, AVN: {color: "#1f5c2c", weight: 0, fillColor: "#2f6d3b", fillOpacity: .75},
  AC: {color: "#c8b37a", weight: 0, fillColor: "#c2ad72", fillOpacity: .6}, APP: {color: "#3fb6c4", weight: 1, fillColor: "#3fb6c4", fillOpacity: .5},
  ARL: {color: "#9cf5b0", weight: 2, dashArray: "6 4", fillColor: "#9cf5b0", fillOpacity: .08}, AUAS: {color: "#e67e22", weight: 1, fillColor: "#e67e22", fillOpacity: .45},
  HIDRO: {color: "#5aa9e6", weight: 2, fillColor: "#5aa9e6", fillOpacity: .5}, OUTRO: {color: "#cfd8dc", weight: 1, fillColor: "#cfd8dc", fillOpacity: .2}
};
const IM_ORDEM = ["AC", "AUAS", "AVN", "ARL", "APP", "HIDRO", "OUTRO", "ATP"];

let USER, CFG, IMOVEIS = [], cur = null, tab = "triagem", map, imLayers = {}, refLayers = {}, abortRef = {}, gps = null;
const vis = {};

/* ---------------- mapa ---------------- */
function initMap() {
  map = L.map("map", {zoomControl: false, minZoom: 4, maxZoom: 18, attributionControl: false}).setView([-13, -56], 6);
  L.control.zoom({position: "bottomleft"}).addTo(map);
  L.control.scale({imperial: false, position: "bottomleft"}).addTo(map);
  const sel = $("#fundoSel"); let base = null;
  sel.innerHTML = CFG.fundos.map((f, i) => `<option value="${i}">${esc(f.nome)}</option>`).join("") + '<option value="-1">Sem fundo</option>';
  const porFundo = i => { if (base) map.removeLayer(base); base = null; const f = CFG.fundos[i];
    $("#atrib").textContent = f ? f.atribuicao : ""; if (f) base = L.tileLayer(f.url, {maxZoom: 18, maxNativeZoom: f.max_zoom || 18}).addTo(map); guardar("gp_fundo", i); };
  const ini = Number(ler("gp_fundo") ?? 0); sel.value = String(ini); porFundo(ini);
  sel.addEventListener("change", () => porFundo(Number(sel.value)));
  map.on("mousemove", e => { $("#coord").textContent = `${e.latlng.lat.toFixed(5)}, ${e.latlng.lng.toFixed(5)}`; });
  let h; map.on("moveend", () => { clearTimeout(h); h = setTimeout(atualizarRefs, 250); });
}
function tabelaAttrs(obj, titulo) {
  const linhas = Object.entries(obj || {}).filter(([k, v]) => v !== null && v !== "" && k !== "tipo").slice(0, 14);
  return `<div class="pop"><h4>${esc(titulo)}</h4><table>${linhas.map(([k, v]) => `<tr><td>${esc(k)}</td><td><b>${esc(v)}</b></td></tr>`).join("")}</table></div>`;
}
function estiloRef(c) { return {color: c.cor, weight: 1.6, dashArray: c.tracejado || null, fill: c.preenchimento !== false, fillColor: c.cor, fillOpacity: .15}; }
async function atualizarRefs() {
  const z = map.getZoom(), b = map.getBounds(), bbox = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()].map(v => v.toFixed(5)).join(",");
  const longe = [];
  for (const c of CFG.camadas) {
    if (!c.carregada) continue;
    if (!vis[c.slug] || z < c.min_zoom) { if (refLayers[c.slug]) { map.removeLayer(refLayers[c.slug]); delete refLayers[c.slug]; } if (vis[c.slug] && z < c.min_zoom) longe.push(c.nome); continue; }
    if (abortRef[c.slug]) abortRef[c.slug].abort();
    const ctl = abortRef[c.slug] = new AbortController();
    fetch(`/api/camadas/${c.slug}/geojson?bbox=${bbox}&z=${z}`, {credentials: "same-origin", signal: ctl.signal})
      .then(r => r.ok ? r.json() : null).then(gj => {
        if (!gj || ctl.signal.aborted) return;
        if (refLayers[c.slug]) map.removeLayer(refLayers[c.slug]);
        refLayers[c.slug] = L.geoJSON(gj, {style: () => estiloRef(c), pointToLayer: (f, ll) => L.circleMarker(ll, {radius: 5, ...estiloRef(c), fillOpacity: .7}),
          onEachFeature: (f, l) => l.bindPopup(tabelaAttrs(f.properties, c.nome))}).addTo(map);
        if (imLayers.ATP) imLayers.ATP.bringToFront();
      }).catch(() => {});
  }
  const av = $("#avisoMapa"); av.hidden = !longe.length;
  if (longe.length) av.textContent = `Aproxime o mapa para ver: ${longe.slice(0, 3).join(", ")}${longe.length > 3 ? "…" : ""}`;
}
function desenharImovel() {
  Object.values(imLayers).forEach(l => map.removeLayer(l)); imLayers = {};
  if (!cur) return;
  for (const f of cur.geojson.features) {
    const t = IM_STY[f.properties.tipo] ? f.properties.tipo : "OUTRO";
    (imLayers[t] = imLayers[t] || L.featureGroup());
    L.geoJSON(f, {style: IM_STY[t]}).bindPopup(tabelaAttrs(t === "ATP" ? {CAR: cur.car, Área: fmt(cur.area_ha) + " ha", Município: cur.municipio} : f.properties, nomeTipo(t))).addTo(imLayers[t]);
  }
  aplicarVisImovel();
  if (imLayers.ATP) map.fitBounds(imLayers.ATP.getBounds(), {padding: [50, 50]});
}
function aplicarVisImovel() { IM_ORDEM.forEach(t => { const l = imLayers[t]; if (!l) return; if (vis["im_" + t] !== false) { l.addTo(map); l.bringToFront(); } else map.removeLayer(l); }); }
const nomeTipo = t => (CFG.imovel_tipos.find(x => x.tipo === t) || {nome: t === "OUTRO" ? "Outras camadas do CAR" : t}).nome;

/* GPS: só mostra na tela, nada é gravado */
$("#btnGps").addEventListener("click", () => {
  const b = $("#btnGps");
  if (gps) { navigator.geolocation.clearWatch(gps.id); map.removeLayer(gps.layer); gps = null; b.classList.remove("on"); return; }
  if (!navigator.geolocation) return toast("Este aparelho não informa a posição.");
  const layer = L.featureGroup().addTo(map); let primeiro = true;
  const id = navigator.geolocation.watchPosition(p => {
    const ll = [p.coords.latitude, p.coords.longitude]; layer.clearLayers();
    L.circle(ll, {radius: p.coords.accuracy, color: "#3576d6", weight: 1, fillOpacity: .12}).addTo(layer);
    L.circleMarker(ll, {radius: 7, color: "#fff", weight: 2, fillColor: "#3576d6", fillOpacity: 1}).addTo(layer);
    if (primeiro) { map.setView(ll, Math.max(map.getZoom(), 15)); primeiro = false; }
  }, e => { toast("Não consegui a posição: " + e.message); }, {enableHighAccuracy: true, maximumAge: 10000});
  gps = {id, layer}; b.classList.add("on");
});

/* ---------------- árvore de camadas ---------------- */
function renderTree() {
  const q = $("#layerFilter").value.trim().toLowerCase();
  const grupos = [];
  if (cur) {
    const tipos = IM_ORDEM.slice().reverse().filter(t => cur.geojson.features.some(f => (IM_STY[f.properties.tipo] ? f.properties.tipo : "OUTRO") === t));
    grupos.push({g: "Imóvel em análise", itens: tipos.map(t => ({k: "im_" + t, nome: nomeTipo(t), sty: IM_STY[t], ok: true}))});
  }
  const por = {};
  CFG.camadas.forEach(c => { (por[c.grupo] = por[c.grupo] || []).push({k: c.slug, nome: c.nome, sty: estiloRef(c), ok: c.carregada, c}); });
  Object.entries(por).forEach(([g, itens]) => grupos.push({g, itens}));
  $("#tree").innerHTML = grupos.map((gr, gi) => {
    const its = gr.itens.filter(i => !q || i.nome.toLowerCase().includes(q)); if (!its.length) return "";
    return `<div class="grp"><button type="button" aria-expanded="true">${esc(gr.g)}<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="m6 9 6 6 6-6"/></svg></button><div class="items">${its.map(i => {
      const s = i.sty, sw = `<span class="swatch" style="border-color:${s.color};background:${s.fill === false ? "transparent" : (s.fillColor || "transparent")};${s.dashArray ? "border-style:dashed" : ""}"></span>`;
      if (!i.ok) return `<div class="li off" title="Base ainda não importada no servidor"><span class="sw"></span>${sw}<span>${esc(i.nome)}</span><span class="cnt">sem base</span></div>`;
      const on = i.k.startsWith("im_") ? vis[i.k] !== false : !!vis[i.k];
      const tit = i.c && i.c.versao_em ? ` title="${esc(i.c.fonte || "")} · base de ${new Date(i.c.versao_em).toLocaleDateString("pt-BR")}"` : "";
      return `<label class="li"${tit}><input type="checkbox" data-k="${i.k}" ${on ? "checked" : ""}><span class="sw"></span>${sw}<span>${esc(i.nome)}</span></label>`;
    }).join("")}</div></div>`;
  }).join("");
}
$("#tree").addEventListener("change", e => { const k = e.target.dataset.k; if (!k) return; vis[k] = e.target.checked;
  if (k.startsWith("im_")) aplicarVisImovel(); else { guardar("gp_vis", JSON.stringify(vis)); atualizarRefs(); } });
$("#tree").addEventListener("click", e => { const b = e.target.closest(".grp>button"); if (!b) return; const g = b.parentElement; g.classList.toggle("closed"); b.setAttribute("aria-expanded", !g.classList.contains("closed")); });
$("#layerFilter").addEventListener("input", renderTree);

/* ---------------- imóvel e triagem ---------------- */
async function abrir(car) {
  $("#aBody").innerHTML = `<div class="empty"><span class="spin"></span> Carregando ${esc(car)}…</div>`;
  try {
    cur = await api("/api/imovel?car=" + encodeURIComponent(car));
    if (!cur.triagem) cur.triagem = await api("/api/triagem?car=" + encodeURIComponent(cur.car), {method: "POST"});
  } catch (e) { cur = null; renderPanel(); toast(e.message); return; }
  guardar("gp_ultimo", cur.car); $("#searchInput").value = cur.car; tab = "triagem";
  desenharImovel(); renderTree(); renderPanel();
}
async function recalcular() {
  if (!cur) return; const b = $("#btnRecalc"); if (b) b.classList.add("carregando");
  try { cur.triagem = await api("/api/triagem?car=" + encodeURIComponent(cur.car), {method: "POST"}); renderPanel(); carregarImoveis(); toast("Triagem recalculada com as bases atuais."); }
  catch (e) { toast(e.message); } finally { if (b) b.classList.remove("carregando"); }
}
async function editar(campos) {
  try { await api("/api/imovel?car=" + encodeURIComponent(cur.car), {method: "PATCH", body: campos}); Object.assign(cur, campos); toast("Alteração salva."); carregarImoveis(); }
  catch (e) { toast(e.message); }
}
function renderPanel() {
  if (!cur) { $("#aHead").innerHTML = ""; $("#tabs").innerHTML = "";
    $("#aBody").innerHTML = `<div class="empty">${icon("pin", 28, 1.6)}<p>Busque um CAR pelo número ou importe o zip exportado do Geoportal SEMA.</p><button class="btn primary" type="button" data-novo>${icon("upload", 15)}Importar CAR</button></div>`;
    $("#mdot").style.background = "transparent"; return; }
  const T = cur.triagem || {flags: [], servicos: [], sobreposicoes: [], desmatamento: {anos: []}, reserva_legal: {}, custeio: [], resumo: {}};
  const rl = T.reserva_legal || {};
  $("#aHead").innerHTML = `<div class="eyebrow">${esc(cur.origem)}${cur.analista ? " · " + esc(cur.analista) : ""}</div><h3>${esc(cur.nome || "Imóvel sem nome")}</h3>
   <div class="a-meta"><span class="mono"><b>${esc(cur.car)}</b></span><span><b class="num">${fmt(cur.area_ha)}</b> ha</span><span>${esc(cur.municipio || "município não informado")}</span>${rl.modulos_fiscais != null ? `<span><b class="num">${fmt(rl.modulos_fiscais, 1)}</b> MF</span>` : ""}</div>
   <div class="hdr-edit"><select id="edSitu" aria-label="Situação">${CFG.situacoes.map(s => `<option ${s === cur.situacao ? "selected" : ""}>${esc(s)}</option>`).join("")}</select>
   <select id="edOrig" aria-label="Origem">${["Prospecção", "Carteira Bioma"].map(s => `<option ${s === cur.origem ? "selected" : ""}>${s}</option>`).join("")}</select></div>
   <div class="a-actions"><button class="btn primary" type="button" id="btnRecalc">${icon("refresh", 15)}Recalcular triagem</button><button class="btn" type="button" data-novo="${esc(cur.car)}">${icon("upload", 15)}Reimportar CAR</button></div>`;
  $("#edSitu").onchange = e => editar({situacao: e.target.value});
  $("#edOrig").onchange = e => editar({origem: e.target.value});
  $("#btnRecalc").onclick = recalcular;
  const pior = (T.flags || []).some(f => f.nivel === "critico") ? "var(--bad)" : (T.flags || []).some(f => f.nivel === "atencao") ? "var(--warn)" : "var(--ok)";
  const nOv = (T.sobreposicoes || []).filter(s => s.n > 0).length;
  const tabs = [["triagem", "Triagem", pior], ["sobrep", "Sobreposições", null, nOv], ["desmate", "Desmatamento", (T.desmatamento || {}).pos_marco_ha > 0.01 ? "var(--bad)" : null],
    ["georref", "Georref.", null], ["custeio", "Custeio", (T.custeio || []).some(k => k.desmate || k.embargo) ? "var(--bad)" : null], ["rl", "Reserva Legal", rl.saldo_ha < 0 ? "var(--bad)" : null]];
  $("#tabs").innerHTML = tabs.map(t => `<button type="button" role="tab" data-t="${t[0]}" class="${t[0] === tab ? "on" : ""}" aria-selected="${t[0] === tab}">${t[2] ? `<span class="dot" style="background:${t[2]}"></span>` : ""}${t[1]}${t[3] ? ` <span class="muted">${t[3]}</span>` : ""}</button>`).join("");
  $("#aBody").innerHTML = VIEWS[tab](T); $("#aBody").scrollTop = 0;
  $("#mdot").style.background = pior;
  const f = $("#formPct"); if (f) f.onsubmit = e => { e.preventDefault(); const v = $("#inPct").value; editar({pct_rl: v === "" ? null : Number(v)}).then(() => abrir(cur.car)); };
}
$("#tabs").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; tab = b.dataset.t; renderPanel(); });

const flagHTML = f => { const c = LV[f.nivel] || LV.info; return `<div class="flag"><span class="ico" style="background:${c.bg};color:${c.fg}">${icon(f.icone, 18)}</span><div style="min-width:0"><b>${esc(f.titulo)}</b><small>${esc(f.detalhe)}</small></div><span class="v num" style="color:${c.fg}">${esc(f.valor)}</span></div>`; };
const basesNota = T => `<p class="bases-info">Calculado em ${dataBR(T.calculado_em)}.${(T.bases_nao_carregadas || []).length ? ` <b>Bases ainda não importadas:</b> ${T.bases_nao_carregadas.map(esc).join(", ")}.` : ""} Triagem preliminar por geoprocessamento; não substitui a análise do analista nem a validação da SEMA-MT.</p>`;
const VIEWS = {
  triagem(T) {
    const u = T.uso_solo || {}, A = cur.area_ha || 0;
    const seg = [[u.avn_ha, "var(--ok)", "Vegetação nativa"], [u.app_ha, "#3fb6c4", "APP"], [u.ac_declarada_ha, "#c2ad72", "Consolidada declarada"], [u.desmate_pos_ha, "var(--bad)", "Desmate pós-2008"]].filter(s => s[0] != null);
    const medidor = seg.length && A ? `<div class="card"><h5>Uso do solo no imóvel</h5><div class="meter" role="img" aria-label="Distribuição do uso do solo">${seg.map(s => `<i style="width:${Math.max(0, s[0]) / A * 100}%;background:${s[1]}"></i>`).join("")}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px 12px;margin-top:10px;font-size:12px">${seg.map(s => `<span style="display:flex;align-items:center;gap:6px"><i style="width:9px;height:9px;border-radius:2px;background:${s[1]};flex:none"></i>${s[2]} <b class="num" style="margin-left:auto">${fmt(s[0])} ha</b></span>`).join("")}</div></div>`
      : `<div class="card small muted">O zip importado não trouxe AVN, APP ou área consolidada. Reimporte com as camadas do Simcar Digital para ver o uso do solo.</div>`;
    return `${medidor}<div class="flags">${(T.flags || []).map(flagHTML).join("") || '<div class="card small muted">Nenhum cruzamento disponível: importe as bases de referência no servidor.</div>'}</div>
      ${(T.servicos || []).length ? `<div class="card"><h5>Serviços que este imóvel pede</h5><div class="svc">${T.servicos.map(s => `<span>${esc(s)}</span>`).join("")}</div></div>` : (T.flags || []).length ? `<div class="clear"><b>${icon("check", 16, 2.6)}Sem pendências na triagem</b>Bom candidato para acompanhamento e renovações.</div>` : ""}
      ${basesNota(T)}`;
  },
  sobrep(T) {
    const com = (T.sobreposicoes || []).filter(s => s.n > 0), sem = (T.sobreposicoes || []).filter(s => !s.n);
    const cor = n => (LV[n] || LV.info).fg;
    return `${com.map(s => `<div class="ov"><span class="d" style="background:${cor(s.nivel)}"></span><div style="min-width:0"><b>${esc(s.camada)}</b><div class="small muted">${s.n} feição(ões)</div></div><div class="r"><b class="num">${fmt(s.ha)} ha</b></div></div>`).join("")}
      ${sem.length ? `<div class="clear"><b>${icon("check", 16, 2.6)}Sem sobreposição em ${sem.length} base(s)</b><ul>${sem.map(s => `<li>✓ ${esc(s.camada)}</li>`).join("")}</ul></div>` : ""}
      ${!com.length && !sem.length ? '<div class="card small muted">Nenhuma base de referência importada ainda.</div>' : ""}${basesNota(T)}`;
  },
  desmate(T) {
    const D = T.desmatamento || {anos: []}, by = {};
    (D.anos || []).forEach(a => { if (a.ano) by[a.ano] = (by[a.ano] || 0) + a.ha; });
    const anoFim = new Date().getFullYear(), anos = []; for (let y = 2001; y <= anoFim; y++) anos.push(y);
    const mx = Math.max(1, ...Object.values(by)), step = mx > 60 ? 20 : mx > 30 ? 10 : mx > 12 ? 5 : mx > 5 ? 2 : 1, top = Math.ceil(mx / step) * step;
    const W = 360, H = 170, l = 34, r = 8, t = 14, b = 26, cw = (W - l - r) / anos.length, ys = v => t + (H - t - b) * (1 - v / top);
    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Desmatamento PRODES por ano no imóvel">`;
    for (let v = 0; v <= top; v += step) svg += `<line class="gl" x1="${l}" x2="${W - r}" y1="${ys(v)}" y2="${ys(v)}"/><text x="${l - 5}" y="${ys(v) + 3}" text-anchor="end">${v}</text>`;
    anos.forEach((y, i) => { const v = by[y] || 0, x = l + i * cw + 1.5; if (v > 0) svg += `<rect x="${x}" y="${ys(v)}" width="${Math.max(1, cw - 3)}" height="${ys(0) - ys(v)}" rx="2" fill="${y >= D.ano_pos_marco ? "var(--bad)" : "var(--warn)"}"><title>${y}: ${fmt(v)} ha</title></rect>`; if (y % 4 === 1) svg += `<text x="${x + (cw - 3) / 2}" y="${H - 10}" text-anchor="middle">${y}</text>`; });
    const mk = l + (D.ano_pos_marco - 2001) * cw;
    svg += `<line x1="${mk}" x2="${mk}" y1="${t - 4}" y2="${ys(0)}" stroke="var(--fg)" stroke-dasharray="3 3"/><text x="${mk + 4}" y="${t + 4}" style="fill:var(--fg);font-weight:600">22/07/2008</text><text x="${l}" y="${H - 1}">ha</text></svg>`;
    const lista = Object.entries(by).sort((a, b) => b[0] - a[0]);
    return `<div class="card chart"><h5>PRODES ano a ano dentro do imóvel</h5>${svg}<p class="note" style="margin:8px 0 0">O ano PRODES vai de agosto a julho: supressão em PRODES ${D.ano_pos_marco} em diante ocorreu depois do marco de 22/07/2008.</p></div>
      <dl class="kv card"><dt>Até PRODES ${D.ano_pos_marco - 1}</dt><dd>${fmt(D.pre_marco_ha)} ha</dd><dt>PRODES ${D.ano_pos_marco} em diante</dt><dd style="color:${D.pos_marco_ha > 0.01 ? "var(--bad)" : "inherit"}">${fmt(D.pos_marco_ha)} ha</dd></dl>
      ${lista.length ? `<div class="card"><div class="tbl-wrap"><table class="t"><thead><tr><th>Ano PRODES</th><th>Marco</th><th class="r">Área (ha)</th></tr></thead><tbody>${lista.map(([y, v]) => `<tr><td class="num">${y}</td><td>${y >= D.ano_pos_marco ? '<span class="pill p-red">Após</span>' : '<span class="pill p-amber">Antes</span>'}</td><td class="r">${fmt(v)}</td></tr>`).join("")}</tbody></table></div></div>` : ""}${basesNota(T)}`;
  },
  georref(T) {
    const g = T.georref;
    if (!g) return `<div class="flag"><span class="ico" style="background:var(--t-amber);color:var(--warn)">${icon("map", 18)}</span><div><b>Sem parcela certificada encontrada</b><small>Nenhuma parcela SIGEF ou certificação SNCI cobre o perímetro do CAR, ou as bases do INCRA ainda não foram importadas.</small></div><span></span></div>${basesNota(T)}`;
    const d = g.dif_pct || 0;
    return `<dl class="kv card"><dt>Fonte</dt><dd>${esc(g.fonte)}</dd><dt>Código</dt><dd class="mono">${esc(g.codigo || "—")}</dd><dt>Área certificada</dt><dd>${fmt(g.area_ha)} ha</dd><dt>Área do CAR</dt><dd>${fmt(cur.area_ha)} ha</dd>
      <dt class="total">Diferença</dt><dd class="total" style="color:${Math.abs(d) > 1 ? "var(--warn)" : "var(--ok)"}">${d > 0 ? "+" : ""}${fmt(d)}%</dd><dt>Área comum</dt><dd>${fmt(g.comum_ha)} ha</dd></dl>
      <div class="card small">${Math.abs(d) > 1 ? "A diferença passa de 1%. Vale retificar o perímetro do CAR para coincidir com a parcela certificada." : "O perímetro do CAR acompanha a parcela certificada."}</div>${basesNota(T)}`;
  },
  custeio(T) {
    const C = T.custeio || [];
    if (!C.length) return `<div class="empty" style="padding:24px 8px">${icon("bank", 28, 1.6)}<p>Nenhuma gleba de crédito rural do Sicor sobre este imóvel.</p></div><p class="note">Nem toda operação de crédito rural informa as coordenadas da gleba.</p>${basesNota(T)}`;
    const tot = C.reduce((s, k) => s + (k.valor || 0), 0);
    return `<dl class="kv card"><dt>Glebas no imóvel</dt><dd>${C.length}</dd><dt>Valor somado</dt><dd>${tot ? brl(tot) : "—"}</dd><dt>Glebas com conflito</dt><dd style="color:${C.some(k => k.desmate || k.embargo) ? "var(--bad)" : "var(--ok)"}">${C.filter(k => k.desmate || k.embargo).length}</dd></dl>
      <div class="card"><div class="tbl-wrap"><table class="t"><thead><tr><th>Safra</th><th>Instituição · cultura</th><th class="r">Gleba (ha)</th><th class="r">Valor</th></tr></thead><tbody>${C.map(k => `<tr><td class="num">${esc(k.ano || "—")}${k.desmate || k.embargo ? `<div><span class="pill p-red" style="margin-top:4px">${k.embargo ? "Embargo" : "Desmate pós-2008"}</span></div>` : ""}</td><td>${esc(k.instituicao || "—")}<div class="small muted">${esc([k.finalidade, k.cultura].filter(Boolean).join(" · "))}</div></td><td class="r">${fmt(k.ha)}</td><td class="r">${brl(k.valor)}</td></tr>`).join("")}</tbody></table></div></div>
      <p class="note">Fonte: microdados do Sicor (Banco Central), anonimizados. O vínculo com o imóvel é feito por sobreposição espacial da gleba.</p>`;
  },
  rl(T) {
    const r = T.reserva_legal || {};
    const saldo = (v) => v == null ? "—" : `<span style="color:${v < 0 ? "var(--bad)" : "var(--ok)"}">${v < 0 ? "" : "+"}${fmt(v)} ha</span>`;
    return `<dl class="kv card"><dt>Área do imóvel</dt><dd>${fmt(r.area_ha)} ha</dd><dt>Fitofisionomia (RADAM)</dt><dd style="font-weight:500">${esc(r.fitofisionomia || "—")}</dd>
      <dt>Percentual exigido</dt><dd>${esc(r.pct_texto || "não definido")}</dd><dt>RL exigida</dt><dd>${r.exigida_ha != null ? fmt(r.exigida_ha) + " ha" : "—"}</dd>
      <dt>Vegetação nativa (AVN)</dt><dd>${r.avn_ha != null ? fmt(r.avn_ha) + " ha" : "não veio no zip"}</dd><dt class="total">Saldo</dt><dd class="total">${saldo(r.saldo_ha)}</dd></dl>
      <div class="card"><h5>Com a APP computada na RL (art. 15)</h5><dl class="kv"><dt>APP</dt><dd>${r.app_ha != null ? fmt(r.app_ha) + " ha" : "—"}</dd><dt>Saldo com APP</dt><dd>${saldo(r.saldo_com_app_ha)}</dd></dl>
      <p class="note" style="margin:8px 0 0">Vale se o cômputo não levar a novo desmate, se a APP estiver conservada ou em recuperação e se o imóvel estiver no CAR.</p></div>
      <div class="card"><h5>Como o passivo pode ser resolvido</h5><dl class="kv"><dt>Recompor (desmate pós-2008)</dt><dd>${r.saldo_ha != null ? fmt(Math.min(r.desmate_pos_ha || 0, Math.max(0, -r.saldo_ha))) + " ha" : "—"}</dd><dt>Recompor ou compensar</dt><dd>${r.saldo_ha != null ? fmt(Math.max(0, -r.saldo_ha - (r.desmate_pos_ha || 0))) + " ha" : "—"}</dd>
      <dt>Módulos fiscais</dt><dd>${r.modulos_fiscais != null ? fmt(r.modulos_fiscais, 1) + ` MF (${fmt(r.mf_ha, 0)} ha/MF)` : "município sem módulo cadastrado"}</dd></dl></div>
      <form class="card" id="formPct" style="display:flex;gap:10px;align-items:flex-end;flex-wrap:wrap"><label class="fld" style="flex:1;min-width:160px">Definir percentual de RL manualmente (%)<input id="inPct" type="number" min="0" max="100" step="1" value="${cur.pct_rl ?? ""}" placeholder="Usar o RADAM"></label><button class="btn" type="submit">Salvar e recalcular</button></form>
      <p class="note">Estimativa preliminar. O cálculo final usa a área líquida do CAR, a vegetação na data do marco e o Decreto Estadual 1.031/2017.</p>`;
  }
};

/* ---------------- busca ---------------- */
$("#searchForm").addEventListener("submit", async e => {
  e.preventDefault(); const v = normCar($("#searchInput").value); if (!v) return;
  const achou = IMOVEIS.find(i => i.car === v || i.car.replace(/\D/g, "") === v.replace(/\D/g, ""));
  if (achou) { setMob("map"); return abrir(achou.car); }
  if (CFG.busca_sema) {
    toast("Buscando o CAR na SEMA-MT…");
    try { const r = await api("/api/imovel/sema", {method: "POST", body: {car: v}}); await carregarImoveis(); return abrir(r.car); }
    catch (err) { toast(err.message); }
  } else { abrirNovo(v); toast("CAR ainda não cadastrado. Importe o zip exportado do Geoportal SEMA."); }
});

/* ---------------- carteira ---------------- */
let cartF = "all";
async function carregarImoveis() {
  try { IMOVEIS = await api("/api/imoveis"); } catch (e) { return; }
  $("#navCount").textContent = IMOVEIS.length;
  $("#carList").innerHTML = IMOVEIS.map(i => `<option value="${esc(i.car)}">${esc(i.nome || "")}</option>`).join("");
  renderKpis(); renderCart();
}
function renderKpis() {
  const n = (...s) => IMOVEIS.filter(i => s.includes(i.situacao)).length;
  const k = [["Total de CARs", IMOVEIS.length, "var(--t-green)", "var(--ok)", "layers"], ["Em análise", n("Em análise", "Distribuído", "Enviado"), "var(--t-blue)", "var(--info)", "file"],
    ["Aguardando com.", n("Aguardando complementação"), "var(--t-amber)", "var(--warn)", "alert"], ["Aprovados", n("Aprovado"), "var(--t-green)", "var(--ok)", "check"],
    ["Prospecção", IMOVEIS.filter(i => i.origem === "Prospecção").length, "var(--t-violet)", "var(--violet)", "pin"]];
  $("#kpis").innerHTML = k.map(x => `<div class="kpi"><div class="top"><span class="ico" style="background:${x[2]};color:${x[3]}">${icon(x[4], 18)}</span>${x[0]}</div><div class="n num">${x[1]}</div></div>`).join("");
}
function resumoHTML(r) {
  if (!r) return '<span class="small muted">Não triado</span>';
  const p = [];
  if (r.criticos) p.push(`<span class="pill p-red">${r.criticos} crítico${r.criticos > 1 ? "s" : ""}</span>`);
  if (r.atencao) p.push(`<span class="pill p-amber">${r.atencao} atenção</span>`);
  return p.join(" ") || '<span class="pill p-green">Sem pendências</span>';
}
function renderCart() {
  const q = $("#cartSearch").value.trim().toLowerCase();
  const rows = IMOVEIS.filter(i => (cartF === "all" || i.origem === cartF) && (!q || [i.car, i.nome, i.municipio, i.proprietario].join(" ").toLowerCase().includes(q)));
  $("#cartTable").innerHTML = `<thead><tr><th>Número CAR</th><th>Imóvel</th><th>Município</th><th class="r">Área (ha)</th><th>Situação</th><th>Origem</th><th>Triagem</th></tr></thead><tbody>${rows.map(i => `<tr data-car="${esc(i.car)}" tabindex="0">
    <td class="carno">${esc(i.car)}</td><td><b style="font-weight:600">${esc(i.nome || "—")}</b><div class="small muted">${esc(i.proprietario || "")}</div></td><td>${esc(i.municipio || "—")}</td>
    <td class="r">${fmt(i.area_ha)}</td><td><span class="pill ${SITU[i.situacao] || "p-blue"}">${esc(i.situacao)}</span></td>
    <td>${i.origem === "Prospecção" ? '<span class="pill p-violet">Prospecção</span>' : '<span class="muted small">Carteira Bioma</span>'}</td><td><div class="alerts" style="gap:6px">${resumoHTML(i.resumo)}</div></td></tr>`).join("")
    || `<tr><td colspan="7" class="empty">${IMOVEIS.length ? "Nenhum CAR com esse filtro." : "Nenhum CAR cadastrado ainda. Use “Importar CAR”."}</td></tr>`}</tbody>`;
}
$("#cartSearch").addEventListener("input", renderCart);
$("#cartSeg").addEventListener("click", e => { const b = e.target.closest("button"); if (!b) return; cartF = b.dataset.f; $$("#cartSeg button").forEach(x => x.classList.toggle("on", x === b)); renderCart(); });
const irPara = car => { location.hash = "#geoportal"; route(); setMob("analysis"); abrir(car); };
$("#cartTable").addEventListener("click", e => { const tr = e.target.closest("tr[data-car]"); if (tr) irPara(tr.dataset.car); });
$("#cartTable").addEventListener("keydown", e => { if (e.key === "Enter") { const tr = e.target.closest("tr[data-car]"); if (tr) irPara(tr.dataset.car); } });

/* ---------------- importar CAR ---------------- */
const dlg = $("#dlgNovo"); let arquivo = null;
function abrirNovo(car = "") {
  $("#formNovo").reset(); arquivo = null; $("#fNomeArq").textContent = ""; $("#fErro").textContent = ""; $("#fCar").value = car || "";
  if (car && cur && cur.car === car) { $("#fOrigem").value = cur.origem; $("#fNome").value = cur.nome || ""; $("#fMun").value = cur.municipio || ""; $("#fProp").value = cur.proprietario || ""; $("#fAnalista").value = cur.analista || ""; }
  dlg.showModal();
}
document.addEventListener("click", e => { const b = e.target.closest("[data-novo]"); if (b) abrirNovo(b.dataset.novo || ""); });
$("#btnNovo").onclick = () => abrirNovo(); $("#btnNovoMapa").onclick = () => abrirNovo();
const escolher = f => { arquivo = f; $("#fNomeArq").textContent = f ? `Selecionado: ${f.name} (${fmt(f.size / 1048576, 1)} MB)` : ""; };
$("#fArquivo").addEventListener("change", e => escolher(e.target.files[0]));
const drop = $("#drop");
["dragenter", "dragover"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("on"); }));
["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("on"); }));
drop.addEventListener("drop", e => escolher(e.dataTransfer.files[0]));
$("#formNovo").addEventListener("submit", async e => {
  if (e.submitter && e.submitter.value === "cancel") return;
  e.preventDefault();
  if (!arquivo) { $("#fErro").textContent = "Escolha o arquivo do CAR."; return; }
  const fd = new FormData(); fd.append("arquivo", arquivo);
  [["car", "#fCar"], ["origem", "#fOrigem"], ["nome", "#fNome"], ["municipio", "#fMun"], ["proprietario", "#fProp"], ["analista", "#fAnalista"]].forEach(([k, s]) => fd.append(k, $(s).value.trim()));
  if ($("#fOrigem").value === "Carteira Bioma") fd.append("situacao", "Em análise");
  const b = $("#fEnviar"); b.innerHTML = '<span class="spin"></span> Importando e triando…'; b.disabled = true; $("#fErro").textContent = "";
  try { const r = await api("/api/imovel", {method: "POST", body: fd}); dlg.close(); await carregarImoveis(); toast(`${r.car} importado (${fmt(r.area_ha)} ha).`); irPara(r.car); }
  catch (err) { $("#fErro").textContent = err.message; }
  finally { b.textContent = "Importar e triar"; b.disabled = false; }
});

/* ---------------- equipe ---------------- */
async function carregarEquipe() {
  try {
    const us = await api("/api/usuarios");
    $("#tabUsuarios").innerHTML = `<thead><tr><th>Nome</th><th>E-mail</th><th>Perfil</th><th>Desde</th></tr></thead><tbody>${us.map(u => `<tr><td><b style="font-weight:600">${esc(u.nome)}</b></td><td>${esc(u.email)}</td><td>${u.perfil === "admin" ? '<span class="pill p-green">Administrador</span>' : '<span class="pill p-blue">Analista</span>'}</td><td>${new Date(u.criado_em).toLocaleDateString("pt-BR")}</td></tr>`).join("")}</tbody>`;
  } catch (e) { toast(e.message); }
}
$("#formUsuario").addEventListener("submit", async e => {
  e.preventDefault(); $("#uErro").textContent = "";
  try { await api("/api/usuarios", {method: "POST", body: {nome: $("#uNome").value.trim(), email: $("#uEmail").value.trim(), senha: $("#uSenha").value, perfil: $("#uPerfil").value}});
    e.target.reset(); toast("Pessoa salva. Passe a senha inicial para ela por um canal seguro."); carregarEquipe(); }
  catch (err) { $("#uErro").textContent = err.message; }
});

/* ---------------- navegação ---------------- */
function setMob(m) { $("#geo").dataset.m = m; $$("#mobtabs button").forEach(b => b.classList.toggle("on", b.dataset.m === m)); if (m === "map" && map) setTimeout(() => map.invalidateSize(), 0); }
$("#mobtabs").addEventListener("click", e => { const b = e.target.closest("button"); if (b) { setMob(b.dataset.m); window.scrollTo(0, 0); } });
function route() {
  const h = location.hash.slice(1), v = ["carteira", "equipe"].includes(h) && (h !== "equipe" || USER.perfil === "admin") ? h : "geoportal";
  ["geoportal", "carteira", "equipe"].forEach(x => { $("#v-" + x).hidden = x !== v; });
  $("#mobtabs").hidden = v !== "geoportal";
  $$(".nav a[data-view]").forEach(a => a.classList.toggle("on", a.dataset.view === v));
  if (v === "geoportal" && map) setTimeout(() => map.invalidateSize(), 0);
  if (v === "equipe") carregarEquipe();
}
window.addEventListener("hashchange", route);
$("#btnSair").onclick = async () => { try { await api("/api/logout", {method: "POST"}); } catch (e) {} location.href = "/login.html"; };

/* ---------------- início ---------------- */
async function iniciar() {
  try { USER = await api("/api/eu"); CFG = await api("/api/config"); } catch (e) { return; }
  $("#userNome").textContent = USER.nome; $("#userPerfil").textContent = USER.perfil === "admin" ? "Administrador" : "Analista";
  $("#avatar").textContent = (USER.nome || "?").trim().charAt(0).toUpperCase();
  $("#navEquipe").hidden = USER.perfil !== "admin";
  let salvo = {}; try { salvo = JSON.parse(ler("gp_vis") || "{}"); } catch (e) {}
  CFG.camadas.forEach(c => { vis[c.slug] = c.carregada && (c.slug in salvo ? salvo[c.slug] : c.visivel); });
  initMap(); renderTree(); renderPanel(); route();
  await carregarImoveis();
  const ult = ler("gp_ultimo");
  if (ult && IMOVEIS.some(i => i.car === ult)) abrir(ult);
  window.addEventListener("resize", () => map.invalidateSize());
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
}
iniciar();
})();
