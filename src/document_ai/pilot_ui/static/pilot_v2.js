/* Document AI Pilot v2 — user-facing wizard (no engine changes). */

const state = {
  step: 1,
  sessionId: null,
  scenarios: [],
  last: null,
};

function $(id) {
  return document.getElementById(id);
}

function showStep(n) {
  state.step = n;
  document.querySelectorAll("#wizard-tabs .tab").forEach((b) => {
    b.classList.toggle("active", Number(b.dataset.step) === n);
  });
  document.querySelectorAll("main .panel").forEach((p) => {
    p.classList.toggle("active", p.id === `step-${n}`);
  });
  const bar = $("progress-bar");
  if (bar) bar.style.width = `${(n / 6) * 100}%`;
}

document.querySelectorAll("#wizard-tabs .tab").forEach((btn) => {
  btn.addEventListener("click", () => showStep(Number(btn.dataset.step)));
});

function renderSummary(el, rows) {
  if (!el) return;
  el.hidden = !rows.length;
  el.innerHTML = rows
    .map(
      ([k, v]) =>
        `<div class="summary-card"><div class="k">${k}</div><div class="v">${v == null || v === "" ? "-" : v}</div></div>`
    )
    .join("");
}

async function loadScenarios() {
  const res = await fetch("/api/pilot-v2/scenarios");
  const data = await res.json();
  state.scenarios = data.scenarios || [];
  const sel = $("scenario_id");
  state.scenarios.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s.scenario_id;
    opt.textContent = `[${s.domain}] ${s.title}`;
    sel.appendChild(opt);
  });
}

function updateScenarioDesc() {
  const id = $("scenario_id").value;
  const hit = state.scenarios.find((s) => s.scenario_id === id);
  if (hit) {
    $("scenario-desc").textContent = `변경 요청 예: ${hit.change_request}`;
    $("document_set").value = hit.document_set;
    $("change_request").value = hit.change_request;
  } else {
    $("scenario-desc").textContent = "시나리오 없이 직접 업로드할 수 있습니다.";
  }
}

$("scenario_id").addEventListener("change", updateScenarioDesc);

$("btn-create-session").addEventListener("click", async () => {
  const fd = new FormData();
  fd.append("document_set", $("document_set").value);
  fd.append("change_request", $("change_request").value || "(시나리오 기본값)");
  fd.append("participant_id", $("participant_id").value || "");
  fd.append("scenario_id", $("scenario_id").value || "");
  fd.append("routing_mode", ($("routing_mode") && $("routing_mode").value) || "assisted");
  const files = $("files").files;
  for (let i = 0; i < files.length; i++) fd.append("files", files[i]);

  $("create-status").textContent = "업로드 중…";
  $("create-status").className = "status";
  const res = await fetch("/api/pilot-v2/sessions", { method: "POST", body: fd });
  const data = await res.json();
  if (!res.ok) {
    $("create-status").textContent = data.detail || "세션 생성 실패";
    $("create-status").className = "status err";
    return;
  }
  state.sessionId = data.session_id;
  state.last = data;
  const docs = data.documents || [];
  $("create-status").textContent = `세션 준비 완료 · ${data.session_id}`;
  $("create-status").className = "status ok";
  renderSummary(
    $("upload-summary"),
    [
      ["세션 ID", data.session_id],
      ["상태", data.status],
      ["문서 수", String(docs.length)],
      ["복사본", docs.length ? "세션 workspace에 저장됨" : "시나리오 픽스처 사용"],
      [
        "파일",
        docs.map((d) => d.filename || d.document_id || d.name || "?").join(", ") || "-",
      ],
    ]
  );
  $("session-id-2").textContent = data.session_id;
  $("change_request").value = data.change_request || $("change_request").value;
  $("identity-out").textContent = JSON.stringify(data.identity || {}, null, 2);
  showStep(2);
});

function paintIdentity(data) {
  const id = data.identity || data;
  const pack = id.recommended_domain_pack || id.domain_pack || id.document_set || "-";
  const conf = id.confidence != null ? Number(id.confidence).toFixed(2) : "-";
  const needs = id.needs_user_confirmation ? "예 — 아래 확정 버튼을 눌러 주세요" : "아니오";
  renderSummary($("identity-summary"), [
    ["추천 Domain Pack", pack],
    ["신뢰도", conf],
    ["사용자 확인 필요", needs],
    ["문서 역할", (id.roles && JSON.stringify(id.roles)) || id.role || "-"],
    ["충돌", id.conflict ? "있음" : "없음"],
  ]);
  $("identity-out").textContent = JSON.stringify(id, null, 2);
  $("btn-confirm-identity").disabled = !id.needs_user_confirmation;
}

