/* Shared light/dark switch for every AILa app (single source of truth —
   copied into each app at build time, like theme.css).
   - All apps live on one origin (Gateway), so the choice is stored once in
     localStorage["aila-theme"] and follows the user across modules.
   - No stored choice → follow the OS (prefers-color-scheme) and keep following it.
   - Injects a floating switch (.aila-theme, styled in theme.css) unless the
     page already has its own control (#theme, e.g. Krouzek). */
(function () {
  var KEY = "aila-theme", root = document.documentElement;
  function stored() { try { var v = localStorage.getItem(KEY); return v === "light" || v === "dark" ? v : null; } catch (e) { return null; } }
  function system() { return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; }
  function apply(mode) { root.dataset.theme = mode; root.style.colorScheme = mode; }
  apply(stored() || system());
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", function () { if (!stored()) apply(system()); });
  window.addEventListener("storage", function (e) { if (e.key === KEY && e.newValue) apply(e.newValue); });

  var SUN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>';
  var MOON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>';
  /* Logo menu: a click anywhere inside any .logo opens a dropdown — first "Rozcestník" (the hub at "/"),
     then the page's own sections, read from the links currently in nav.tabs (so it follows tabs that
     appear later, e.g. React). Picking a section clicks the original tab link. */
  var HOME_ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 11l9-8 9 8"/><path d="M5 10v10h5v-6h4v6h5V10"/></svg>';
  var menu = null, menuFor = null;
  function closeMenu() {
    if (!menu) return;
    menu.remove(); menu = null;
    if (menuFor) menuFor.setAttribute("aria-expanded", "false");
    menuFor = null;
  }
  function item(label, iconHtml, current) {
    var a = document.createElement("a");
    a.className = "aila-menu-item"; a.setAttribute("role", "menuitem");
    if (current) a.setAttribute("aria-current", "page");
    a.innerHTML = (iconHtml || "") + "<span></span>";
    a.lastChild.textContent = label;
    return a;
  }
  function openMenu(logo) {
    closeMenu();
    menu = document.createElement("div");
    menu.className = "aila-menu"; menu.setAttribute("role", "menu"); menu.setAttribute("aria-label", "Menu");
    var home = item("Rozcestník", HOME_ICON, location.pathname === "/" || location.pathname === "/index.html");
    home.href = "/";
    menu.appendChild(home);
    var tabs = document.querySelectorAll("nav.tabs a");
    if (tabs.length) menu.appendChild(Object.assign(document.createElement("hr"), { className: "aila-menu-sep" }));
    tabs.forEach(function (t) {
      var svg = t.querySelector("svg"), label = (t.textContent || t.getAttribute("aria-label") || "").trim();
      var el = item(label, svg ? svg.outerHTML : "", t.getAttribute("aria-current") === "page");
      if (t.getAttribute("href")) el.href = t.getAttribute("href"); else el.setAttribute("tabindex", "0");
      el.addEventListener("click", function (e) { e.preventDefault(); closeMenu(); t.click(); });
      menu.appendChild(el);
    });
    document.body.appendChild(menu);
    var r = logo.getBoundingClientRect();
    menu.style.top = Math.round(r.bottom + 8) + "px";
    menu.style.left = Math.max(8, Math.min(Math.round(r.left), innerWidth - menu.offsetWidth - 8)) + "px";
    logo.setAttribute("aria-expanded", "true"); menuFor = logo;
    var first = menu.querySelector("a"); if (first) first.focus({ preventScroll: true });
  }
  document.addEventListener("click", function (e) {
    var logo = e.target.closest && e.target.closest(".logo");
    if (logo) { e.preventDefault(); if (menu && menuFor === logo) closeMenu(); else openMenu(logo); return; }
    if (menu && !menu.contains(e.target)) closeMenu();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && menu) { var l = menuFor; closeMenu(); if (l) l.focus(); return; }
    var logo = e.target.closest && e.target.closest(".logo");
    if (logo && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); if (menu) closeMenu(); else openMenu(logo); return; }
    if (menu && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
      e.preventDefault();
      var items = Array.prototype.slice.call(menu.querySelectorAll("a")), i = items.indexOf(document.activeElement);
      items[(i + (e.key === "ArrowDown" ? 1 : items.length - 1)) % items.length].focus();
    }
  });
  addEventListener("resize", closeMenu);
  /* make every .logo (also ones React renders later) keyboard-reachable and announce the popup */
  function decorate() {
    document.querySelectorAll(".logo:not([data-menu])").forEach(function (l) {
      l.dataset.menu = "1"; l.setAttribute("tabindex", "0"); l.setAttribute("role", "button");
      l.setAttribute("aria-haspopup", "menu"); l.setAttribute("aria-expanded", "false");
      l.setAttribute("title", "Menu");
    });
  }
  function watchLogos() {
    decorate();
    new MutationObserver(decorate).observe(document.body, { childList: true, subtree: true });
  }
  function mount() {
    watchLogos();
    if (document.getElementById("theme") || document.querySelector(".aila-theme")) return;
    var box = document.createElement("div");
    box.className = "aila-theme"; box.setAttribute("role", "group"); box.setAttribute("aria-label", "Režim zobrazení");
    box.innerHTML = '<span class="knob"></span>' +
      '<button type="button" data-mode="light" aria-label="Světlý režim" title="Světlý režim">' + SUN + '</button>' +
      '<button type="button" data-mode="dark" aria-label="Tmavý režim" title="Tmavý režim">' + MOON + '</button>';
    function sync() {
      var m = root.dataset.theme; box.dataset.mode = m;
      box.querySelectorAll("button").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.mode === m)); });
    }
    box.addEventListener("click", function () {
      var next = root.dataset.theme === "dark" ? "light" : "dark";
      apply(next); try { localStorage.setItem(KEY, next); } catch (e) {} sync();
    });
    new MutationObserver(sync).observe(root, { attributes: true, attributeFilter: ["data-theme"] });
    sync(); document.body.appendChild(box);
  }
  if (document.body) mount(); else document.addEventListener("DOMContentLoaded", mount);
})();
