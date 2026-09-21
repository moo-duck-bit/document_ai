/* PR-27 Workflow wizard client */

const state = {
  step: 1,
  workflowId: null,
  catalog: [],
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
}

document.querySelectorAll("#wizard-tabs .tab").forEach((btn) => {
  btn.addEventListener("click", () => showStep(Number(btn.dataset.step)));
});

async function loadCatalog() {
  const res = await fetch("/api/workflow/catalog");
  const data = await res.json();
  state.catalog = data.document_sets || [];
  const sel = $("document_set");
  sel.innerHTML = "";
  state.catalog.forEach((c) => {
    const opt = document.createElement("option");
    opt.value = c.document_set_id;
    opt.textContent = c.display_name;
    sel.appendChild(opt);
  });
  updateDesc();
}

function updateDesc() {
  const id = $("document_set").value;
  const hit = state.catalog.find((c) => c.document_set_id === id);
  $("set-desc").textContent = hit ? hit.description : "";
}

$("document_set").addEventListener("change", updateDesc);
$("btn-next-1").addEventListener("click", () => showStep(2));

$("btn-create").addEventListener("click", async () => {
  const fd = new FormData();
  fd.append("document_set", $("document_set").value);
  fd.append("change_request", $("change_request").value);
  fd.append("name", $("wf-name").value || "workflow");
  fd.append("document_routing_mode", ($("routing_mode") && $("routing_mode").value) || "assisted");
  const files = $("files").files;
  for (let i = 0; i < files.length; i++) fd.append("files", files[i]);
  const res = await fetch("/api/workflow/create", { method: "POST", body: fd });
  const data = await res.json();
  if (!res.ok) {
    $("create-status").textContent = data.detail || "create failed";
    $("create-status").className = "status err";
    return;
  }
  state.workflowId = data.workflow_id;
  state.last = data;
  state.identityConfirmed = false;
  $("create-status").textContent = `created ${data.workflow_id} · ${data.state}`;
  $("create-status").className = "status ok";
  $("wf-id").textContent = data.workflow_id;
  renderIdentity(data);
  showStep(3);
});

function renderIdentity(data) {
  const panel = $("identity-panel");
  const docs = data.documents || [];
  if (!docs.length) {
    panel.textContent = "문서 없음";
    return;
  }
  const lines = docs.map((d) => {
    const reasons = (d.identity_reasons || []).slice(0, 4).join(", ");
    return [
      `file: ${d.filename}`,
      `  type/role: ${d.document_type || "-"} / ${d.document_role || d.role || "-"}`,
      `  pack: ${d.selected_pack_id || d.domain_pack_id || "-"} · status: ${d.identity_status || "-"}`,
      `  canonical: ${d.canonical_document_id || "-"} · score: ${d.identity_score ?? "-"}`,
      `  reasons: ${reasons || "-"}`,
    ].join("\n");
  });
  const needs = (data.metadata || {}).needs_identity_confirmation;
  panel.textContent = lines.join("\n\n") + (needs ? "\n\n[assisted] 분석 전 추천 확인이 필요합니다." : "");
  if ($("btn-accept-identity")) {
    $("btn-accept-identity").disabled = false;
    $("btn-hold-review").disabled = false;
  }
}

if ($("btn-accept-identity")) {
  $("btn-accept-identity").addEventListener("click", () => {
    state.identityConfirmed = true;
    $("create-status").textContent = "identity: 추천대로 사용 확인됨";
    $("create-status").className = "status ok";
  });
  $("btn-hold-review").addEventListener("click", () => {
    state.identityConfirmed = false;
    $("create-status").textContent = "identity: REVIEW 보류 — 분석 전 확인 필요";
    $("create-status").className = "status err";
  });
}

$("btn-analyze").addEventListener("click", async () => {
  if (!state.workflowId) return;
  const mode = ($("routing_mode") && $("routing_mode").value) || "assisted";
  if (mode === "assisted" && state.last && (state.last.metadata || {}).needs_identity_confirmation && !state.identityConfirmed) {
    $("analyze-out").textContent = "assisted 모드: 문서 identity 추천을 확인한 뒤 분석을 실행하세요.";
    return;
  }
  const res = await fetch(`/api/workflow/${encodeURIComponent(state.workflowId)}/analyze`, {
    method: "POST",
  });
  const data = await res.json();
  state.last = data;
  $("analyze-out").textContent = JSON.stringify(
    {
      state: data.state,
      impacted_documents: data.impacted_documents,
      patch_candidates: (data.patch_candidates || []).length,
      review_required: (data.review_required || []).length,
      validation: data.validation,
      metadata: data.metadata,
    },
    null,
    2
  );
  $("rev-impacted").textContent = JSON.stringify(data.impacted_documents || [], null, 2);
  $("rev-patch").textContent = JSON.stringify((data.patch_candidates || []).slice(0, 20), null, 2);
  $("rev-review").textContent = JSON.stringify((data.review_required || []).slice(0, 30), null, 2);
  showStep(4);
});

$("btn-to-approve").addEventListener("click", () => showStep(5));

$("btn-approve-all").addEventListener("click", async () => {
  if (!state.workflowId) return;
  const res = await fetch(`/api/workflow/${encodeURIComponent(state.workflowId)}/approve`, {
    method: "POST",
  });
  const data = await res.json();
  state.last = data;
  $("approve-out").textContent = JSON.stringify(
    {
      state: data.state,
      approvals_sample: (data.approvals || []).slice(0, 30),
    },
    null,
    2
  );
});

$("btn-writer").addEventListener("click", async () => {
  if (!state.workflowId) return;
  const res = await fetch(
    `/api/workflow/${encodeURIComponent(state.workflowId)}/writer?enable_write=false`,
    { method: "POST" }
  );
  const data = await res.json();
  state.last = data.workflow || data;
  $("approve-out").textContent = JSON.stringify(data.result || data, null, 2);
  renderResult(data);
  showStep(6);
});

$("btn-result").addEventListener("click", async () => {
  if (!state.workflowId) return;
  const res = await fetch(`/api/workflow/${encodeURIComponent(state.workflowId)}/result`);
  const data = await res.json();
  renderResult(data);
});

function renderResult(data) {
  const rows = data.result?.rows || data.workflow?.result_rows || [];
  const tbody = document.querySelector("#result-table tbody");
  tbody.innerHTML = "";
  rows.forEach((r) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${r.document_id || ""}</td>
      <td>${r.status || ""}</td>
      <td>${r.review || ""}</td>
      <td>${r.applied ?? ""}</td>
      <td>${r.rejected ?? ""}</td>
      <td>${r.blocked ?? ""}</td>
      <td>${r.validation || ""}</td>
      <td>${r.diff_available ? "Y" : "N"}</td>
      <td>${r.download ? "copy" : "-"}</td>`;
    tbody.appendChild(tr);
  });
  $("result-out").textContent = JSON.stringify(data.result?.summary || data, null, 2);
}

loadCatalog();
showStep(1);
