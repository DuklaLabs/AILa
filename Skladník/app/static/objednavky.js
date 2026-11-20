/* Modul Objednávky – stránka {BASE}/objednavky/. Používá pomůcky ze sklad.js (window.Sklad). */
(function (w) {
  "use strict";
  var S = w.Sklad, esc = S.esc, $ = S.$, api = S.api;

  var STATUS = {
    draft:    { label: "Rozpracovaná", cls: "s-x" },
    created:  { label: "Vytvořená",    cls: "st-run" },
    sent:     { label: "Odeslaná",     cls: "s-u" },
    received: { label: "Přijatá",      cls: "s-p" },
    canceled: { label: "Zrušená",      cls: "s-a" }
  };
  /* tlačítka podle stavu: [cílový stav, popisek, třída] */
  var ACTIONS = {
    draft:   [["created", "Vytvořit", "primary"], ["canceled", "Zrušit", "danger"]],
    created: [["sent", "Odeslat", "primary"], ["canceled", "Zrušit", "danger"]],
    sent:    [["received", "Přijato", "primary"], ["canceled", "Zrušit", "danger"]],
    received: [], canceled: []
  };

  var orders = [], materials = [];
  var qty = {};            // material_id -> množství v nové objednávce

  function fmtDate(v) {
    if (!v) return "";
    var d = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(v) ? v : v + "Z");
    return isNaN(d.getTime()) ? String(v) : d.toLocaleString("cs-CZ");
  }

  function orderCard(o) {
    var st = STATUS[o.status] || STATUS.draft;
    var items = (o.items || []).map(function (it) {
      return '<span class="chip">' + esc(it.material_name || ("#" + it.material_id)) +
        " <em>× " + S.fmtNum(it.quantity) + (it.unit ? " " + esc(it.unit) : "") + "</em></span>";
    }).join("");
    var acts = (ACTIONS[o.status] || []).map(function (a) {
      return '<button type="button" class="btn sm ' + a[2] + '" data-oid="' + o.order_id + '" data-to="' + a[0] + '">' + a[1] + "</button>";
    }).join("");
    return '<article class="order">' +
      '<div class="order-head"><h3>Objednávka #' + o.order_id + "</h3>" +
      '<span class="pill ' + st.cls + '">' + st.label + "</span></div>" +
      '<div class="when">' + esc(fmtDate(o.created_at)) + "</div>" +
      (items ? '<div class="chips">' + items + "</div>" : '<div class="hint">Bez položek.</div>') +
      (o.note ? '<p class="note">' + esc(o.note) + "</p>" : "") +
      (acts ? '<div class="order-actions">' + acts + "</div>" : "") +
      "</article>";
  }
  function orderList(list, emptyMsg) {
    if (!list.length) return '<div class="empty"><b>Nic tu není</b><span>' + esc(emptyMsg) + "</span></div>";
    return list.map(orderCard).join("");
  }
  function byIdDesc(a, b) { return b.order_id - a.order_id; }
  function withStatus() {
    var set = Array.prototype.slice.call(arguments);
    return orders.filter(function (o) { return set.indexOf(o.status) >= 0; }).sort(byIdDesc);
  }

  function renderOrders() {
    var counts = {};
    orders.forEach(function (o) { counts[o.status] = (counts[o.status] || 0) + 1; });
    var waiting = (counts.created || 0) + (counts.sent || 0);
    $("tiles").innerHTML =
      '<div class="tile"><span class="k">Objednávek celkem</span><span class="v num">' + orders.length + "</span></div>" +
      '<div class="tile' + (waiting ? " hl" : "") + '"><span class="k">Čekající</span><span class="v num">' + waiting + '</span><span class="s">vytvořené ' + (counts.created || 0) + " · odeslané " + (counts.sent || 0) + "</span></div>" +
      '<div class="tile"><span class="k">Rozpracované</span><span class="v num">' + (counts.draft || 0) + "</span></div>" +
      '<div class="tile"><span class="k">Vyřízené</span><span class="v num">' + (counts.received || 0) + '</span><span class="s">zrušené ' + (counts.canceled || 0) + "</span></div>";

    $("list-prehled").innerHTML = orderList(orders.slice().sort(byIdDesc), "Zatím žádné objednávky. Založ první v záložce Nová.");
    $("list-vyrizene").innerHTML = orderList(withStatus("received"), "Žádná objednávka ještě nedorazila.");
    $("list-cekajici").innerHTML = orderList(withStatus("created", "sent"), "Na nic se nečeká.");
    $("list-rozpracovane").innerHTML = orderList(withStatus("draft"), "Žádné rozpracované objednávky.");
  }

  // ---------- změna stavu (zrušení potvrdit druhým kliknutím) ----------
  document.addEventListener("click", function (e) {
    var b = e.target.closest("button[data-oid]"); if (!b) return;
    var to = b.dataset.to;
    if (to === "canceled" && !b.classList.contains("armed")) {
      b.classList.add("armed"); b.textContent = "Opravdu zrušit?";
      setTimeout(function () { b.classList.remove("armed"); b.textContent = "Zrušit"; }, 4000);
      return;
    }
    b.disabled = true;
    api("/orders/" + b.dataset.oid + "/status?status=" + encodeURIComponent(to), { method: "POST" })
      .then(function () { S.toast("Objednávka #" + b.dataset.oid + ": " + STATUS[to].label.toLowerCase()); return loadOrders(); })
      .catch(function (err) { if (err.message !== "401") { S.toast("Změna stavu se nezdařila."); b.disabled = false; } });
  });

  // ---------- nová objednávka ----------
  function renderPick() {
    var q = S.norm($("nSearch").value);
    var list = materials.filter(function (m) {
      return !q || S.norm(m.name).indexOf(q) >= 0 || S.norm(S.catLabel(S.catKey(m))).indexOf(q) >= 0;
    }).sort(function (a, b) { return (S.isLow(b) - S.isLow(a)) || String(a.name).localeCompare(String(b.name), "cs"); });
    $("nList").innerHTML = list.length ? list.map(function (m) {
      var v = qty[m.id];
      return '<div class="pickrow' + (v > 0 ? " on" : "") + (S.isLow(m) ? " low" : "") + '">' +
        '<div class="nm">' + esc(m.name) + "<small>" + esc(S.catLabel(S.catKey(m))) + "</small></div>" +
        '<div class="stk num">' + S.fmtNum(m.stock) + " / min " + S.fmtNum(m.min_stock) + " " + esc(S.unitOf(m)) + "</div>" +
        '<input type="number" min="0" step="any" inputmode="decimal" placeholder="0" aria-label="Množství: ' + esc(m.name) + '" data-mid="' + m.id + '"' + (v > 0 ? ' value="' + v + '"' : "") + ">" +
        "</div>";
    }).join("") : '<div class="empty"><b>Nic nenalezeno</b><span>' + (materials.length ? "Zkus jiný hledaný výraz." : "Sklad je prázdný, nejdřív přidej materiál.") + "</span></div>";
    updateSummary();
  }
  function updateSummary() {
    var n = Object.keys(qty).filter(function (k) { return qty[k] > 0; }).length;
    $("nSummary").textContent = n ? "Vybráno položek: " + n : "Zatím nic nevybráno.";
  }

  $("nList").addEventListener("input", function (e) {
    var inp = e.target.closest("input[data-mid]"); if (!inp) return;
    var v = Number(inp.value);
    if (isFinite(v) && v > 0) qty[inp.dataset.mid] = v; else delete qty[inp.dataset.mid];
    inp.closest(".pickrow").classList.toggle("on", !!qty[inp.dataset.mid]);
    updateSummary();
  });
  $("nSearch").addEventListener("input", renderPick);
  $("nFillLow").addEventListener("click", function () {
    var any = false;
    materials.filter(S.isLow).forEach(function (m) {
      var need = Math.ceil((S.num(m.min_stock) - S.num(m.stock)) * 100) / 100;
      if (need > 0) { qty[m.id] = need; any = true; }
    });
    if (!any) S.toast("Nic není pod minimem.");
    renderPick();
  });
  $("nClear").addEventListener("click", function () { qty = {}; renderPick(); });

  function submitOrder(status) {
    var err = $("nError"); err.hidden = true;
    var ids = Object.keys(qty).filter(function (k) { return qty[k] > 0; });
    if (!ids.length) { err.textContent = "Vyber alespoň jednu položku a zadej množství."; err.hidden = false; return Promise.resolve(); }
    var btns = [$("nDraft"), $("nCreate")]; btns.forEach(function (b) { b.disabled = true; });
    var p = new URLSearchParams({ status: status });
    var note = $("nNote").value.trim(); if (note) p.set("note", note);
    return api("/orders?" + p.toString(), { method: "POST" }).then(function (order) {
      var oid = order.id;
      return ids.reduce(function (chain, mid) {
        return chain.then(function () {
          return api("/orders/" + oid + "/item?material_id=" + encodeURIComponent(mid) + "&quantity=" + encodeURIComponent(qty[mid]), { method: "POST" });
        });
      }, Promise.resolve()).then(function () { return oid; });
    }).then(function (oid) {
      qty = {}; $("nNote").value = ""; $("nSearch").value = "";
      S.toast("Objednávka #" + oid + (status === "draft" ? " uložena jako rozpracovaná." : " vytvořena."));
      return loadOrders().then(function () { renderPick(); location.hash = status === "draft" ? "#rozpracovane" : "#cekajici"; });
    }).catch(function (e) {
      if (e.message !== "401") { err.textContent = "Objednávku se nepodařilo uložit."; err.hidden = false; }
    }).then(function () { btns.forEach(function (b) { b.disabled = false; }); });
  }
  $("newForm").addEventListener("submit", function (e) { e.preventDefault(); submitOrder("created"); });
  $("nDraft").addEventListener("click", function () { submitOrder("draft"); });

  // ---------- načtení ----------
  function loadOrders() {
    return api("/orders").then(function (d) { orders = Array.isArray(d) ? d : []; S.showLoadError(""); renderOrders(); });
  }
  function loadAll() {
    return Promise.all([
      api("/materials").then(function (d) { materials = Array.isArray(d) ? d : []; renderPick(); }),
      loadOrders()
    ]).catch(function (e) { if (e.message !== "401") S.showLoadError("Nepodařilo se načíst data (Skladník neběží?)."); });
  }

  S.initTabs("prehled");
  if (w.AilaUI) w.AilaUI.auto();
  loadAll();
})(window);
