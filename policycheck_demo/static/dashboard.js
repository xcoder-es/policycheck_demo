(() => {
  const dataElement = document.getElementById("dashboard-data");
  if (!dataElement || typeof d3 === "undefined") return;

  const data = JSON.parse(dataElement.textContent || "{}");
  const money = new Intl.NumberFormat("en-GB", { notation: "compact", maximumFractionDigits: 1 });

  function drawDonut(selector, values) {
    const el = document.querySelector(selector);
    if (!el || !values?.length) return;
    el.innerHTML = "";
    const width = 260;
    const radius = width / 2;
    const svg = d3.select(el).append("svg").attr("viewBox", `0 0 ${width} ${width}`).attr("role", "img").attr("aria-label", "Compliance breakdown donut chart");
    svg.append("title").text("Compliance distribution");
    const group = svg.append("g").attr("transform", `translate(${radius},${radius})`);
    const arc = d3.arc().innerRadius(72).outerRadius(110);
    const pie = d3.pie().value((d) => d.count).sort(null);
    const classes = ["chart-good", "chart-warn", "chart-bad"];
    group.selectAll("path").data(pie(values)).enter().append("path").attr("d", arc).attr("class", (_d, i) => classes[i] || "chart-good");
    group.append("text").attr("text-anchor", "middle").attr("dy", "-0.2em").attr("class", "chart-total").text(values.reduce((s, d) => s + d.count, 0));
    group.append("text").attr("text-anchor", "middle").attr("dy", "1.4em").attr("class", "chart-caption").text("policies");
  }

  function drawBars(selector, values, labelKey = "type", valueKey = "count") {
    const el = document.querySelector(selector);
    if (!el || !values?.length) return;
    el.innerHTML = "";
    const max = Math.max(...values.map((d) => Number(d[valueKey]) || 0), 1);
    values.forEach((item) => {
      const row = document.createElement("div");
      row.className = "viz-bar-row";
      row.innerHTML = `<span>${item[labelKey]}</span><div><i style="width:${((Number(item[valueKey]) || 0) / max) * 100}%"></i></div><strong>${item[valueKey]}</strong>`;
      el.appendChild(row);
    });
  }

  function drawExposure(selector, values) {
    const scaled = (values || []).map((item) => ({ ...item, display: `£${money.format(item.value || 0)}` }));
    drawBars(selector, scaled, "label", "value");
    document.querySelectorAll(`${selector} .viz-bar-row strong`).forEach((node, index) => {
      node.textContent = scaled[index]?.display || "£0";
    });
  }

  drawDonut("#compliance-donut", data.compliance_breakdown || []);
  drawBars("#issue-bars", data.issue_categories || []);
  drawExposure("#exposure-bars", data.exposure_metrics || []);
  drawBars("#severity-bars", data.severity_distribution || [], "label", "count");

  const buttons = [...document.querySelectorAll("[data-filter]")];
  const rows = [...document.querySelectorAll(".exception-row")];
  const search = document.getElementById("exception-search");
  const sort = document.getElementById("exception-sort");

  function matchesFilter(row, filter) {
    if (filter === "all") return true;
    if (filter === "compliant") return row.dataset.status === "compliant";
    if (filter === "warnings") return row.dataset.status === "warning";
    if (filter === "breaches") return row.dataset.status === "breach";
    if (filter === "high") return row.dataset.severity === "high";
    return (row.dataset.issues || "").includes(filter);
  }

  function apply() {
    const active = document.querySelector("[data-filter][aria-pressed='true']")?.dataset.filter || "all";
    const term = (search?.value || "").toLowerCase().trim();
    rows.forEach((row) => {
      const visible = matchesFilter(row, active) && (!term || (row.dataset.search || "").includes(term));
      row.hidden = !visible;
    });
  }

  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      buttons.forEach((item) => item.setAttribute("aria-pressed", "false"));
      button.setAttribute("aria-pressed", "true");
      apply();
    });
  });
  search?.addEventListener("input", apply);
  sort?.addEventListener("change", () => {
    const tbody = document.querySelector(".exception-table tbody");
    const key = sort.value;
    const rank = { compliant: 1, warning: 2, breach: 3, low: 1, medium: 2, high: 3 };
    rows.sort((a, b) => {
      if (key === "sum") return Number(b.dataset.sum || 0) - Number(a.dataset.sum || 0);
      if (key === "bind") return (a.dataset.bind || "").localeCompare(b.dataset.bind || "");
      if (key === "status") return (rank[b.dataset.status] || 0) - (rank[a.dataset.status] || 0);
      return (rank[b.dataset.severity] || 0) - (rank[a.dataset.severity] || 0);
    }).forEach((row) => tbody.appendChild(row));
    apply();
  });
})();
