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
  /* Logo menu: a click anywhere inside any .logo opens a dropdown listing ALL modules of AILa (one place
     to edit the list — the Gateway routes are path prefixes on one origin). The module's own navigation
     (nav.tabs) is untouched and stays on the page. The module the visitor is in is highlighted. */
  function svg(path) { return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + path + '</svg>'; }
  var MODULES = [
    { title: "Rozcestník", href: "/", match: /^\/(index\.html)?$/, icon: svg('<path d="M3 11l9-8 9 8"/><path d="M5 10v10h5v-6h4v6h5V10"/>') },
    { title: "Volné hodiny", href: "/access/", match: /^\/access(?!\/machines)(\/|$)/, icon: svg('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>') },
    { title: "Projekty", href: "/projects/app/projects/", match: /^\/projects(\/|$)/, icon: svg('<rect x="3" y="3" width="7" height="9" rx="2"/><rect x="14" y="3" width="7" height="5" rx="2"/><rect x="14" y="12" width="7" height="9" rx="2"/><rect x="3" y="16" width="7" height="5" rx="2"/>') },
    { title: "Kroužek", href: "/krouzek/", match: /^\/krouzek(\/|$)/, icon: svg('<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>') },
    { title: "Stroje", href: "/access/machines", match: /^\/access\/machines(\/|$)/, icon: svg('<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18v3h3l6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.4-.6-.6-2.4z"/>') }
  ];
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
    MODULES.forEach(function (m) {
      var el = item(m.title, m.icon, m.match.test(location.pathname));
      el.href = m.href;
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
