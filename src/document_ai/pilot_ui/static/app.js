/* Document AI Pilot UI client */

const state = {
  runId: null,
  reviewDocs: {},
};

function $(id) {
  return document.getElementById(id);
}

function setStatus(el, msg, ok) {
  el.textContent = msg || "";
  el.className = "status " + (ok === true ? "ok" : ok === false ? "err" : "");
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === name);
  });
  document.querySelectorAll(".panel").forEach((p) => {
    p.classList.toggle("active", p.id === `tab-${name}`);
  });
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

async function refreshRuns() {
  const res = await fetch("/api/pilot/runs");
  const data = await res.json();
  const box = $("run-list");
  box.innerHTML = "<h3>Recent runs</h3>";
  (data.runs || []).forEach((r) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "linkish";
    b.textContent = `${r.run_id} · ${r.status}`;
    b.onclick = () => selectRun(r.run_id);
    box.appendChild(b);
  });
}

function selectRun(runId) {
  state.runId = runId;
  $("review-run-id").value = runId;
  $("writer-run-id").value = runId;
  switchTab("review");
  loadReview(runId);
}

async function loadReview(runId) {
  const res = await fetch(`/api/pilot/runs/${encodeURIComponent(runId)}`);
  if (!res.ok) {
    $("review-header").textContent = await res.text();
    return;
  }
  const data = await res.json();
  state.reviewDocs = data.review || {};
  $("review-header").innerHTML =
    `<strong>${data.run_id}</strong> · <code>${data.status}</code>` +
    (data.summary?.input_hashes_unchanged === false
      ? " · <span style='color:#9b1c1c'>input hash changed?</span>"
      : " · input hashes unchanged");

  $("review-summary").textContent = JSON.stringify(data.summary || {}, null, 2);

  const ul = $("review-artifacts");
  ul.innerHTML = "";
  (data.artifacts || []).forEach((a) => {
    const li = document.createElement("li");
    const link = document.createElement("a");
    link.href = a.download_url;
    link.textContent = a.name;
    link.target = "_blank";
    li.appendChild(link);
    ul.appendChild(li);
  });

  const first = data.review?.change_summary || "(empty)";
  $("review-doc").textContent = first;

  const mdtmBox = $("review-mdtm");
  if (mdtmBox) {
    mdtmBox.textContent = JSON.stringify(
      {
        document_set_summary: data.document_set?.summary,
        mdtm_index_summary: data.document_set?.mdtm_index_summary,
        mdtm_impact_candidates_sample: (data.document_set?.mdtm_impact_candidates || []).slice(0, 8),
        mdtm_review_required_sample: (data.document_set?.mdtm_review_required || []).slice(0, 8),
        mdtm_patch_preview: data.document_set?.mdtm_patch_preview,
        mdtm_write_enabled: data.document_set?.mdtm_write_enabled === true,
      },
      null,
      2
    );
  }

  // Writer pipeline summary preview
  const writerPreview = {
    pipeline_summary: data.writer?.pipeline_summary,
    pilot_approval: data.writer?.pilot_approval,
    pilot_writer_result_summary: data.writer?.pilot_writer_result?.summary,
  };
  $("writer-out").textContent = JSON.stringify(writerPreview, null, 2);
}

$("btn-load-review").addEventListener("click", () => {
  const id = $("review-run-id").value.trim();
  if (id) loadReview(id);
});

document.querySelectorAll(".seg-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".seg-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const key = btn.dataset.doc;
    $("review-doc").textContent = state.reviewDocs[key] || "(empty)";
  });
});

$("run-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("btn-run");
  btn.disabled = true;
  setStatus($("run-status"), "실행 중… (문서 크기에 따라 수 분 걸릴 수 있습니다)", null);
  try {
    const fd = new FormData(e.target);
    // checkbox: only present when checked; FastAPI expects bool
    if (!fd.has("keep_output")) fd.set("keep_output", "false");
    else fd.set("keep_output", "true");
    fd.set("execute", "true");
    const res = await fetch("/api/pilot/runs", { method: "POST", body: fd });
    const text = await res.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      throw new Error(text);
    }
    if (!res.ok) throw new Error(data.detail || text);
    setStatus($("run-status"), `완료: ${data.run_id} · ${data.status}`, true);
    selectRun(data.run_id);
    await refreshRuns();
  } catch (err) {
    setStatus($("run-status"), String(err.message || err), false);
  } finally {
    btn.disabled = false;
  }
});

$("demo-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  setStatus($("run-status"), "데모 시나리오 복사 후 실행 중…", null);
  try {
    const fd = new FormData(e.target);
    fd.set("execute", "true");
    fd.set("scenario_name", "demo-copy");
    const res = await fetch("/api/pilot/runs/from-existing", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
    setStatus($("run-status"), `완료: ${data.run_id} · ${data.status}`, true);
    selectRun(data.run_id);
    await refreshRuns();
  } catch (err) {
    setStatus($("run-status"), String(err.message || err), false);
  }
});

$("btn-approve").addEventListener("click", async () => {
  const runId = $("writer-run-id").value.trim();
  if (!runId) return;
  const fd = new FormData();
  fd.set("decision", $("writer-decision").value);
  fd.set("approved_by", $("writer-by").value);
  fd.set("reason", $("writer-reason").value);
  const res = await fetch(`/api/pilot/runs/${encodeURIComponent(runId)}/approve`, {
    method: "POST",
    body: fd,
  });
  const data = await res.json();
  $("writer-out").textContent = JSON.stringify(data, null, 2);
});

$("btn-writer").addEventListener("click", async () => {
  const runId = $("writer-run-id").value.trim();
  if (!runId) return;
  $("writer-out").textContent = "Writer 실행 중…";
  const res = await fetch(`/api/pilot/runs/${encodeURIComponent(runId)}/writer`, {
    method: "POST",
  });
  const data = await res.json();
  $("writer-out").textContent = JSON.stringify(data, null, 2);
});

refreshRuns().catch(console.error);
