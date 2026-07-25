/* ============================================================
   GrokFarmBox · 前端逻辑
   ============================================================ */
"use strict";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

async function _apiCall(method, body) {
  const opt = body !== undefined
    ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
    : { method: "POST" };
  const r = await fetch("/api/" + method, opt);
  return r.json();
}
// Proxy 让 api().method(arg) 透明转成 POST /api/method —— 与原 pywebview 调用兼容
const api = () => new Proxy({}, { get: (_, m) => (arg) => _apiCall(m, arg) });
const ready = () => true;

/* ---------------- toast ---------------- */
function toast(msg, kind = "") {
  const el = document.createElement("div");
  el.className = "toast " + kind;
  el.textContent = msg;
  $("#toasts").appendChild(el);
  setTimeout(() => { el.style.opacity = "0"; el.style.transform = "translateX(20px)"; }, 2600);
  setTimeout(() => el.remove(), 3000);
}

/* ---------------- 按钮异步封装 ---------------- */
async function run(btn, label, apiFn) {
  const orig = btn.innerHTML;
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> ${label}`;
  try {
    const r = await apiFn();
    return r;
  } catch (e) {
    toast("出错：" + (e?.message || e), "bad");
    return null;
  } finally {
    btn.disabled = false;
    btn.innerHTML = orig;
  }
}

/* ---------------- 导航 ---------------- */
function goto(page) {
  $$(".page").forEach(p => p.classList.remove("active"));
  $("#page-" + page).classList.add("active");
  $$(".nav-btn").forEach(b => b.classList.toggle("active", b.dataset.page === page));
  window.scrollTo(0, 0);
  if (page === "dashboard") refreshConnBar();
}

/* ---------------- 配置读写 ---------------- */
const CFG_KEYS = [
  "sub2api_base", "sub2api_email", "sub2api_password", "sub2api_safe_suffix",
  "sub2api_group_id", "sub2api_proxy_id",
  "cf_api_base", "cf_admin_token", "cf_domain", "cf_auth_mode",
  "external_register_cmd", "external_register_cwd", "register_count", "proxy",
  "register_enabled", "register_silent", "cpa_export_enabled",
  "test_concurrency", "max_tokens_probe", "auto_kill_bad",
];

async function loadCfgToForm() {
  if (!ready()) return;
  const cfg = await api().get_config();
  for (const k of CFG_KEYS) {
    const el = $("#cfg-" + k);
    if (!el) continue;
    const v = cfg[k];
    if (el.type === "checkbox") el.checked = !!v;
    else el.value = v === null || v === undefined ? "" : String(v);
  }
  $("#cfg-msg").textContent = "已加载本机配置";
}

async function saveCfgFromForm() {
  const cfg = {};
  for (const k of CFG_KEYS) {
    const el = $("#cfg-" + k);
    if (!el) continue;
    if (el.type === "checkbox") cfg[k] = el.checked;
    else cfg[k] = el.value.trim();
  }
  const btn = $("#btn-save-cfg");
  const r = await run(btn, "保存中…", async () => api().save_config(cfg));
  if (r && r.ok) {
    $("#cfg-msg").textContent = "已保存 ✓";
    toast("设置已保存", "ok");
    refreshConnBar();
  } else if (r) {
    $("#cfg-msg").textContent = r.error || "保存失败";
    toast(r.error || "保存失败", "bad");
  }
}

/* ---------------- 连接状态条 ---------------- */
async function refreshConnBar() {
  if (!ready()) return;
  const cfg = await api().get_config();
  $("#chip-server").innerHTML = `<span class="dot"></span> 服务器：<b>${cfg.sub2api_base || "未设置"}</b>`;
  $("#chip-group").innerHTML = `<span class="dot"></span> 分组/代理：<b>${cfg.sub2api_group_id ?? "?"} / ${cfg.sub2api_proxy_id ?? "?"}</b>`;
  $("#chip-suffix").innerHTML = `<span class="dot"></span> 安全后缀：<b>${cfg.sub2api_safe_suffix || "（空=管全部）"}</b>`;
  const cpa = await api().cpa_dir().catch(() => "?");
  $("#chip-cpa").innerHTML = `<span class="dot"></span> 凭证目录：<b>${cpa}</b>`;
}

/* ---------------- 日志 ---------------- */
async function pollLogs() {
  if (!ready()) return;
  try {
    const lines = await api().take_logs();
    if (Array.isArray(lines) && lines.length) {
      const box = $("#log-box");
      for (const ln of lines) {
        const div = document.createElement("div");
        div.className = "ln" + (ln.kind ? " " + ln.kind : "");
        const t = new Date().toLocaleTimeString("zh-CN", { hour12: false });
        div.innerHTML = `<span class="t">${t}</span>${escapeHtml(ln.msg)}`;
        box.appendChild(div);
      }
      box.scrollTop = box.scrollHeight;
      // 限制条数
      while (box.children.length > 600) box.removeChild(box.firstChild);
    }
  } catch (_) {}
}

/* ---------------- 仪表盘操作 ---------------- */
function setKpi(id, val, cls) {
  const el = $("#" + id);
  el.textContent = val;
  el.className = "val" + (cls ? " " + cls : "");
}

let _accounts = [], _page = 1, _pageSize = 20, _acctCollapsed = false;
const _maxPage = () => Math.max(1, Math.ceil(_accounts.length / _pageSize));

function renderAccountsPage() {
  const wrap = $("#acct-wrap"), pager = $("#acct-pager"), body = $("#acct-body");
  if (_acctCollapsed) { if (wrap) wrap.classList.add("hidden"); if (pager) pager.classList.add("hidden"); return; }
  if (wrap) wrap.classList.remove("hidden");
  if (!_accounts.length) {
    body.innerHTML = `<tr><td colspan="3" class="muted" style="padding:18px;">（暂无匹配安全后缀的号）</td></tr>`;
    if (pager) pager.classList.add("hidden");
    return;
  }
  if (pager) pager.classList.remove("hidden");
  const start = (_page - 1) * _pageSize;
  body.innerHTML = _accounts.slice(start, start + _pageSize).map(a => {
    const st = a.status || "-";
    const cls = st === "active" ? "active" : (st === "error" ? "error" : "inactive");
    return `<tr><td>${a.id}</td><td><span class="st-tag ${cls}">${st}</span></td><td>${escapeHtml(a.name || "")}</td></tr>`;
  }).join("");
  const info = $("#page-info");
  if (info) info.textContent = `第 ${_page} / ${_maxPage()} 页 · 共 ${_accounts.length} 个`;
  const prev = $("#btn-prev"), next = $("#btn-next");
  if (prev) prev.disabled = _page <= 1;
  if (next) next.disabled = _page >= _maxPage();
}

function applyOverview(ov) {
  setKpi("kpi-active", ov.safe_active ?? 0, "ok");
  setKpi("kpi-total", ov.safe_total ?? 0, "accent");
  setKpi("kpi-other", ov.other_total ?? 0);
  _accounts = ov.accounts || [];
  if (_page > _maxPage()) _page = 1;
  renderAccountsPage();
}

async function doTestConn() {
  const r = await run($("#btn-test-conn"), "连接中…", () => api().test_connection());
  if (!r) return;
  if (r.ok) {
    $("#conn-msg").innerHTML = `<span style="color:var(--ok);">✅ 连接成功</span> · 匹配 ${r.overview.safe_total} / 其它 ${r.overview.other_total}`;
    $("#chip-server").classList.add("ok");
    applyOverview(r.overview);
    toast("连接成功", "ok");
  } else {
    $("#conn-msg").innerHTML = `<span style="color:var(--bad);">❌ 连接失败</span> · ${escapeHtml(r.error || "")}`;
    $("#chip-server").classList.add("bad");
    toast("连接失败：" + (r.error || ""), "bad");
  }
}

async function doOverview() {
  const r = await run($("#btn-overview"), "拉取中…", () => api().overview());
  if (r && r.ok) { applyOverview(r.overview); toast("概况已刷新", "ok"); }
}

// 静默自动刷新：只在仪表盘页、无按钮 loading 时，后台更新 KPI/账号列表（不打扰、不弹 toast）
let _busy = false;
const _origRun = run;
run = async function (btn, label, apiFn) { _busy = true; try { return await _origRun(btn, label, apiFn); } finally { _busy = false; } };
async function silentRefresh() {
  if (!document.querySelector("#page-dashboard.active")) return;
  if (_busy || !ready()) return;
  try {
    const r = await api().overview();
    if (r && r.ok) applyOverview(r.overview);
    const s = await api().farm_state();
    setFarmButtons(!!s.running);
    setKpi("kpi-imported", s.imported_ok ?? 0, "accent");
    const f = $("#kpi-farm");
    if (f) { f.textContent = s.running ? "运行中" : "停止"; f.className = "val" + (s.running ? " accent" : ""); }
  } catch (_) {}
}

async function doImport() {
  const r = await run($("#btn-import"), "导入中…", () => api().import_cpa());
  if (r && r.ok) {
    const s = r.stats;
    toast(`导入完成：新增 ${s.imported} / 删 ${s.deleted} / 失败 ${s.failed}`, s.failed ? "" : "ok");
    const ov = await api().overview().catch(() => null);
    if (ov && ov.ok) applyOverview(ov.overview);
  }
}

async function doClean() {
  const r = await run($("#btn-clean"), "测活清理中…", () => api().clean());
  if (r && r.ok) {
    const s = r.stats;
    toast(`清理完成：保留 ${s.kept} / 删除 ${s.deleted}`, "ok");
    const ov = await api().overview().catch(() => null);
    if (ov && ov.ok) applyOverview(ov.overview);
  }
}

async function doQuota() {
  const r = await run($("#btn-quota"), "抽样中…", () => api().quota());
  if (r && r.ok) {
    const q = r.quota;
    $("#quota-box").innerHTML =
      `匹配可用号：<b>${q.active_total ?? 0}</b> · 抽样：<b>${q.sampled ?? 0}</b><br>` +
      `平均剩余请求次数：<b>${fmt(q.avg_remaining_requests)}</b><br>` +
      `平均剩余 token：<b>${fmt(q.avg_remaining_tokens)}</b><br>` +
      `<span class="muted">单号常见上限：21 次请求 / 1,000,000 token / 窗口</span>`;
    toast("额度已更新", "ok");
  }
}

async function doSmoke() {
  const r = await run($("#btn-smoke"), "冒烟中…", () => api().smoke());
  if (r && r.ok) {
    toast(r.result.ok ? "冒烟成功 ✅" : "冒烟返回：" + (r.result.status || "fail"), r.result.ok ? "ok" : "bad");
  }
}

function setFarmButtons(running) {
  const start = $("#btn-farm-start"), stop = $("#btn-farm-stop");
  if (start) start.disabled = !!running;
  if (stop) stop.disabled = !running;
}
async function doFarmStart() {
  const r = await run($("#btn-farm-start"), "启动中…", () => api().start_farm());
  if (r && r.ok) {
    toast("农场循环已启动", "ok"); setKpi("kpi-farm", "运行中", "accent"); setFarmButtons(true);
    try { const s = await api().farm_state(); setKpi("kpi-imported", s.imported_ok ?? 0, "accent"); } catch (_) {}
  }
  else { toast("启动失败", "bad"); }
}
async function doFarmStop() {
  await run($("#btn-farm-stop"), "停止中…", () => api().stop_farm());
  setKpi("kpi-farm", "停止");
  setFarmButtons(false);
  toast("已请求停止农场");
}

function fmt(v) { return v === null || v === undefined ? "—" : (typeof v === "number" ? Math.round(v).toLocaleString() : v); }

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* ---------------- Markdown 教程 ---------------- */
async function loadGuide() {
  if (!ready()) return;
  try {
    const md = await api().get_guide_md();
    $("#guide-md").innerHTML = mdToHtml(md || "(无内容)");
  } catch (e) {
    $("#guide-md").innerHTML = `<p class="muted">读取失败：${escapeHtml(String(e))}</p>`;
  }
}

/* 轻量 markdown 渲染器（零依赖，离线可用） */
function mdToHtml(src) {
  const codeBlocks = [];
  // 1. 抽出代码块
  src = src.replace(/```([^\n`]*)\n([\s\S]*?)```/g, (_, lang, body) => {
    codeBlocks.push(`<pre><code class="${lang || ""}">${escapeHtml(body.replace(/\n$/, ""))}</code></pre>`);
    return ` CB${codeBlocks.length - 1} `;
  });

  const lines = src.split(/\r?\n/);
  const out = [];
  let i = 0;
  const inline = (t) => t
    .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img alt="$1" src="$2" />')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");

  while (i < lines.length) {
    const line = lines[i];

    // 代码块占位
    const cb = line.match(/^ CB(\d+) $/);
    if (cb) { out.push(codeBlocks[+cb[1]]); i++; continue; }

    // 空行
    if (!line.trim()) { i++; continue; }

    // 标题
    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) { out.push(`<h${h[1].length}>${inline(escapeHtml(h[2]))}</h${h[1].length}>`); i++; continue; }

    // 分隔线
    if (/^(\s*[-*_]){3,}\s*$/.test(line)) { out.push("<hr/>"); i++; continue; }

    // 引用
    if (/^>\s?/.test(line)) {
      const buf = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) { buf.push(lines[i].replace(/^>\s?/, "")); i++; }
      out.push(`<blockquote>${inline(escapeHtml(buf.join("<br>")))}</blockquote>`);
      continue;
    }

    // 表格
    if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
      const header = splitRow(line);
      i += 2;
      const rows = [];
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) { rows.push(splitRow(lines[i])); i++; }
      let tbl = "<table><thead><tr>" + header.map(c => `<th>${inline(escapeHtml(c))}</th>`).join("") + "</tr></thead><tbody>";
      for (const r of rows) tbl += "<tr>" + r.map(c => `<td>${inline(escapeHtml(c))}</td>`).join("") + "</tr>";
      tbl += "</tbody></table>";
      out.push(tbl);
      continue;
    }

    // 无序列表
    if (/^\s*[-*+]\s+/.test(line)) {
      const buf = [];
      while (i < lines.length && /^\s*[-*+]\s+/.test(lines[i])) { buf.push(`<li>${inline(escapeHtml(lines[i].replace(/^\s*[-*+]\s+/, "")))}</li>`); i++; }
      out.push("<ul>" + buf.join("") + "</ul>");
      continue;
    }

    // 有序列表
    if (/^\s*\d+\.\s+/.test(line)) {
      const buf = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) { buf.push(`<li>${inline(escapeHtml(lines[i].replace(/^\s*\d+\.\s+/, "")))}</li>`); i++; }
      out.push("<ol>" + buf.join("") + "</ol>");
      continue;
    }

    // 段落（连续非空行合并）
    const buf = [line];
    i++;
    while (i < lines.length && lines[i].trim() && !/^(#{1,6}\s|>\s?|\s*[-*+]\s|\s*\d+\.\s|\s*\||```)/.test(lines[i]) && !/^ CB/.test(lines[i])) {
      buf.push(lines[i]); i++;
    }
    out.push(`<p>${inline(escapeHtml(buf.join(" ")))}</p>`);
  }
  return out.join("\n");
}
function splitRow(line) {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map(c => c.trim());
}

