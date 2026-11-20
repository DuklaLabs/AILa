import React, { useEffect, useRef, useState } from "react";
import "./LabOrchestratorDashboard.css";

// Portálový shell na kořeni domény (localhost) – navigační rozcestník pod
// jednotným přihlášením. Všechny moduly běží na stejném originu jako podcesty
// (viz Gateway/Caddyfile: /access, /projects, /assistant, /krouzek), takže
// cookie dl_session je prostě host-only a platí všude bez SESSION_COOKIE_DOMAIN
// ani CORS – fetch je same-origin.
const ACCESS_ORIGIN = "/access";
const PROJECTS_ORIGIN = "/projects";
// General je za Gateway na vlastní podcestě (/assistant, viz Gateway/Caddyfile),
// na stejném originu jako tenhle portál, takže čistý relativní fetch bez CORS.
// General je čistě JSON API bez vlastního UI, takže "Generál" dole není `href`
// ven, ale přepne portál do chat view (viz GeneralChat) – jinak by člověk
// skončil na holé JSON odpovědi.
const ASSISTANT_ORIGIN = "/assistant";
const PORTAL_URL = "/";
// Kroužek (port Claude-artefaktového prototypu "Kroužek DuklaLabs") – vlastní
// služba na 8009 (Krouzek/), vlastní podcesta přes Gateway/Caddyfile.
const KROUZEK_ORIGIN = "/krouzek";

// Hlavní nabídka – to, co člověk v laborce reálně potřebuje. `href` je
// hotový a funkční modul; `comingSoon` zatím nemá backend a tile jen
// vysvětlí, co tam jednou bude. Některé tily se liší podle role – dozor/
// admin/staff potřebuje u otevřených hodin administraci, ne přihlašovací
// formulář pro studenty.
function buildTiles(role) {
  const isStaff = role === "admin" || role === "staff";

  const tiles = [
    isStaff
      ? {
          id: "open-hours",
          title: "Administrace volných hodin",
          description: "Správa otevřených hodin, uvolňování z výuky a docházky.",
          icon: "🕒",
          href: `${ACCESS_ORIGIN}/admin#openHoursCard`,
        }
      : {
          id: "open-hours",
          title: "Přihlášení na volnou hodinu",
          description: "Zápis na otevřené hodiny DuklaLabs, uvolňování z výuky.",
          icon: "🕒",
          href: `${ACCESS_ORIGIN}/student-hours`,
        },
    {
      id: "assistant",
      title: "Chat s AIla",
      description: "Chat s AI asistentem laborky – sklad, objednávky, dotazy.",
      icon: "🤖",
      action: "chat",
    },
    {
      id: "projects",
      title: "Projekty",
      description: "Kanban, hierarchie úkolů, time tracking a finance.",
      icon: "📋",
      href: `${PROJECTS_ORIGIN}/app/projects/`,
    },
    {
      id: "krouzek",
      title: "Kroužek pro základky",
      description: "Docházka, kalendář, projekty a kontakty kroužku (ZŠ i SŠ).",
      icon: "🔧",
      href: `${KROUZEK_ORIGIN}/`,
    },
    {
      id: "machines",
      title: "Stroje",
      description: "Provozní stav strojů – kdo co používá, co je mimo provoz.",
      icon: "🖨️",
      href: `${ACCESS_ORIGIN}/machines`,
    },
    {
      id: "wiki",
      title: "DuklaWiki",
      description: "Návody, troubleshooting a znalostní báze laborky.",
      icon: "📖",
      comingSoon: true,
    },
    {
      id: "inventory",
      title: "Sklad",
      description: "Materiál, zásoby a stav skladu.",
      icon: "📦",
      href: "/sklad/",
    },
    {
      id: "orders",
      title: "Objednávky",
      description: "Objednávky materiálu a schvalování.",
      icon: "🛒",
      href: "/sklad/objednavky/",
    },
    {
      id: "teaching",
      title: "Moje Výuka",
      description: "Moje hodiny, podklady a výuka.",
      icon: "🎓",
      href: "/vyuka/",
    },
    {
      id: "thesis",
      title: "Ročníkové práce",
      description: "Zadání, vedoucí a postup ročníkových prací.",
      icon: "📝",
      href: "/rocnikove-prace/",
    },
    isStaff
      ? {
          id: "analytics",
          title: "Analytika",
          description: "Měsíční reporty o využívání laborky a log odeslaných e-mailů.",
          icon: "📊",
          href: `${ACCESS_ORIGIN}/admin/analytics`,
        }
      : {
          id: "analytics",
          title: "Analytika",
          description: "Přehledy a statistiky napříč moduly.",
          icon: "📊",
          comingSoon: true,
        },
  ];

  if (isStaff) {
    tiles.push({
      id: "users",
      title: "Uživatelé",
      description: "Role a oprávnění, souhlas s uvolňováním z výuky – na jednom místě.",
      icon: "👤",
      href: `${ACCESS_ORIGIN}/admin/users`,
    });
  }

  return tiles;
}