$("btn-resolve-identity").addEventListener("click", async () => {
  if (!state.sessionId) return;
  const fd = new FormData();
  fd.append("routing_mode", $("routing_mode").value);
  fd.append("user_confirmed", "false");
  const res = await fetch(`/api/pilot-v2/sessions/${encodeURIComponent(state.sessionId)}/resolve-identity`, {
    method: "POST",
    body: fd,
  });
  const data = await res.json();
  state.last = data;
  paintIdentity(data);
});

$("btn-confirm-identity").addEventListener("click", async () => {
  if (!state.sessionId) return;
  const fd = new FormData();
  fd.append("routing_mode", $("routing_mode").value);
  fd.append("user_confirmed", "true");
  const res = await fetch(`/api/pilot-v2/sessions/${encodeURIComponent(state.sessionId)}/resolve-identity`, {
    method: "POST",
    body: fd,
  });
  const data = await res.json();
  state.last = data;
  paintIdentity(data);
});

$("btn-to-step3").addEventListener("click", () => showStep(3));
$("btn-to-step4").addEventListener("click", () => showStep(4));

$("btn-analyze").addEventListener("click", async () => {
  if (!state.sessionId) return;
  $("analyze-out").textContent = "분석 중…";
  const res = await fetch(`/api/pilot-v2/sessions/${encodeURIComponent(state.sessionId)}/analyze`, {
    method: "POST",
  });
  const data = await res.json();
  state.last = data;
  const items = data.review_items || [];
  const reviewN = items.filter((i) => i.kind === "REVIEW_REQUIRED").length;
  const patchN = items.filter((i) => i.kind === "PATCH_CANDIDATE").length;
  const analysis = (data.metadata || {}).analysis || {};
  renderSummary($("analyze-summary"), [
    ["상태", data.status],
    ["검토 항목 수", String(items.length)],
    ["패치 후보", String(patchN)],
    ["REVIEW 필요", String(reviewN)],
    ["영향 문서", String(analysis.impacted_documents ?? analysis.n_documents ?? "-")],
    ["처리 시간", analysis.elapsed_ms != null ? `${analysis.elapsed_ms} ms` : "-"],
  ]);
  $("analyze-out").textContent = JSON.stringify(
    { status: data.status, n_review_items: items.length, analysis },
    null,
    2
  );
  renderReviewItems(items);
});

$("btn-to-step5").addEventListener("click", () => showStep(5));

function renderReviewItems(items) {
  const box = $("review-items");
  box.innerHTML = "";
  if (!items.length) {
    box.innerHTML = '<p class="hint callout">검토할 변경 후보가 없습니다. (영향 없음으로 볼 수 있습니다)</p>';
    return;
  }
  items.forEach((item) => {
    const card = document.createElement("div");
    card.className = "card";
    const evidence = (item.evidence || []).slice(0, 3).join(" · ");
    card.innerHTML = `
      <strong>${item.display_name || item.item_id}</strong>
      <span class="hint"> · ${item.document_id || ""} · ${item.kind || ""}</span>
      <p class="hint">${item.reason_text_ko || "사유 없음"}</p>
      ${evidence ? `<p class="hint">근거: ${evidence}</p>` : ""}
      <div class="seg" data-item="${item.item_id}">
        <button type="button" class="seg-btn approve" data-decision="APPROVE">승인</button>
        <button type="button" class="seg-btn reject" data-decision="REJECT">거절</button>
        <button type="button" class="seg-btn hold active" data-decision="HOLD">보류</button>
      </div>
    `;
    card.querySelectorAll(".seg-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        card.querySelectorAll(".seg-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
      });
    });
    box.appendChild(card);
  });
}

