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
  /* portal views live in the hash (#chat, #inventory, ...): one page, several "modules" */
  var PORTAL_HASH = /^#(chat|inventory|orders|wiki)$/;
  function portal(h) { return function (path, hash) { return /^\/(index\.html)?$/.test(path) && hash === h; }; }
  var MODULES = [
    { title: "Rozcestník", href: "/", on: function (p, h) { return /^\/(index\.html)?$/.test(p) && !PORTAL_HASH.test(h); }, icon: svg('<path d="M3 11l9-8 9 8"/><path d="M5 10v10h5v-6h4v6h5V10"/>') },
    { title: "Volné hodiny", href: "/access/", on: function (p) { return /^\/access(\/|$)/.test(p) && !/^\/access\/(machines|admin\/(analytics|users))(\/|$)/.test(p); }, icon: svg('<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>') },
    { title: "Chat s AIla", href: "/#chat", on: portal("#chat"), icon: svg('<path d="M21 12a8 8 0 0 1-11.6 7.1L3 21l1.9-5.4A8 8 0 1 1 21 12z"/>') },
    { title: "Projekty", href: "/projects/app/projects/", on: function (p) { return /^\/projects(\/|$)/.test(p); }, icon: svg('<rect x="3" y="3" width="7" height="9" rx="2"/><rect x="14" y="3" width="7" height="5" rx="2"/><rect x="14" y="12" width="7" height="9" rx="2"/><rect x="3" y="16" width="7" height="5" rx="2"/>') },
    { title: "Kroužek", href: "/krouzek/", on: function (p) { return /^\/krouzek(\/|$)/.test(p); }, icon: svg('<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1"/>') },
    { title: "Stroje", href: "/access/machines", on: function (p) { return /^\/access\/machines(\/|$)/.test(p); }, icon: svg('<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18v3h3l6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.4-.6-.6-2.4z"/>') },
    { title: "Sklad", href: "/#inventory", on: portal("#inventory"), icon: svg('<path d="M21 8l-9-5-9 5 9 5 9-5z"/><path d="M3 8v8l9 5 9-5V8M12 13v8"/>') },
    { title: "Objednávky", href: "/#orders", on: portal("#orders"), icon: svg('<circle cx="9" cy="20" r="1.5"/><circle cx="18" cy="20" r="1.5"/><path d="M2 3h3l2.7 12.4a2 2 0 0 0 2 1.6h7.7a2 2 0 0 0 2-1.5L21 8H6"/>') },
    { title: "Analytika", href: "/access/admin/analytics", staff: true, on: function (p) { return /^\/access\/admin\/analytics(\/|$)/.test(p); }, icon: svg('<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>') },
    { title: "Uživatelé", href: "/access/admin/users", staff: true, on: function (p) { return /^\/access\/admin\/users(\/|$)/.test(p); }, icon: svg('<circle cx="9" cy="8" r="4"/><path d="M2 21a7 7 0 0 1 14 0"/><path d="M16 4a4 4 0 0 1 0 8M22 21a7 7 0 0 0-4-6.3"/>') },
    { title: "DuklaWiki", href: "/#wiki", on: portal("#wiki"), icon: svg('<path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v17H6.5A2.5 2.5 0 0 0 4 21.5z"/><path d="M4 19.5V4.5M9 7h7M9 11h7"/>') }
  ];
  /* Analytika / Uživatelé are staff-only pages: show them only to admin/staff (cached /access/api/whoami) */
  var staffP = null;
  function isStaff() {
    if (!staffP) staffP = fetch("/access/api/whoami", { credentials: "include" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (u) { return !!u && (u.role === "admin" || u.role === "staff"); })
      .catch(function () { return false; });
    return staffP;
  }
  var menu = null, menuFor = null;
  function closeMenu() {
    if (menu) { menu.remove(); menu = null; }
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
    menuFor = logo;
    isStaff().then(function (staff) {
      if (menuFor !== logo || menu) return;   // closed or re-opened meanwhile
      menu = document.createElement("div");
      menu.className = "aila-menu"; menu.setAttribute("role", "menu"); menu.setAttribute("aria-label", "Moduly");
      MODULES.forEach(function (m) {
        if (m.staff && !staff) return;
        var el = item(m.title, m.icon, m.on(location.pathname, location.hash));
        el.href = m.href;
        menu.appendChild(el);
      });
      document.body.appendChild(menu);
      place(logo);
    });
  }
  function place(logo) {
    var r = logo.getBoundingClientRect();
    menu.style.top = Math.round(r.bottom + 8) + "px";
    menu.style.left = Math.max(8, Math.min(Math.round(r.left), innerWidth - menu.offsetWidth - 8)) + "px";
    logo.setAttribute("aria-expanded", "true");
    var first = menu.querySelector("a"); if (first) first.focus({ preventScroll: true });
  }
  document.addEventListener("click", function (e) {
    var logo = e.target.closest && e.target.closest(".logo");
    if (logo) { e.preventDefault(); if (menuFor === logo) closeMenu(); else openMenu(logo); return; }
    if (menu && (!menu.contains(e.target) || e.target.closest(".aila-menu-item"))) closeMenu();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && menu) { var l = menuFor; closeMenu(); if (l) l.focus(); return; }
    var logo = e.target.closest && e.target.closest(".logo");
    if (logo && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); if (menuFor) closeMenu(); else openMenu(logo); return; }
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
