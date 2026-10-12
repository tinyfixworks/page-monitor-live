const state = { links: [], report: null, query: "", status: "all", area: "all" };
const $ = (id) => document.getElementById(id);

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[char]));
}

function statusOf(link) {
  if (link.classification) return link.classification;
  if (link.broken) return "broken";
  if (link.status === null || link.status === undefined || link.status === 403 || link.status === 429 || link.status >= 500) return "review";
  if (link.status >= 400) return "broken";
  return "ok";
}

function statusLabel(status) {
  return ({ broken: "Broken", review: "Needs review", ok: "Healthy" })[status] || "Unknown";
}

function statusClass(status) {
  return ({ broken: "bad", review: "warn", ok: "good" })[status] || "neutral";
}

function formatDate(value) {
  if (!value) return "Unknown";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit", timeZoneName: "short"
  }).format(date);
}

function primarySource(link) {
  return (link.sources || [])[0] || {};
}

function allSearchText(link) {
  const sources = (link.sources || []).map(source =>
    [source.text, source.title, source.area, source.section, source.element_type,
      ...(source.images || []).flatMap(image => [image.alt, image.src])]
      .join(" ")
  ).join(" ");
  return `${link.url} ${link.final_url || ""} ${link.error || ""} ${sources}`.toLowerCase();
}

function filteredLinks() {
  return state.links.filter(link => {
    const status = statusOf(link);
    const matchesStatus = state.status === "all" || status === state.status;
    const matchesArea = state.area === "all" || (link.sources || []).some(source => source.area === state.area);
    const matchesQuery = !state.query || allSearchText(link).includes(state.query);
    return matchesStatus && matchesArea && matchesQuery;
  }).sort((a, b) => {
    const order = { broken: 0, review: 1, ok: 2 };
    return order[statusOf(a)] - order[statusOf(b)] || a.url.localeCompare(b.url);
  });
}

function sourceSummary(link) {
  const sources = link.sources || [];
  const areas = [...new Set(sources.map(source => source.area || "main/page"))];
  return `${sources.length} source${sources.length === 1 ? "" : "s"} · ${areas.join(", ")}`;
}

function render() {
  const links = filteredLinks();
  $("results-body").innerHTML = links.length ? links.map((link, index) => {
    const status = statusOf(link);
    const source = primarySource(link);
    const label = source.text || source.title || source.images?.map(image => image.alt).filter(Boolean).join(", ") || "No visible label";
    const location = [source.area, source.section].filter(Boolean).join(" / ") || "Page";
    const code = link.status ? `HTTP ${link.status}` : "No response";
    return `<tr>
      <td><a class="url-cell" href="${escapeHTML(link.url)}" target="_blank" rel="noreferrer">${escapeHTML(link.url)} <span>↗</span></a>
        ${link.final_url && link.final_url !== link.url ? `<div class="subtext">Redirects to ${escapeHTML(link.final_url)}</div>` : ""}
      </td>
      <td><span class="status-pill ${statusClass(status)}"><span></span>${statusLabel(status)}</span><div class="subtext">${escapeHTML(code)}</div></td>
      <td><div class="location-cell">${escapeHTML(location)}</div><div class="subtext">${escapeHTML(sourceSummary(link))}</div></td>
      <td><div class="content-cell">${escapeHTML(label)}</div>${source.element_type ? `<div class="subtext">${escapeHTML(source.element_type)}</div>` : ""}</td>
      <td><button class="details-button" data-index="${index}" type="button">Details <span>→</span></button></td>
    </tr>`;
  }).join("") : `<tr><td colspan="5" class="empty-cell">No results match these filters.</td></tr>`;

  $("showing-count").textContent = `Showing ${links.length} of ${state.links.length} links`;
  $("result-caption").textContent = `${state.report?.checked_link_count ?? state.links.length} unique destinations checked`;
  document.querySelectorAll(".details-button").forEach(button => {
    button.addEventListener("click", () => openDetails(links[Number(button.dataset.index)]));
  });
}

