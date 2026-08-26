(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const config = window.PRINTWISE || { materials: {}, loggedIn: false };
  const draftKey = "printwise-draft-v1";
  const symbols = { USD: "$", EUR: "€", GBP: "£", CAD: "CA$", AUD: "A$" };
  let materialLines = [];
  let result = null;
  let timer;

  const numeric = (id) => Number($(id)?.value || 0);
  const money = (value) => `${symbols[$("currency")?.value] || "$"}${Number(value || 0).toFixed(2)}`;
  const notice = (message, error = false) => {
    const node = $("notice");
    if (!node) return;
    node.textContent = message;
    node.classList.toggle("error", error);
  };

  function defaultLine(mode = "FDM") {
    const name = mode === "Resin" ? "Resin" : "PLA";
    const preset = config.materials[name] || { cost: 0.05, density: 1.1 };
    return { name, cost_per_gram: preset.cost, density: preset.density };
  }

  function renderMaterials() {
    const host = $("materials");
    host.innerHTML = "";
    materialLines.forEach((line, index) => {
      const row = document.createElement("div");
      row.className = "material-editor";
      row.innerHTML = `<label>Material<select data-field="name"></select></label>
        <label>Cost / g<input data-field="cost_per_gram" type="number" min="0" step="0.001" value="${line.cost_per_gram}"></label>
        <label>Density<input data-field="density" type="number" min="0.01" step="0.01" value="${line.density}"></label>
        <button type="button" class="remove-material" aria-label="Remove material">×</button>`;
      const select = row.querySelector("select");
      Object.keys(config.materials).forEach((name) => select.add(new Option(name, name)));
      if (![...select.options].some((option) => option.value === line.name)) select.add(new Option(line.name, line.name));
      select.value = line.name;
      row.querySelectorAll("[data-field]").forEach((input) => input.addEventListener("input", () => {
        const field = input.dataset.field;
        line[field] = field === "name" ? input.value : Number(input.value || 0);
        if (field === "name" && config.materials[input.value]) {
          line.cost_per_gram = config.materials[input.value].cost;
          line.density = config.materials[input.value].density;
          renderMaterials();
        }
        changed();
      }));
      row.querySelector("button").addEventListener("click", () => {
        if (materialLines.length > 1) materialLines.splice(index, 1);
        renderMaterials(); changed();
      });
      host.append(row);
    });
  }

  function state() {
    return {
      part_name: $("partName").value,
      quantity: numeric("quantity"), print_hours: numeric("printHours"), print_minutes: numeric("printMinutes"),
      labor_hours: numeric("laborHours"), labor_minutes: numeric("laborMinutes"), labor_rate: numeric("laborRate"),
      hardware: numeric("hardware"), packaging: numeric("packaging"), tax_rate: numeric("taxRate"),
      electricity_rate: numeric("electricityRate"), power_watts: numeric("powerWatts"), waste_rate: numeric("wasteRate"),
      printer_cost: numeric("printerCost"), printer_life_hours: numeric("printerLifeHours"), maintenance_rate: numeric("maintenanceRate"),
      failure_rate: numeric("failureRate"), overhead_rate: numeric("overheadRate"), setup_cost: numeric("setupCost"),
      setup_minutes: numeric("setupMinutes"),
      custom_margin: numeric("customMargin"), currency: $("currency").value,
      material_lines: materialLines.map((line) => ({ ...line, grams: numeric("weight") / materialLines.length, volume_ml: numeric("volume") / materialLines.length }))
    };
  }

  function apply(saved) {
    const map = { part_name: "partName", quantity: "quantity", print_hours: "printHours", print_minutes: "printMinutes", labor_hours: "laborHours", labor_minutes: "laborMinutes", labor_rate: "laborRate", hardware: "hardware", packaging: "packaging", tax_rate: "taxRate", electricity_rate: "electricityRate", power_watts: "powerWatts", waste_rate: "wasteRate", printer_cost: "printerCost", printer_life_hours: "printerLifeHours", maintenance_rate: "maintenanceRate", failure_rate: "failureRate", overhead_rate: "overheadRate", setup_cost: "setupCost", setup_minutes: "setupMinutes", custom_margin: "customMargin", currency: "currency" };
    Object.entries(map).forEach(([key, id]) => { if (saved[key] !== undefined && $(id)) $(id).value = saved[key]; });
    if (saved.material_lines?.length) materialLines = saved.material_lines.map(({ name, cost_per_gram, density }) => ({ name, cost_per_gram, density }));
    renderMaterials();
  }

  async function calculate() {
    try {
      const response = await fetch("/api/calculate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(state()) });
      if (!response.ok) throw new Error("Calculation failed");
      result = await response.json();
      renderResult(); notice("");
    } catch (error) { notice(error.message, true); }
  }

  function renderResult() {
    $("total").textContent = money(result.total);
    $("unitCost").textContent = money(result.unit_cost);
    $("summary").textContent = `${result.quantity} ${result.quantity === 1 ? "part" : "parts"}`;
    $("weightSummary").textContent = `${result.weight.toFixed(1)} g`;
    const entries = Object.entries(result.breakdown).filter(([, value]) => value > 0);
    $("breakdown").innerHTML = entries.map(([name, value]) => `<div class="breakdown-row"><span>${name}</span><strong>${money(value)}</strong></div>`).join("");
    const maximum = Math.max(...entries.map(([, value]) => value), 1);
    $("meterFill").style.width = `${Math.min(100, maximum / Math.max(result.total, 1) * 100)}%`;
    [25, 40, 60, 80].forEach((margin) => $(`price${margin}`).textContent = money(result.prices[String(margin)]));
    $("priceCustom").textContent = money(result.prices.custom);
  }

  function changed() {
    localStorage.setItem(draftKey, JSON.stringify(state()));
    clearTimeout(timer); timer = setTimeout(calculate, 120);
  }

  async function copyShare() {
    const encoded = btoa(unescape(encodeURIComponent(JSON.stringify(state()))));
    const url = `${location.origin}${location.pathname}#quote=${encoded}`;
    await navigator.clipboard.writeText(url);
    notice("Share link copied. It contains the quote inputs, not account data.");
  }

  async function api(path, method = "GET", body) {
    const response = await fetch(path, { method, headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
    if (!response.ok) throw new Error((await response.json()).error || "Request failed");
    return response.json();
  }

  function accountPanel() {
    if (!config.loggedIn) return;
    const card = document.createElement("section");
    card.className = "card account-card";
    card.innerHTML = `<div class="section-heading"><div><span class="step">04</span><h2>Account library</h2></div></div>
      <p class="hint">Save reusable settings, materials, printers, and complete quotes to this profile.</p>
      <div class="account-actions"><button type="button" data-save="preferences">Save preferences</button><button type="button" data-save="material-presets">Save material preset</button><button type="button" data-save="printer-profiles">Save printer profile</button><button type="button" data-save="quotes">Save quote</button></div>
      <div id="accountItems" class="saved-grid"></div>`;
    $("calculator").append(card);
    card.querySelectorAll("[data-save]").forEach((button) => button.addEventListener("click", async () => {
      try {
        const kind = button.dataset.save;
        const payload = state();
        if (kind === "preferences") await api("/api/preferences", "POST", payload);
        else {
          const fallback = kind === "quotes" ? $("partName").value : materialLines[0]?.name;
          const name = prompt("Name", fallback || "Saved item");
          if (!name) return;
          await api(`/api/${kind}`, "POST", { ...payload, name });
        }
        notice("Saved to your profile."); loadAccountItems();
      } catch (error) { notice(error.message, true); }
    }));
    loadAccountItems();
  }

  async function loadAccountItems() {
    try {
      const groups = await Promise.all(["material-presets", "printer-profiles", "quotes"].map(async (kind) => [kind, await api(`/api/${kind}`)]));
      $("accountItems").innerHTML = groups.flatMap(([kind, items]) => items.map((item) => `<button type="button" data-kind="${kind}" data-id="${item.id}"><strong>${item.name}</strong><small>${kind.replace("-", " ")}</small></button>`)).join("") || "<p class='hint'>Nothing saved yet.</p>";
      $("accountItems").querySelectorAll("button").forEach((button) => button.addEventListener("click", async () => {
        const items = groups.find(([kind]) => kind === button.dataset.kind)[1];
        const item = items.find(({ id }) => String(id) === button.dataset.id);
        apply(item.data); changed(); notice(`Loaded ${item.name}.`);
      }));
    } catch (error) { notice(error.message, true); }
  }

  document.querySelectorAll("#calculator input, #calculator select").forEach((input) => input.addEventListener("input", changed));
  document.querySelectorAll(".mode").forEach((button) => button.addEventListener("click", () => {
    document.querySelectorAll(".mode").forEach((item) => { item.classList.toggle("active", item === button); item.setAttribute("aria-selected", item === button); });
    materialLines = [defaultLine(button.dataset.mode)]; renderMaterials(); changed();
  }));
  $("addMaterial").addEventListener("click", () => { materialLines.push(defaultLine()); renderMaterials(); changed(); });
  document.querySelector(".collapse-button").addEventListener("click", (event) => { const hidden = $("advanced").hidden; $("advanced").hidden = !hidden; event.currentTarget.textContent = hidden ? "Hide advanced" : "Show advanced"; event.currentTarget.setAttribute("aria-expanded", String(hidden)); });
  $("themeToggle").addEventListener("click", () => { const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark"; document.documentElement.dataset.theme = theme; localStorage.setItem("printwise-theme", theme); });
  $("reset").addEventListener("click", () => { localStorage.removeItem(draftKey); location.hash = ""; location.reload(); });
  $("share").addEventListener("click", () => copyShare().catch(() => notice("Could not copy the share link.", true)));
  $("print").addEventListener("click", () => window.print());

  document.documentElement.dataset.theme = localStorage.getItem("printwise-theme") || "light";
  materialLines = [defaultLine()];
  try {
    if (location.hash.startsWith("#quote=")) apply(JSON.parse(decodeURIComponent(escape(atob(location.hash.slice(7))))));
    else if (localStorage.getItem(draftKey)) apply(JSON.parse(localStorage.getItem(draftKey)));
    else renderMaterials();
  } catch { renderMaterials(); notice("The shared quote could not be read; defaults were loaded.", true); }
  accountPanel(); calculate();
})();
