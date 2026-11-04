import React, { useEffect, useRef, useState } from "react";
import "./LabOrchestratorDashboard.css";

// Portálový shell na kořeni domény (aila.localhost) – navigační rozcestník
// pod jednotným přihlášením. Session cookie dl_session je společná pro
// všechny *.aila.localhost služby (SESSION_COOKIE_DOMAIN), takže se sem
// člověk přihlásí jednou (na access.aila.localhost/login) a dál už jen
// naviguje. Stav přihlášení si portál čte přes CORS fetch na
// access-request-server (PORTAL_ORIGINS v jeho konfiguraci).
const ACCESS_ORIGIN = "http://access.aila.localhost";
const PROJECTS_ORIGIN = "http://projects.aila.localhost";
// General je za Gateway na vlastní subdoméně (viz Gateway/Caddyfile), ne na
// stejném originu jako tenhle portál – proto plná URL a CORS na straně
// General/app/main.py. General je čistě JSON API bez vlastního UI, takže
// "Generál" dole není `href` ven, ale přepne portál do chat view (viz
// GeneralChat) – jinak by člověk skončil na holé JSON odpovědi.
const ASSISTANT_ORIGIN = "http://assistant.aila.localhost";
const PORTAL_URL = "http://aila.localhost/";

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
      title: "Generál",
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
      comingSoon: true,
    },
    {
      id: "orders",
      title: "Objednávky",
      description: "Objednávky materiálu a schvalování.",
      icon: "🛒",
      comingSoon: true,
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

export default function LabOrchestratorDashboard() {
  const { status, user } = useCurrentUser();
  const [view, setView] = useState("home"); // "home" | "chat"

  return (
    <div className="portal-shell">
      <header className="portal-header">
        <div className="portal-brand">
          <span className="portal-logo">AILa</span>
          <span className="portal-subtitle">DuklaLabs – portál</span>
        </div>
        <div className="portal-account">
          {status === "ok" && user && (
            <>
              <span className="portal-user">
                {user.full_name || user.username}
                <span className="portal-role">{user.role}</span>
              </span>
              <a
                className="portal-btn portal-btn-ghost"
                href={`${ACCESS_ORIGIN}/logout?next=${encodeURIComponent(PORTAL_URL)}`}
              >
                Odhlásit
              </a>
            </>
          )}
          {status === "anonymous" && (
            <a
              className="portal-btn portal-btn-primary"
              href={`${ACCESS_ORIGIN}/login?next=${encodeURIComponent(PORTAL_URL)}`}
            >
              Přihlásit se
            </a>
          )}
        </div>
      </header>

      <main className="portal-main">
        {status === "loading" && <p className="portal-hint">Zjišťuji přihlášení…</p>}

        {status === "error" && (
          <p className="portal-hint portal-hint-error">
            Nepodařilo se ověřit přihlášení ({ACCESS_ORIGIN} neodpovídá). Zkus to prosím znovu.
          </p>
        )}

        {status === "anonymous" && (
          <div className="portal-login-card">
            <h1>Přihlas se</h1>
            <p>
              Jedno přihlášení platí pro všechny moduly DuklaLabs – docházku,
              projekty i sklad.
            </p>
            <a
              className="portal-btn portal-btn-primary"
              href={`${ACCESS_ORIGIN}/login?next=${encodeURIComponent(PORTAL_URL)}`}
            >
              Přihlásit se
            </a>
          </div>
        )}

        {status === "ok" && view === "chat" && (
          <GeneralChat onBack={() => setView("home")} />
        )}

        {status === "ok" && view === "home" && (
          <>
            <div className="portal-grid">
              {buildTiles(user?.role).map((tile) => (
                <PortalTile key={tile.id} tile={tile} onOpenChat={() => setView("chat")} />
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
      </main>
    </div>
  );
}

function PortalTile({ tile, onOpenChat }) {
  const body = (
    <>
      <div className="portal-tile-icon">{tile.icon}</div>
      <div className="portal-tile-title">
        {tile.title}
        {tile.comingSoon && <span className="portal-tile-badge">Připravujeme</span>}
      </div>
      <div className="portal-tile-desc">{tile.description}</div>
    </>
  );

  if (tile.comingSoon) {
    return <div className="portal-tile portal-tile-disabled">{body}</div>;
  }
  if (tile.action === "chat") {
    return (
      <button type="button" className="portal-tile portal-tile-button" onClick={onOpenChat}>
        {body}
      </button>
    );
  }
  return (
    <a className="portal-tile" href={tile.href}>
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

const WELCOME_MESSAGE = { from: "agent", text: "Zdravím, jsem Generál. Jak ti dnes můžu pomoct v laboratoři?" };

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

function GeneralChat({ onBack }) {
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
        if (!cancelled) setLoadError("Nepodařilo se spojit s Generálem (General/Gateway neběží?).");
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
        { from: "agent", text: "⚠️ Nepodařilo se spojit s Generálem (General/Gateway neběží?)." },
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
      <button type="button" className="portal-btn portal-btn-ghost portal-back-btn" onClick={onBack}>
        ← Zpět na rozcestník
      </button>
      <div className="lab-panel lab-chat-panel">
        <div className="lab-panel-header">
          <div>
            <div className="lab-panel-title">Konverzace s Generálem</div>
            <div className="lab-panel-subtitle">
              Hlavní orchestrátor – přijímá příkazy a řídí ostatní agenty.
            </div>
          </div>
          <span className="lab-status-pill">Online</span>
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
                <div className="lab-chat-label">{m.from === "user" ? "Ty" : "Generál"}</div>
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
            className="lab-chat-send-btn"
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
