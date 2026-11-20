"""HTML stránky modulů Sklad a Objednávky ve sdíleném vzhledu DuklaLabs.

Kostra (header.top > .wrap > .brand + .tools, nav.tabs > .tabbar[data-ui],
main > .wrap > section.view) je stejná jako v Kroužku / AccessRequestu
(viz Shared/webui/ui.css, sekce APP SHELL). Obsah sekcí vykresluje JS
(static/sklad.js, static/objednavky.js) z JSON API téže služby.
"""
from html import escape

_LOGO = (
    '<div class="logo" role="img" aria-label="Logo DuklaLabs"><svg viewBox="0 0 192 192" aria-hidden="true">'
    '<defs><mask id="logoMask"><rect width="192" height="192" fill="#fff"/>'
    '<polygon points="24,0 69,0 40,74 76,74 14,188 27,110 4,110" fill="#000" stroke="#000" stroke-width="18"/>'
    '<circle cx="95" cy="96" r="38" fill="#000"/></mask></defs><g mask="url(#logoMask)">'
    '<path class="gear" d="M164.2 76.2 L186.6 79.9 L186.6 112.1 L164.2 115.8 L163.2 119 L162.1 122 L160.9 125.1 '
    'L159.5 128 L158 130.9 L171.2 149.3 L148.3 172.2 L129.9 159 L127 160.5 L124.1 161.9 L121 163.1 L118 164.2 '
    'L114.8 165.2 L111.1 187.6 L78.9 187.6 L75.2 165.2 L72 164.2 L69 163.1 L65.9 161.9 L63 160.5 L60.1 159 '
    'L41.7 172.2 L18.8 149.3 L32 130.9 L30.5 128 L29.1 125.1 L27.9 122 L26.8 119 L25.8 115.8 L3.4 112.1 '
    'L3.4 79.9 L25.8 76.2 L26.8 73 L27.9 70 L29.1 66.9 L30.5 64 L32 61.1 L18.8 42.7 L41.7 19.8 L60.1 33 '
    'L63 31.5 L65.9 30.1 L69 28.9 L72 27.8 L75.2 26.8 L78.9 4.4 L111.1 4.4 L114.8 26.8 L118 27.8 L121 28.9 '
    'L124.1 30.1 L127 31.5 L129.9 33 L148.3 19.8 L171.2 42.7 L158 61.1 L159.5 64 L160.9 66.9 L162.1 70 '
    'L163.2 73Z"/></g><polygon class="bolt" points="24,0 69,0 40,74 76,74 14,188 27,110 4,110"/></svg></div>'
)


def _icon(path: str) -> str:
    return (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
        f'stroke-linecap="round" stroke-linejoin="round">{path}</svg>'
    )


_OVERVIEW = '<rect x="3" y="3" width="7" height="9" rx="2"/><rect x="14" y="3" width="7" height="5" rx="2"/><rect x="14" y="12" width="7" height="9" rx="2"/><rect x="3" y="16" width="7" height="5" rx="2"/>'
_BOLT = '<path d="M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18v3h3l6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.4-.6-.6-2.4z"/>'
_CHIP = '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>'
_SPOOL = '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/><path d="M12 3v6M12 15v6"/>'
_FLASK = '<path d="M9 3h6M10 3v6L4.5 19a2 2 0 0 0 1.8 3h11.4a2 2 0 0 0 1.8-3L14 9V3"/>'
_BOX = '<path d="M21 8l-9-5-9 5v8l9 5 9-5z"/><path d="M3 8l9 5 9-5M12 13v8"/>'
_CHECK = '<path d="M9 11l3 3 8-8"/><path d="M20 12v6a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3h9"/>'
_CLOCK = '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>'
_EDIT = '<path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16z"/>'
_PLUS = '<circle cx="12" cy="12" r="9"/><path d="M12 8v8M8 12h8"/>'