$("btn-save-decisions").addEventListener("click", async () => {
  if (!state.sessionId) return;
  const decisions = [];
  document.querySelectorAll("#review-items .seg").forEach((seg) => {
    const active = seg.querySelector(".seg-btn.active");
    decisions.push({ item_id: seg.dataset.item, decision: active ? active.dataset.decision : "HOLD" });
  });
  const res = await fetch(`/api/pilot-v2/sessions/${encodeURIComponent(state.sessionId)}/decisions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decisions, decided_by: "pilot-participant" }),
  });
  const data = await res.json();
  state.last = data;
  const counts = { APPROVE: 0, REJECT: 0, HOLD: 0 };
  decisions.forEach((d) => {
    if (counts[d.decision] != null) counts[d.decision] += 1;
  });
  $("decisions-out").textContent = `저장됨 · 승인 ${counts.APPROVE} · 거절 ${counts.REJECT} · 보류 ${counts.HOLD}`;
});

$("btn-run-writer").addEventListener("click", async () => {
  if (!state.sessionId) return;
  const fd = new FormData();
  fd.append("enable_write", $("enable_write").checked ? "true" : "false");
  fd.append("decided_by", "pilot-participant");
  const res = await fetch(`/api/pilot-v2/sessions/${encodeURIComponent(state.sessionId)}/writer`, {
    method: "POST",
    body: fd,
  });
  const data = await res.json();
  state.last = data;
  const wr = data.writer_result || data;
  $("writer-out").textContent = JSON.stringify(wr, null, 2);
});

$("btn-to-step6").addEventListener("click", () => {
  showStep(6);
  refreshResult();
});

function renderDownloads(sessionId, session) {
  const box = $("download-links");
  if (!box || !sessionId) return;
  const links = [
    ["세션 JSON", `sessions/${sessionId}`],
    ["분석 trace", `output/analysis_trace.json`],
    ["승인 trace", `review/approval_trace.json`],
    ["검증 trace", `output/validation_trace.json`],
    ["Writer trace", `output/writer_trace.json`],
  ];
  const copies = ((session || {}).writer_result || {}).copies || [];
  copies.forEach((c, i) => {
    const rel = c.relative_path || c.path || `output/copies/${c.document_id || i}.docx`;
    links.push([`복사본 ${c.document_id || i + 1}`, rel.replace(/^.*?(output\/)/, "$1")]);
  });
  box.innerHTML =
    "<h3>다운로드</h3>" +
    links
      .map(([label, rel]) => {
        if (rel.startsWith("sessions/")) {
          return `<a class="dl" href="/api/pilot-v2/sessions/${encodeURIComponent(sessionId)}">${label}</a>`;
        }
        const href = `/api/pilot-v2/sessions/${encodeURIComponent(sessionId)}/artifacts/${rel}`;
        return `<a class="dl" href="${href}" download>${label}</a>`;
      })
      .join(" ");
}

async function refreshResult() {
  if (!state.sessionId) return;
  const res = await fetch(`/api/pilot-v2/sessions/${encodeURIComponent(state.sessionId)}`);
  const data = await res.json();
  const session = data.session || data;
  const wr = session.writer_result || {};
  renderSummary($("result-summary"), [
    ["세션 상태", session.status],
    ["Writer", wr.status || "-"],
    ["원본 변경", wr.original_changed === true ? "예 (오류)" : "아니오"],
    ["차단 사유", (wr.blocked_reasons || []).join(", ") || "-"],
    ["복사본 수", String((wr.copies || []).length)],
  ]);
  $("result-out").textContent = JSON.stringify(
    { status: session.status, writer_result: wr, metrics: session.metrics },
    null,
    2
  );
  renderDownloads(state.sessionId, session);
}

$("btn-result").addEventListener("click", refreshResult);

$("btn-save-human-review").addEventListener("click", async () => {
  if (!state.sessionId) return;
  const scores = {
    understanding: Number($("score_understanding").value),
    document_impact: Number($("score_document_impact").value),
    node_accuracy: Number($("score_node_accuracy").value),
    proposal_accuracy: Number($("score_proposal_accuracy").value),
    review_reason: Number($("score_review_reason").value),
    diff_readability: Number($("score_diff_readability").value),
    no_unnecessary_change: Number($("score_no_unnecessary_change").value),
    format_preservation: Number($("score_format_preservation").value),
    trust: Number($("score_trust").value),
    usability: Number($("score_usability").value),
  };
  const res = await fetch(`/api/pilot-v2/sessions/${encodeURIComponent(state.sessionId)}/human-review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      scores,
      comments: $("hr_comments").value,
      verdict: $("hr_verdict").value,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    $("hr-status").textContent = data.detail || "저장 실패";
    $("hr-status").className = "status err";
    return;
  }
  $("hr-status").textContent = `평가 저장됨 · 상태 ${data.status}`;
  $("hr-status").className = "status ok";
  $("result-out").textContent = JSON.stringify(data.metrics || data, null, 2);
});

loadScenarios();
updateScenarioDesc();
showStep(1);
