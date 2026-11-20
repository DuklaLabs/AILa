/* Sklad – společné pomůcky obou modulů (Sklad, Objednávky) + stránka Sklad.
   Data jdou z JSON API téže služby: GET/POST {BASE}/materials, {BASE}/orders …
   Záložky se řídí hashem (#prehled, #chemie, …) – jedna stránka, více sekcí. */
(function (w) {
  "use strict";
  var BASE = w.BASE_PATH || "";

  // ---------- pomůcky ----------
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function $(id) { return document.getElementById(id); }
  function num(v) { var n = Number(v); return isFinite(n) ? n : 0; }
  function fmtNum(n) { return (Math.round(num(n) * 100) / 100).toLocaleString("cs-CZ"); }

  var toastTimer;
  function toast(msg) {
    var t = $("toast"); if (!t) return;
    t.textContent = msg; t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.hidden = true; }, 3200);
  }

  function redirectToLogin() {
    var next = location.pathname + location.search;
    location.href = "/access/login?next=" + encodeURIComponent(next);
  }

  /* fetch s cookie; 401 → přihlášení; ostatní chyby jako výjimka */
  function api(path, opts) {
    opts = Object.assign({ credentials: "include" }, opts || {});
    return fetch(BASE + path, opts).then(function (res) {
      if (res.status === 401) { redirectToLogin(); throw new Error("401"); }
      if (!res.ok) {
        return res.text().then(function (t) {
          var e = new Error("HTTP " + res.status); e.status = res.status; e.body = t; throw e;
        });
      }
      return res.json();
    });
  }

  function showLoadError(msg) {
    var el = $("loadError"); if (!el) return;
    el.textContent = msg || ""; el.hidden = !msg;
  }

  // ---------- kategorie ----------
  var CATEGORIES = [
    { key: "spojovaci", label: "Spojovací materiál" },
    { key: "soucastky", label: "Součástky" },
    { key: "filamenty", label: "Filamenty" },
    { key: "chemie", label: "Chemie" },
    { key: "ostatni", label: "Ostatní" }
  ];
  function norm(s) {
    return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
  }
  /* null / neznámá kategorie → "ostatni"; tolerantní k diakritice a tvaru slova */
  function catKey(m) {
    var c = norm(m && m.category);
    if (!c) return "ostatni";
    if (c.indexOf("spoj") === 0 || c.indexOf("fastener") === 0) return "spojovaci";
    if (c.indexOf("soucast") === 0 || c.indexOf("component") === 0) return "soucastky";
    if (c.indexOf("filament") === 0) return "filamenty";
    if (c.indexOf("chem") === 0) return "chemie";
    return "ostatni";
  }
  function catLabel(key) {
    for (var i = 0; i < CATEGORIES.length; i++) if (CATEGORIES[i].key === key) return CATEGORIES[i].label;
    return "Ostatní";
  }
  function isLow(m) { return num(m.stock) < num(m.min_stock); }
  function unitOf(m) { return m.unit || "ks"; }

  // ---------- záložky v hashi ----------
  function initTabs(defaultKey, onShow) {
    var bar = document.querySelector(".tabbar");
    var links = bar.querySelectorAll("a[data-view]");
    var keys = Array.prototype.map.call(links, function (a) { return a.dataset.view; });
    function show() {
      var key = location.hash.replace("#", "");
      if (keys.indexOf(key) < 0) key = defaultKey;
      links.forEach(function (a) {
        if (a.dataset.view === key) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
      });
      document.querySelectorAll("section.view").forEach(function (s) { s.hidden = s.dataset.v !== key; });
      if (w.AilaUI) w.AilaUI.tabs(bar);
      if (onShow) onShow(key);
    }
    addEventListener("hashchange", show);
    show();
  }

  w.Sklad = {
    BASE: BASE, esc: esc, $: $, num: num, fmtNum: fmtNum, toast: toast, api: api,
    showLoadError: showLoadError, CATEGORIES: CATEGORIES, catKey: catKey, catLabel: catLabel,
    isLow: isLow, unitOf: unitOf, norm: norm, initTabs: initTabs
  };

  // ---------- stránka Sklad ----------
  if (!$("addForm")) return;

  var materials = [];

  function matRow(m) {
    var low = isLow(m);
    return '<div class="mrow' + (low ? " low" : "") + '">' +
      '<div class="nm">' + esc(m.name) + '<small>' + esc(catLabel(catKey(m))) + '</small></div>' +
      '<div class="qty num" data-l="Zásoba:"><span class="stock">' + fmtNum(m.stock) + "</span> " + esc(unitOf(m)) + "</div>" +
      '<div class="qty num" data-l="Minimum:">' + fmtNum(m.min_stock) + " " + esc(unitOf(m)) + "</div>" +
      '<div class="st">' + (low ? '<span class="pill s-a">Pod minimem</span>' : '<span class="pill s-p">V pořádku</span>') + "</div>" +
      "</div>";
  }
  function matList(items, emptyMsg) {
    if (!items.length) return '<div class="empty"><b>Nic tu není</b><span>' + esc(emptyMsg) + "</span></div>";
    return '<div class="mlist"><div class="mrow mhead"><div>Materiál</div><div class="qty">Zásoba</div><div class="qty">Minimum</div><div class="st">Stav</div></div>' +
      items.map(matRow).join("") + "</div>";
  }
  function byName(a, b) { return String(a.name).localeCompare(String(b.name), "cs"); }

  function render() {
    var low = materials.filter(isLow).sort(byName);
    $("tiles").innerHTML =
      '<div class="tile"><span class="k">Položek ve skladu</span><span class="v num">' + materials.length + '</span><span class="s">celkem materiálů</span></div>' +
      '<div class="tile' + (low.length ? " hl" : "") + '"><span class="k">Pod minimem</span><span class="v num">' + low.length + '</span><span class="s">' +
      (low.length ? "je potřeba doobjednat" : "zásoby jsou v pořádku") + "</span></div>";

    $("lowList").innerHTML = low.length
      ? '<div class="mlist">' + low.map(matRow).join("") + "</div>" +
        '<a class="btn primary" href="' + BASE + '/objednavky/#nova">Objednat</a>'
      : '<div class="empty"><b>Vše v pořádku</b><span>Žádný materiál není pod minimem.</span></div>';

    var counts = {};
    materials.forEach(function (m) { var k = catKey(m); counts[k] = (counts[k] || 0) + 1; });
    $("catChips").innerHTML = CATEGORIES.map(function (c) {
      return '<a class="chip" href="#' + c.key + '">' + esc(c.label) + " <em>" + (counts[c.key] || 0) + "</em></a>";
    }).join("");

    CATEGORIES.forEach(function (c) {
      var items = materials.filter(function (m) { return catKey(m) === c.key; }).sort(byName);
      $("list-" + c.key).innerHTML = matList(items, "V této kategorii zatím není žádný materiál.");
    });
  }

  function load() {
    return api("/materials").then(function (data) {
      materials = Array.isArray(data) ? data : [];
      showLoadError("");
      render();
    }).catch(function (e) {
      if (e.message !== "401") showLoadError("Nepodařilo se načíst sklad (Skladník neběží?).");
    });
  }

  // formulář
  var sel = $("fCategory");
  sel.innerHTML = CATEGORIES.map(function (c) { return '<option value="' + esc(c.label) + '">' + esc(c.label) + "</option>"; }).join("");
  sel.value = "Ostatní";

  $("addForm").addEventListener("submit", function (e) {
    e.preventDefault();
    var err = $("fError"); err.hidden = true;
    var name = $("fName").value.trim();
    if (!name) return;
    var stock = $("fStock").value === "" ? 0 : Number($("fStock").value);
    var min = $("fMin").value === "" ? 0 : Number($("fMin").value);
    if (!isFinite(stock) || !isFinite(min) || stock < 0 || min < 0) {
      err.textContent = "Zásoba a minimum musí být nezáporná čísla."; err.hidden = false; return;
    }
    var params = new URLSearchParams({ name: name, stock: String(stock), min_stock: String(min), category: sel.value });
    var unit = $("fUnit").value.trim(); if (unit) params.set("unit", unit);
    var btn = $("fSubmit"); btn.disabled = true;
    api("/materials?" + params.toString(), { method: "POST" }).then(function () {
      $("addForm").reset(); sel.value = "Ostatní";
      toast("Materiál přidán: " + name);
      return load();
    }).catch(function (e2) {
      if (e2.message !== "401") { err.textContent = "Materiál se nepodařilo přidat."; err.hidden = false; }
    }).then(function () { btn.disabled = false; });
  });

  initTabs("prehled");
  if (w.AilaUI) w.AilaUI.auto();
  load();
})(window);