SKLAD_TABS = [
    ("prehled", "Přehled", _OVERVIEW),
    ("spojovaci", "Spojovací materiál", _BOLT),
    ("soucastky", "Součástky", _CHIP),
    ("filamenty", "Filamenty", _SPOOL),
    ("chemie", "Chemie", _FLASK),
    ("ostatni", "Ostatní", _BOX),
]

ORDER_TABS = [
    ("prehled", "Přehled", _OVERVIEW),
    ("vyrizene", "Vyřízené", _CHECK),
    ("cekajici", "Čekající", _CLOCK),
    ("rozpracovane", "Rozpracované", _EDIT),
    ("nova", "Nová", _PLUS),
]


def _shell(*, prefix: str, title: str, subtitle: str, tools: str, tabs, body: str, scripts: list[str]) -> str:
    cur = ' aria-current="page"'
    tab_html = "".join(
        f'<a href="#{key}" data-view="{key}"{cur if i == 0 else ""}>'
        f"{_icon(icon)}<span>{escape(label)}</span></a>"
        for i, (key, label, icon) in enumerate(tabs)
    )
    script_html = "".join(f'<script src="{prefix}/static/{s}"></script>' for s in scripts)
    return f"""<!doctype html>
<html lang="cs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{escape(title)} DuklaLabs</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,700;12..96,800&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@500&display=swap">
<link rel="stylesheet" href="{prefix}/static/theme.css">
<link rel="stylesheet" href="{prefix}/static/ui.css">
<link rel="stylesheet" href="{prefix}/static/sklad.css">
<script src="{prefix}/static/theme-toggle.js"></script>
</head>
<body>
<header class="top">
  <div class="wrap">
    <div class="brand">
      {_LOGO}
      <div>
        <h1>{escape(title)} <span>DuklaLabs</span></h1>
        <p>{escape(subtitle)}</p>
      </div>
      <div class="tools">{tools}</div>
    </div>
  </div>
</header>
<nav class="tabs" aria-label="Sekce">
  <div class="wrap">
    <div class="tabbar" data-ui>
      <span class="ind"></span>
      {tab_html}
    </div>
  </div>
</nav>
<main>
  <div class="wrap">
{body}
  </div>
</main>
<div class="toast" id="toast" hidden></div>
<script>window.BASE_PATH = "{prefix}";</script>
<script src="{prefix}/static/ui.js"></script>
{script_html}
</body>
</html>
"""


def _section(key: str, heading: str, hint: str, inner: str = "", actions: str = "") -> str:
    act = f'<div class="actions">{actions}</div>' if actions else ""
    return (
        f'    <section id="v-{key}" class="view" data-v="{key}"{"" if key == "prehled" else " hidden"}>\n'
        f'      <div class="head"><h2>{escape(heading)}</h2>{act}<p>{escape(hint)}</p></div>\n'
        f"{inner}\n    </section>"
    )


