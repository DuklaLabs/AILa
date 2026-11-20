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
  /* "← Rozcestník": slim bar at the very top of every page except the hub itself (portal at "/"). */
  function mountHome() {
    var p = location.pathname;
    if (p === "/" || p === "/index.html" || document.querySelector(".aila-home")) return;
    var bar = document.createElement("div");
    bar.className = "aila-home";
    bar.innerHTML = '<a class="btn sm" href="/" title="Zpět na rozcestník"><span aria-hidden="true">←</span> Rozcestník</a>';
    document.body.insertBefore(bar, document.body.firstChild);
  }
  function mount() {
    mountHome();
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