// Admin/staff navíc vidí odkaz na obecnou administraci (čekající registrace,
// rozesílání digestů, běhy agentů) – drženo mimo hlavní nabídku, ať zůstane
// přehledná i pro studenty.
const ADMIN_LINKS = [
  { id: "admin", title: "Administrace přístupů", href: `${ACCESS_ORIGIN}/admin` },
];

function useCurrentUser() {
  const [state, setState] = useState({ status: "loading", user: null });

  useEffect(() => {
    let cancelled = false;
    fetch(`${ACCESS_ORIGIN}/api/whoami`, { credentials: "include" })
      .then((res) => {
        if (cancelled) return;
        if (res.status === 401) {
          setState({ status: "anonymous", user: null });
          return;
        }
        if (!res.ok) throw new Error(`whoami ${res.status}`);
        return res.json().then((user) => setState({ status: "ok", user }));
      })
      .catch(() => {
        if (!cancelled) setState({ status: "error", user: null });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return state;
}

const LOGO = (
  <svg viewBox="0 0 192 192" aria-hidden="true">
    <defs>
      <mask id="logoMask">
        <rect width="192" height="192" fill="#fff" />
        <polygon points="24,0 69,0 40,74 76,74 14,188 27,110 4,110" fill="#000" stroke="#000" strokeWidth="18" />
        <circle cx="95" cy="96" r="38" fill="#000" />
      </mask>
    </defs>
    <g mask="url(#logoMask)">
      <path className="gear" d="M164.2 76.2 L186.6 79.9 L186.6 112.1 L164.2 115.8 L163.2 119 L162.1 122 L160.9 125.1 L159.5 128 L158 130.9 L171.2 149.3 L148.3 172.2 L129.9 159 L127 160.5 L124.1 161.9 L121 163.1 L118 164.2 L114.8 165.2 L111.1 187.6 L78.9 187.6 L75.2 165.2 L72 164.2 L69 163.1 L65.9 161.9 L63 160.5 L60.1 159 L41.7 172.2 L18.8 149.3 L32 130.9 L30.5 128 L29.1 125.1 L27.9 122 L26.8 119 L25.8 115.8 L3.4 112.1 L3.4 79.9 L25.8 76.2 L26.8 73 L27.9 70 L29.1 66.9 L30.5 64 L32 61.1 L18.8 42.7 L41.7 19.8 L60.1 33 L63 31.5 L65.9 30.1 L69 28.9 L72 27.8 L75.2 26.8 L78.9 4.4 L111.1 4.4 L114.8 26.8 L118 27.8 L121 28.9 L124.1 30.1 L127 31.5 L129.9 33 L148.3 19.8 L171.2 42.7 L158 61.1 L159.5 64 L160.9 66.9 L162.1 70 L163.2 73Z" />
    </g>
    <polygon className="bolt" points="24,0 69,0 40,74 76,74 14,188 27,110 4,110" />
  </svg>
);

const HEADS = {
  home: { title: "Rozcestník", hint: "Vyber modul laborky." },
  chat: { title: "Chat s AIla", hint: "Chat s hlavním AI asistentem laborky." },
  wiki: { title: "DuklaWiki", hint: "Návody, troubleshooting a znalostní báze laborky." },
};

// Pohledy portálu žijí v hashi (#chat, #wiki) – odkazy z menu u loga
// (Shared/webui/theme-toggle.js) tak otevřou rovnou správný pohled. Mezi
// moduly se přepíná právě tím menu, portál nemá vlastní navigační záložky.
const VIEW_IDS = Object.keys(HEADS);
const viewFromHash = () => {
  const id = window.location.hash.replace(/^#/, "");
  return VIEW_IDS.includes(id) ? id : "home";
};

export default function LabOrchestratorDashboard() {
  const { status, user } = useCurrentUser();
  const [view, setViewState] = useState(viewFromHash); // "home" | "chat" | "wiki"
  const setView = (id) => {
    window.history.replaceState(null, "", id === "home" ? window.location.pathname : `#${id}`);
    setViewState(id);
  };
  useEffect(() => {
    const onHash = () => setViewState(viewFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const head = status === "ok" ? HEADS[view] : null;

  return (
    <>
      <header className="top">
        <div className="wrap">
          <div className="brand">
            <div className="logo" role="img" aria-label="Logo DuklaLabs">{LOGO}</div>
            <div>
              <h1>
                AILa <span>DuklaLabs</span>
              </h1>
              <p>Portál laboratoře</p>
            </div>
            <div className="tools">
              {status === "ok" && user && (
                <>
                  <span className="portal-user">
                    {user.full_name || user.username}
                    <span className="nick">{user.role}</span>
                  </span>
                  <a
                    className="btn sm"
                    href={`${ACCESS_ORIGIN}/logout?next=${encodeURIComponent(PORTAL_URL)}`}
                  >
                    Odhlásit
                  </a>
                </>
              )}
              {status === "anonymous" && (
                <a
                  className="btn primary"
                  href={`${ACCESS_ORIGIN}/login?next=${encodeURIComponent(PORTAL_URL)}`}
                >
                  Přihlásit se
                </a>
              )}
            </div>
          </div>
        </div>
      </header>

      <main>
        <div className="wrap">
          <section className="view" key={status === "ok" ? view : status}>
            {head && (
              <div className="head">
                <h2>{head.title}</h2>
                <p>{head.hint}</p>
              </div>
            )}

            {status === "loading" && <p className="portal-hint">Zjišťuji přihlášení…</p>}

            {status === "error" && (
              <p className="portal-hint portal-hint-error">
                Nepodařilo se ověřit přihlášení ({ACCESS_ORIGIN} neodpovídá). Zkus to prosím znovu.
              </p>
            )}

            {status === "anonymous" && (
              <div className="panel portal-login-card">
                <h2>Přihlas se</h2>
                <p>
                  Jedno přihlášení platí pro všechny moduly DuklaLabs – docházku,
                  projekty i sklad.
                </p>
                <a
                  className="btn primary"
                  href={`${ACCESS_ORIGIN}/login?next=${encodeURIComponent(PORTAL_URL)}`}
                >
                  Přihlásit se
                </a>
              </div>
            )}

            {status === "ok" && view === "chat" && <GeneralChat />}

            {status === "ok" && view === "wiki" && (
              <div className="empty">
                <b>Připravujeme</b>
                <span>{HEADS[view].title} zatím nemá backend – tady se objeví, až bude hotový.</span>
              </div>
            )}

            {status === "ok" && view === "home" && (
              <>
                <div className="portal-grid">
                  {buildTiles(user?.role).map((tile) => (
                    <PortalTile key={tile.id} tile={tile} onAction={setView} />
                  ))}
                </div>

                {user?.role === "admin" || user?.role === "staff" ? (
                  <div className="portal-admin-row">
                    {ADMIN_LINKS.map((link) => (
                      <a key={link.id} className="portal-admin-link" href={link.href}>
                        {link.title}
                      </a>
                    ))}
                  </div>
                ) : null}
              </>
            )}
          </section>
        </div>
      </main>
    </>
  );
}

function PortalTile({ tile, onAction }) {
  const body = (
    <>
      <div className="portal-tile-icon">{tile.icon}</div>
      <div className="portal-tile-title">
        {tile.title}
        {tile.comingSoon && <span className="pill s-x">Připravujeme</span>}
      </div>
      <div className="portal-tile-desc">{tile.description}</div>
    </>
  );

  if (tile.comingSoon) {
    return <div className="card portal-tile portal-tile-disabled">{body}</div>;
  }
  if (tile.action) {
    return (
      <button
        type="button"
        className="card portal-tile portal-tile-button"
        onClick={() => onAction(tile.action)}
      >
        {body}
      </button>
    );
  }
  return (
    <a className="card portal-tile" href={tile.href}>
      {body}
    </a>
  );
}

// ----------------------------------------------------------------------
// Chat s Generálem – General je čistě JSON API (General/app/main.py), tahle
// komponenta je jeho jediné UI. Konverzace žije v general.chat_messages pod
// účtem (General/app/history.py), ne v localStorage – přežije reload i
// přihlášení z jiného zařízení.
// ----------------------------------------------------------------------

const WELCOME_MESSAGE = { from: "agent", text: "Zdravím, jsem AIla. Jak ti dnes můžu pomoct v laboratoři?" };

// Odpověď z POST /general je {reply, data?} – "reply" je vždy volný text
// (Generál umí i běžný pokec, ne jen CHECK_STOCK/CREATE_ORDER), "data" jsou
// data vrácená skladníkem/nákupčím, když šlo o jednu z těch dvou akcí.
// Backend by v "reply" měl vracet vždy čistý text, ale pro jistotu (např.
// když model omylem zdvojí JSON obal) zkusíme "reply" ještě jednou
// rozbalit, pokud sám vypadá jako {"reply": "..."} JSON objekt.
function unwrapReplyText(reply) {
  if (typeof reply !== "string") return reply;
  const trimmed = reply.trim();
  if (!trimmed.startsWith("{")) return reply;
  try {
    const parsed = JSON.parse(trimmed);
    if (parsed && typeof parsed === "object" && typeof parsed.reply === "string") {
      return unwrapReplyText(parsed.reply);
    }
  } catch {
    // není to JSON, necháme text jak je
  }
  return reply;
}

function formatAssistantReply(data) {
  if (!data || typeof data !== "object") return String(data);
  const parts = [];
  if (data.reply) parts.push(unwrapReplyText(data.reply));
  // pending_email nese i plný seznam příjemců (general/app/orchestrator.py)
  // – ten by tu jen zabral místo syrovým JSON dumpem, "reply" už obsahuje
  // předmět/text/počet příjemců čitelně naformátované.
  if (data.data !== undefined && !(data.data && data.data.pending_email)) {
    parts.push(JSON.stringify(data.data, null, 2));
  }
  return parts.length ? parts.join("\n\n") : JSON.stringify(data, null, 2);
}

function GeneralChat() {
  const [messages, setMessages] = useState([WELCOME_MESSAGE]);
  const [loadError, setLoadError] = useState(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef(null);

  // Přihlášení už ověřil portál (LabOrchestratorDashboard), takže tu jen
  // natáhneme historii. 401 tu teoreticky nemůže nastat (stejná dl_session
  // cookie), ale fetch sem tam může i selhat na nedostupném Gateway/General.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${ASSISTANT_ORIGIN}/general/history`, { credentials: "include" });
        if (res.status === 401) {
          window.location.href = `${ACCESS_ORIGIN}/login?next=${encodeURIComponent(PORTAL_URL)}`;
          return;
        }
        if (!res.ok) throw new Error(`history: HTTP ${res.status}`);
        const history = await res.json();
        if (!cancelled) setMessages(history.length > 0 ? history : [WELCOME_MESSAGE]);
      } catch {
        if (!cancelled) setLoadError("Nepodařilo se spojit s AIla (General/Gateway neběží?).");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Auto-scroll na poslední zprávu – ať uživatel nemusí ručně scrollovat
  // dolů po každé nové odpovědi Generála.
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async () => {
    const prompt = input.trim();
    if (!prompt || sending) return;
    setMessages((prev) => [...prev, { from: "user", text: prompt }]);
    setInput("");
    setSending(true);
    try {
      const resp = await fetch(`${ASSISTANT_ORIGIN}/general`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      if (resp.status === 401) {
        window.location.href = `${ACCESS_ORIGIN}/login?next=${encodeURIComponent(PORTAL_URL)}`;
        return;
      }
      const data = await resp.json();
      // Uloženo stejně jako to, co vrátí /general/history (text + volitelná
      // data), ať se historická a čerstvá zpráva renderují identicky.
      setMessages((prev) => [
        ...prev,
        { from: "agent", text: unwrapReplyText(data.reply) ?? String(data), data: data.data },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { from: "agent", text: "⚠️ Nepodařilo se spojit s AIla (General/Gateway neběží?)." },
      ]);
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="portal-chat">
      <div className="panel lab-chat-panel">
        <div className="lab-panel-header">
          <div>
            <div className="lab-panel-title">Konverzace s AIla</div>
            <div className="lab-panel-subtitle">
              Hlavní orchestrátor – přijímá příkazy a řídí ostatní agenty.
            </div>
          </div>
          <span className="pill s-p">Online</span>
        </div>

        {loadError && <p className="portal-hint portal-hint-error">{loadError}</p>}

        <div className="lab-chat-messages">
          {messages.map((m, idx) => (
            <div
              key={idx}
              className={
                "lab-chat-message " +
                (m.from === "user" ? "lab-chat-message-user" : "lab-chat-message-agent")
              }
            >
              <div className="lab-chat-bubble">
                <div className="lab-chat-label">{m.from === "user" ? "Ty" : "AIla"}</div>
                <div>{m.from === "user" ? m.text : formatAssistantReply({ reply: m.text, data: m.data })}</div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        <div className="lab-chat-input-row">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Zeptej se generála – např. „Zkontroluj sklad“ nebo „Objednej chybějící materiál“..."
            className="lab-chat-textarea"
            disabled={sending}
          />
          <button
            className="btn primary lab-chat-send-btn"
            onClick={handleSend}
            disabled={!input.trim() || sending}
          >
            {sending ? "Posílám…" : "Odeslat"}
          </button>
        </div>
      </div>
    </div>
  );
}