def sklad_page(prefix: str) -> str:
    cats = [
        ("spojovaci", "Spojovací materiál", "Šrouby, matice, podložky a další spojovací materiál."),
        ("soucastky", "Součástky", "Elektronické a mechanické součástky."),
        ("filamenty", "Filamenty", "Filamenty a materiály pro 3D tisk."),
        ("chemie", "Chemie", "Lepidla, pájka, čističe a jiná chemie."),
        ("ostatni", "Ostatní", "Vše bez zařazení do kategorie."),
    ]
    prehled = _section(
        "prehled",
        "Přehled skladu",
        "Stav zásob a materiál, kterému dochází.",
        """      <div class="tiles" id="tiles"></div>
      <div class="grid2">
        <div class="panel"><h3>Pod minimem</h3><div id="lowList"></div></div>
        <div class="panel"><h3>Podle kategorií</h3><div id="catChips" class="chips"></div></div>
      </div>
      <div class="panel">
        <h3>Přidat materiál</h3>
        <form id="addForm" class="addform" autocomplete="off">
          <label class="f">Název<input type="text" id="fName" required maxlength="200" placeholder="Např. Šroub M3x10"></label>
          <label class="f">Kategorie<select id="fCategory"></select></label>
          <label class="f">Jednotka<input type="text" id="fUnit" list="unitList" placeholder="ks" maxlength="20"></label>
          <label class="f">Zásoba<input type="number" id="fStock" min="0" step="any" placeholder="0"></label>
          <label class="f">Minimum<input type="number" id="fMin" min="0" step="any" placeholder="0"></label>
          <datalist id="unitList"><option value="ks"><option value="m"><option value="g"><option value="kg"><option value="l"><option value="ml"><option value="role"></datalist>
          <div class="addform-actions"><button class="btn primary" type="submit" id="fSubmit">Přidat</button></div>
        </form>
        <div class="err-note" id="fError" hidden></div>
      </div>""",
    )
    sections = [prehled] + [
        _section(key, label, hint, f'      <div id="list-{key}"></div>') for key, label, hint in cats
    ]
    body = (
        '    <div class="err-note" id="loadError" hidden></div>\n'
        + "\n".join(sections)
    )
    tools = (
        f'<a class="btn" href="{prefix}/objednavky/" title="Přejít na objednávky">Objednávky</a>'
    )
    return _shell(
        prefix=prefix,
        title="Sklad",
        subtitle="Materiál a zásoby dílny",
        tools=tools,
        tabs=SKLAD_TABS,
        body=body,
        scripts=["sklad.js"],
    )


def objednavky_page(prefix: str) -> str:
    prehled = _section(
        "prehled",
        "Přehled objednávek",
        "Všechny objednávky a jejich stav.",
        """      <div class="tiles" id="tiles"></div>
      <div id="list-prehled" class="orders"></div>""",
    )
    simple = [
        ("vyrizene", "Vyřízené objednávky", "Objednávky, které už dorazily."),
        ("cekajici", "Čekající objednávky", "Vytvořené a odeslané objednávky, na které se čeká."),
        ("rozpracovane", "Rozpracované objednávky", "Koncepty, které ještě nebyly dokončeny."),
    ]
    sections = [prehled] + [
        _section(key, label, hint, f'      <div id="list-{key}" class="orders"></div>')
        for key, label, hint in simple
    ]
    sections.append(
        _section(
            "nova",
            "Nová objednávka",
            "Vyber materiál, zadej množství a přidej poznámku.",
            """      <form id="newForm" class="panel" autocomplete="off">
        <div class="newbar">
          <label class="f">Hledat materiál<input type="search" id="nSearch" placeholder="Název nebo kategorie"></label>
          <button class="btn" type="button" id="nFillLow">Doplnit pod minimum</button>
          <button class="btn" type="button" id="nClear">Vyprázdnit</button>
        </div>
        <div id="nList" class="matpick"></div>
        <label class="f">Poznámka<textarea id="nNote" placeholder="Dodavatel, termín, odkaz…" maxlength="1000"></textarea></label>
        <div class="err-note" id="nError" hidden></div>
        <div class="dlg-actions-inline">
          <span class="hint" id="nSummary"></span>
          <button class="btn" type="button" id="nDraft">Uložit jako rozpracovanou</button>
          <button class="btn primary" type="submit" id="nCreate">Vytvořit objednávku</button>
        </div>
      </form>""",
        )
    )
    body = '    <div class="err-note" id="loadError" hidden></div>\n' + "\n".join(sections)
    tools = f'<a class="btn" href="{prefix}/" title="Přejít na sklad">Sklad</a>'
    return _shell(
        prefix=prefix,
        title="Objednávky",
        subtitle="Objednávky materiálu do dílny",
        tools=tools,
        tabs=ORDER_TABS,
        body=body,
        scripts=["sklad.js", "objednavky.js"],
    )