/* ---------------- 初始化 ---------------- */
function bind() {
  $$(".nav-btn").forEach(b => b.addEventListener("click", () => goto(b.dataset.page)));
  $("#btn-goto-settings").addEventListener("click", () => goto("settings"));
  $("#btn-test-conn").addEventListener("click", doTestConn);
  $("#btn-open-cpa").addEventListener("click", () => api()?.open_cpa_dir());
  $("#btn-overview").addEventListener("click", doOverview);
  $("#btn-import").addEventListener("click", doImport);
  $("#btn-clean").addEventListener("click", doClean);
  $("#btn-quota").addEventListener("click", doQuota);
  $("#btn-smoke").addEventListener("click", doSmoke);
  $("#btn-farm-start").addEventListener("click", doFarmStart);
  $("#btn-farm-stop").addEventListener("click", doFarmStop);
  $("#btn-prev")?.addEventListener("click", () => { if (_page > 1) { _page--; renderAccountsPage(); } });
  $("#btn-next")?.addEventListener("click", () => { if (_page < _maxPage()) { _page++; renderAccountsPage(); } });
  $("#btn-acct-collapse")?.addEventListener("click", (e) => {
    _acctCollapsed = !_acctCollapsed;
    e.target.textContent = _acctCollapsed ? "展开列表" : "收起";
    renderAccountsPage();
  });
  $("#btn-save-cfg").addEventListener("click", saveCfgFromForm);
  $("#btn-reload-cfg").addEventListener("click", loadCfgToForm);
  setInterval(pollLogs, 1500);
}

async function boot() {
  bind();
  await refreshConnBar();
  await loadCfgToForm();
  await loadGuide();
  try { const s = await api().farm_state(); setFarmButtons(!!s.running); setKpi("kpi-imported", s.imported_ok ?? 0, "accent"); if (s.running) setKpi("kpi-farm", "运行中", "accent"); } catch (_) {}
  setInterval(silentRefresh, 60000);  // 每 60 秒静默刷新仪表盘数字
}

document.addEventListener("DOMContentLoaded", boot);
