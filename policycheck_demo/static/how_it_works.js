(() => {
  const steps = [
    ["BAA ingestion", "The user uploads a text-based BAA PDF or enters reviewed controls manually."],
    ["Text extraction", "The document is converted into text without OCR or heavy processing."],
    ["AI-assisted extraction", "AI may identify candidate dates, territories, classes, limits and endorsements. These are not final decisions."],
    ["Human review", "The operator reviews and edits the extracted controls before validation."],
    ["Digital twin", "Reviewed controls become the executable rule set for the demo session."],
    ["Portfolio data", "A CSV bordereaux can be uploaded, or a synthetic portfolio can be generated."],
    ["Deterministic validation", "Each policy row is checked using auditable rules: date, territory, class, authority limit and endorsements."],
    ["Exception intelligence", "The results page summarises compliance, issue patterns, severity and exposure."],
    ["Audit-ready report", "The exception report adds status, severity, issue text and checked timestamp to the source rows."],
  ];

  const timeline = document.getElementById("workflow-timeline");
  const title = document.getElementById("workflow-detail-title");
  const body = document.getElementById("workflow-detail-body");
  if (timeline && title && body) {
    steps.forEach(([label, detail], index) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "timeline-step";
      button.textContent = `${index + 1}. ${label}`;
      button.setAttribute("aria-pressed", index === 0 ? "true" : "false");
      button.addEventListener("click", () => {
        document.querySelectorAll(".timeline-step").forEach((item) => item.setAttribute("aria-pressed", "false"));
        button.setAttribute("aria-pressed", "true");
        title.textContent = label;
        body.textContent = detail;
      });
      timeline.appendChild(button);
    });
    title.textContent = steps[0][0];
    body.textContent = steps[0][1];
  }

  const nodes = [...document.querySelectorAll(".arch-node")];
  const panel = document.getElementById("architecture-detail");
  nodes.forEach((node) => {
    node.addEventListener("click", () => {
      nodes.forEach((item) => item.setAttribute("aria-pressed", "false"));
      node.setAttribute("aria-pressed", "true");
      if (panel) panel.textContent = node.dataset.detail || "This layer participates in the validation workflow.";
    });
  });
})();
