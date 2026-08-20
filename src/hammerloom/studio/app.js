const escapeHtml = (text) => String(text ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const formatNumber = number => Number(number || 0).toLocaleString("zh-CN");
const formatDuration = milliseconds => `${(Number(milliseconds || 0) / 1000).toFixed(1)} 秒`;
const formatTime = timestamp => timestamp ? new Date(timestamp).toLocaleString("zh-CN", { hour12: false }) : "未完成";

function empty() {
  return document.getElementById("empty").innerHTML;
}

function stat(label, number, detail) {
  return `<article class="stat"><p>${label}</p><strong>${number}</strong><small>${detail}</small></article>`;
}

function statusText(success) {
  return success === true ? "已验证成功" : success === false ? "执行失败" : "运行中";
}

function candidateStatusText(status) {
  return { pending: "待评估", promoted: "已提升", rejected: "未通过" }[status] || status;
}

function verdictText(verdict) {
  return { promoted: "已提升", rejected: "未通过" }[verdict] || verdict;
}

function renderOverview(data) {
  const summary = data.summary;
  document.getElementById("active-version").innerHTML = `<span>当前策略版本</span><b>${escapeHtml(summary.active_version)}</b>`;
  document.getElementById("stats").innerHTML = [
    stat("运行总数", formatNumber(summary.runs), "已收集的 Agent 任务"),
    stat("验证成功率", `${Math.round(summary.success_rate * 100)}%`, "已完成任务的验证结果"),
    stat("已启用 Skill", formatNumber(summary.skills), "已通过门控的经验"),
    stat("安全事件", formatNumber(summary.safety_events), "策略门控违规记录")
  ].join("");

  const runs = data.runs.slice().reverse();
  document.getElementById("run-count").textContent = `${runs.length} 次运行`;
  document.getElementById("runs").innerHTML = runs.length ? runs.map(run => `
    <button class="run-item" type="button" data-run-id="${escapeHtml(run.id)}">
      <span class="status-dot ${run.success === true ? "passed" : run.success === false ? "failed" : "running"}"></span>
      <span class="run-main"><b>${escapeHtml(run.task_title)}</b><small>${escapeHtml(run.id)} · ${formatTime(run.created_at)}</small><em>${escapeHtml(run.summary || "任务正在执行，尚无摘要。")}</em></span>
      <span class="run-meta"><strong>${statusText(run.success)}</strong><small>${formatNumber(run.tokens)} tokens · ${formatDuration(run.duration_ms)} · ${run.events.length} 个事件</small></span>
    </button>
  `).join("") : empty();
  document.querySelectorAll("[data-run-id]").forEach(button => button.addEventListener("click", () => showRun(button.dataset.runId)));
}

function jsonBlock(value) {
  return `<pre>${escapeHtml(typeof value === "string" ? value : JSON.stringify(value, null, 2))}</pre>`;
}

function renderEvents(events) {
  if (!events.length) return empty();
  return events.map((event, index) => `
    <article class="event event-${escapeHtml(event.kind)}">
      <div class="event-index">${index + 1}</div>
      <div class="event-content">
        <div class="event-heading"><span>${escapeHtml(event.kind)}</span><b>${escapeHtml(event.name)}</b><small>${formatDuration(event.duration_ms)}</small></div>
        ${event.input ? `<details><summary>输入</summary>${jsonBlock(event.input)}</details>` : ""}
        ${event.output ? `<details><summary>输出</summary>${jsonBlock(event.output)}</details>` : ""}
        ${Object.keys(event.attributes || {}).length ? `<details><summary>附加数据</summary>${jsonBlock(event.attributes)}</details>` : ""}
      </div>
    </article>
  `).join("");
}

function renderSkills(skills, candidates, decisions) {
  const skillHtml = skills.length ? skills.map(skill => `
    <article class="skill-card"><div class="card-heading"><div><span class="tag ${escapeHtml(skill.status)}">${escapeHtml(skill.status === "active" ? "已启用" : "候选" )}</span><h3>${escapeHtml(skill.title)}</h3></div><span>${Math.round(Number(skill.confidence || 0) * 100)}% 置信度</span></div>
    <p><b>触发条件：</b>${escapeHtml(skill.trigger)}</p><p><b>适用范围：</b>${escapeHtml(skill.scope)}</p><p><b>验证命令：</b><code>${escapeHtml(skill.verifier)}</code></p>
    <ol>${skill.procedure.map(step => `<li>${escapeHtml(step)}</li>`).join("")}</ol>
    <details class="skill-source"><summary>查看提炼后的 Skill 原文</summary>${jsonBlock(skill)}</details></article>
  `).join("") : `<p class="empty">本次运行尚未生成 Skill。只有验证成功的任务才会进入经验提炼。</p>`;
  const candidateHtml = candidates.length ? candidates.map(candidate => {
    const decision = decisions.find(item => item.candidate_id === candidate.id);
    return `<article class="candidate-card"><h3>候选 ${escapeHtml(candidate.id)}</h3><p>${escapeHtml(candidate.rationale)}</p><p><b>状态：</b>${escapeHtml(candidateStatusText(candidate.status))}${decision ? ` · <b>门控结论：</b>${escapeHtml(verdictText(decision.verdict))}` : ""}</p><details><summary>查看候选原始数据</summary>${jsonBlock(candidate)}</details></article>`;
  }).join("") : "";
  return `${skillHtml}${candidateHtml}`;
}

function renderRunDetail(run) {
  const verification = run.events.filter(event => event.kind === "verification").at(-1);
  document.getElementById("run-detail").innerHTML = `
    <section class="detail-heading"><p class="eyebrow">运行详情</p><h1>${escapeHtml(run.task_title)}</h1><p class="muted">运行 ID：<code>${escapeHtml(run.id)}</code> · 开始时间：${formatTime(run.created_at)}</p></section>
    <section class="stats detail-stats">
      ${stat("运行状态", statusText(run.success), run.summary || "暂无任务摘要")}
      ${stat("模型调用", formatNumber(run.model_usage.calls), `模型耗时 ${formatDuration(run.model_usage.duration_ms)}`)}
      ${stat("Token 用量", formatNumber(run.model_usage.tokens), "仅统计新运行中的实际接口返回值")}
      ${stat("总耗时", formatDuration(run.duration_ms), `${run.events.length} 个轨迹事件`)}
    </section>
    <section class="detail-grid">
      <article class="panel"><div class="panel-title"><div><p class="eyebrow">Agent 交互轨迹</p><h2>模型决策与工具执行</h2></div></div><div class="event-list">${renderEvents(run.events)}</div></article>
      <aside class="side-stack">
        <article class="panel"><div class="panel-title"><div><p class="eyebrow">验证结果</p><h2>最终测试</h2></div></div>${verification ? `<div class="verification ${verification.attributes.passed ? "passed" : "failed"}"><b>${verification.attributes.passed ? "验证通过" : "验证失败"}</b><code>${escapeHtml(verification.name)}</code><pre>${escapeHtml(verification.output || "无输出")}</pre></div>` : `<p class="empty">尚未记录验证事件。</p>`}</article>
        <article class="panel"><div class="panel-title"><div><p class="eyebrow">代码修改</p><h2>补丁与变更文件</h2></div></div>${run.changed_files.length ? run.changed_files.map(file => `<details class="patch" open><summary>${escapeHtml(file.path)}</summary><pre>${escapeHtml(file.patch)}</pre></details>`).join("") : `<p class="empty">本次运行未产生代码补丁。</p>`}</article>
      </aside>
    </section>
    <section class="panel"><div class="panel-title"><div><p class="eyebrow">经验提炼</p><h2>Skill、候选与门控结果</h2></div></div><div class="skill-list">${renderSkills(run.skills, run.candidates, run.decisions)}</div></section>
  `;
}

async function showRun(runId) {
  const response = await fetch(`/api/runs/${encodeURIComponent(runId)}`);
  if (!response.ok) throw new Error("无法加载运行详情");
  renderRunDetail(await response.json());
  document.getElementById("overview-view").hidden = true;
  document.getElementById("detail-view").hidden = false;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

async function initialize() {
  try {
    const response = await fetch("/api/dashboard");
    if (!response.ok) throw new Error("无法加载控制台数据");
    renderOverview(await response.json());
  } catch (error) {
    document.getElementById("runs").innerHTML = `<p class="error">无法加载 HammerLoom 本地数据。</p>`;
  }
}

document.getElementById("back-button").addEventListener("click", () => {
  document.getElementById("detail-view").hidden = true;
  document.getElementById("overview-view").hidden = false;
});
initialize();
