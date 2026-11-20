/* DuklaLabs UI helpers — companion to ui.css (single source: Shared/webui/).
   Keeps the sliding highlight under the active item of a switch / tab bar.
     AilaUI.knob(switchEl)   – moves .knob under the button[aria-pressed="true"]
     AilaUI.tabs(barEl)      – moves .ind under the a[aria-current] tab
     AilaUI.auto()           – wires every .grp[data-ui] and .tabbar[data-ui] on the page:
                               click on a switch button sets aria-pressed and fires "ui:change"
                               (detail = button.dataset.value || button.dataset.g). */
(function (w) {
  function place(el, item) {
    if (!el || !item) return;
    el.style.width = item.offsetWidth + "px";
    el.style.transform = "translateX(" + item.offsetLeft + "px)";
  }
  function knob(sw) { place(sw.querySelector(".knob"), sw.querySelector('button[aria-pressed="true"]')); }
  function tabs(bar) { place(bar.querySelector(".ind"), bar.querySelector("a[aria-current]")); }
  function refresh() {
    document.querySelectorAll(".grp[data-ui]").forEach(knob);
    document.querySelectorAll(".tabbar[data-ui]").forEach(tabs);
  }
  function auto() {
    document.querySelectorAll(".grp[data-ui]").forEach(function (sw) {
      sw.addEventListener("click", function (e) {
        var b = e.target.closest("button"); if (!b || !sw.contains(b)) return;
        sw.querySelectorAll("button").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
        knob(sw);
        sw.dispatchEvent(new CustomEvent("ui:change", { bubbles: true, detail: b.dataset.value || b.dataset.g }));
      });
    });
    refresh();
    addEventListener("resize", refresh);
    if (document.fonts) document.fonts.ready.then(refresh);
  }
  w.AilaUI = { knob: knob, tabs: tabs, auto: auto, refresh: refresh };
})(window);