function openDetails(link) {
  const status = statusOf(link);
  $("dialog-title").textContent = link.url;
  const sources = (link.sources || []).map((source, index) => {
    const images = (source.images || []).map(image => `
      <div class="image-detail">
        ${image.src ? `<a href="${escapeHTML(image.src)}" target="_blank" rel="noreferrer">${escapeHTML(image.src)}</a>` : ""}
        <div>Alt text: ${escapeHTML(image.alt || "No alt text")}</div>
      </div>`).join("");
    return `<article class="source-card">
      <div class="source-card-top"><span class="source-number">SOURCE ${String(index + 1).padStart(2, "0")}</span><span class="status-pill ${statusClass(status)}"><span></span>${statusLabel(status)}</span></div>
      <div class="detail-grid">
        <div><label>Page area</label><strong>${escapeHTML(source.area || "Unknown")}</strong></div>
        <div><label>Section</label><strong>${escapeHTML(source.section || "No heading detected")}</strong></div>
        <div><label>Element type</label><strong>${escapeHTML(source.element_type || "Link")}</strong></div>
        <div><label>Visible text</label><strong>${escapeHTML(source.text || "No visible text")}</strong></div>
      </div>
      ${source.title ? `<div class="detail-line"><label>Title</label><span>${escapeHTML(source.title)}</span></div>` : ""}
      ${source.href ? `<div class="detail-line"><label>Original href</label><code>${escapeHTML(source.href)}</code></div>` : ""}
      ${source.selector ? `<div class="detail-line"><label>DOM path</label><code>${escapeHTML(source.selector)}</code></div>` : ""}
      ${images}
    </article>`;
  }).join("");

  $("dialog-content").innerHTML = `
    <div class="detail-summary">
      <span class="status-pill ${statusClass(status)}"><span></span>${statusLabel(status)}</span>
      <span>${escapeHTML(link.status ? `HTTP ${link.status}` : "No HTTP response")}</span>
    </div>
    ${link.error ? `<div class="error-box"><label>Check result</label><p>${escapeHTML(link.error)}</p></div>` : ""}
    ${link.final_url && link.final_url !== link.url ? `<div class="detail-line"><label>Final URL</label><a href="${escapeHTML(link.final_url)}" target="_blank" rel="noreferrer">${escapeHTML(link.final_url)}</a></div>` : ""}
    <h3 class="sources-heading">Where this link appears <span>${(link.sources || []).length}</span></h3>
    ${sources || `<p class="empty-cell">No source metadata available. Run a new check to collect it.</p>`}`;
  $("details-dialog").showModal();
}

async function loadReport() {
  try {
    const response = await fetch(`results.json?updated=${Date.now()}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const report = await response.json();
    state.report = report;
    state.links = Array.isArray(report.all_links) ? report.all_links : [
      ...(report.broken_links || []), ...(report.review_links || [])
    ];
    const broken = state.links.filter(link => statusOf(link) === "broken").length;
    const review = state.links.filter(link => statusOf(link) === "review").length;
    $("total-count").textContent = state.links.length.toLocaleString();
    $("healthy-count").textContent = (state.links.length - broken - review).toLocaleString();
    $("broken-count").textContent = broken.toLocaleString();
    $("review-count").textContent = review.toLocaleString();
    $("last-check").innerHTML = `<span class="status-dot"></span><span>Last check <strong>${escapeHTML(formatDate(report.checked_at))}</strong></span>`;
    $("load-error").classList.add("hidden");
    render();
  } catch (error) {
    $("load-error").classList.remove("hidden");
    $("last-check").innerHTML = `<span class="status-dot error"></span><span>Report could not be loaded</span>`;
    $("results-body").innerHTML = `<tr><td colspan="5" class="empty-cell">No report available yet. ${escapeHTML(error.message)}</td></tr>`;
  }
}

$("search").addEventListener("input", event => {
  state.query = event.target.value.trim().toLowerCase();
  render();
});
$("status-filter").addEventListener("change", event => {
  state.status = event.target.value;
  render();
});
$("area-filter").addEventListener("change", event => {
  state.area = event.target.value;
  render();
});
$("close-dialog").addEventListener("click", () => $("details-dialog").close());
$("details-dialog").addEventListener("click", event => {
  if (event.target === $("details-dialog")) $("details-dialog").close();
});

loadReport();
