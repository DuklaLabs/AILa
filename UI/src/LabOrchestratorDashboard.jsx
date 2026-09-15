import React, { useEffect, useRef, useState } from "react";
import "./LabOrchestratorDashboard.css";


/**
 * Jednoduchá dashboardová stránka:
 * - horní černý header
 * - levý výsuvný panel s agenty
 * - střed: chat s "generálem"
 * - pravý panel: detail vybraného agenta (např. stroje)
 */

// Položky se `href` navigují na reálnou (cross-origin) subdoménu dané služby –
// SSO cookie (SESSION_COOKIE_DOMAIN=".aila.localhost") zajišťuje, že tam
// uživatel není znovu vyzván k přihlášení. Položky s `comingSoon` zatím nemají
// žádný backend/UI a zůstávají jen mock náhledem v pravém panelu.
const AGENTS = [
  { id: "orchestrator", name: "AILa", description: "Hlavní agent, který rozděluje práci." },
  {
    id: "assistant",
    name: "Generál",
    description: "Chat s asistentem – napojený na General (assistant.aila.localhost).",
  },
  {
    id: "access",
    name: "Vrátný",
    description: "Přístupy, RFID, registrace a otevřené hodiny.",
    href: "http://access.aila.localhost/admin",
  },
  {
    id: "rbac",
    name: "Oprávnění",
    description: "Správa rolí a oprávnění napříč systémem (RBAC konzole).",
    href: "http://access.aila.localhost/admin/rbac/",
  },
  {
    id: "projects",
    name: "Projekty",
    description: "Kanban, Gantt a sledování času na projektech.",
    href: "http://projects.aila.localhost/app/projects/",
  },
  { id: "machines", name: "Strojník", description: "Správa strojů a jejich stavů.", comingSoon: true },
  { id: "inventory", name: "Skladník", description: "Materiál, sklady, zásoby.", comingSoon: true },
  { id: "orders", name: "Nákupčík", description: "Objednávky materiálu.", comingSoon: true },
  { id: "analytics", name: "Analytik", description: "Přehledy, statistiky, reporty.", comingSoon: true },
];

const MOCK_MACHINES = [
  { id: 1, name: "FDM tiskárna 1", type: "FDM", status: "running", currentUser: "Jan Novák" },
  { id: 2, name: "FDM tiskárna 2", type: "FDM", status: "idle", currentUser: null },
  { id: 3, name: "Laser 1", type: "Laser", status: "error", currentUser: "Petr Svoboda" },
  { id: 4, name: "SLA tiskárna 1", type: "SLA", status: "running", currentUser: "Eva Dvořáková" },
];

const statusColor = (status) => {
  switch (status) {
    case "running":
      return "#00b894"; // zelená
    case "idle":
      return "#b2bec3"; // šedá
    case "error":
      return "#d63031"; // červená
    default:
      return "#636e72";
  }
};

// General je za Gateway na vlastní subdoméně (viz Gateway/Caddyfile), ne na
// stejném originu jako tenhle portál (aila.localhost) – proto plná URL a
// CORS na straně General/app/main.py.
const ASSISTANT_URL = "http://assistant.aila.localhost";

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

const WELCOME_MESSAGE = { from: "agent", text: "Zdravím, jsem Generál. Jak ti dnes můžu pomoct v laboratoři?" };
const LOGIN_URL = "http://access.aila.localhost/login";
const LOGOUT_URL = "http://access.aila.localhost/logout";

function userInitials(user) {
  const source = (user.full_name || user.username || "?").trim();
  const parts = source.split(/\s+/).filter(Boolean);
  const initials = parts.length >= 2 ? parts[0][0] + parts[1][0] : source.slice(0, 2);
  return initials.toUpperCase();
}

export default function LabOrchestratorDashboard() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState(AGENTS[0]);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [user, setUser] = useState(null);
  const [authError, setAuthError] = useState(null);
  const messagesEndRef = useRef(null);

  // Konverzace teď žije v general.chat_messages pod účtem (General/app/
  // history.py), ne v localStorage prohlížeče – přežije reload i přihlášení
  // z jiného zařízení. Bez platné dl_session cookie (sdílené SSO napříč
  // *.aila.localhost) General vrátí 401 a pošleme uživatele na login s
  // "next" zpátky sem.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const meResp = await fetch(`${ASSISTANT_URL}/general/me`, { credentials: "include" });
        if (meResp.status === 401) {
          window.location.href = `${LOGIN_URL}?next=${encodeURIComponent(window.location.href)}`;
          return;
        }
        if (!meResp.ok) throw new Error(`me: HTTP ${meResp.status}`);
        const meData = await meResp.json();

        const historyResp = await fetch(`${ASSISTANT_URL}/general/history`, { credentials: "include" });
        if (!historyResp.ok) throw new Error(`history: HTTP ${historyResp.status}`);
        const historyData = await historyResp.json();

        if (cancelled) return;
        setUser(meData);
        setMessages(historyData.length > 0 ? historyData : [WELCOME_MESSAGE]);
      } catch {
        if (!cancelled) setAuthError("Nepodařilo se spojit s Generálem (General/Gateway neběží?).");
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
      const resp = await fetch(`${ASSISTANT_URL}/general`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      if (resp.status === 401) {
        window.location.href = `${LOGIN_URL}?next=${encodeURIComponent(window.location.href)}`;
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

  // Dokud nevíme, jestli je uživatel přihlášený (nebo se to nepodařilo
  // zjistit), nerenderujeme chat s prázdnou/neúplnou historií.
  if (!user) {
    return (
      <div className="lab-shell">
        <div className="lab-auth-gate">{authError || "Ověřuji přihlášení…"}</div>
      </div>
    );
  }

  return (
    <div className="lab-shell">
      {/* Horní lišta */}
      <header className="lab-header">
        <div className="lab-header-left">
          <div className="lab-logo">LAB CONTROL</div>
          <div className="lab-header-title">Agentní orchestrátor laboratoře</div>
        </div>
        <div className="lab-header-right">
          <span className="lab-user-role">{user.full_name || user.username}</span>
          <div className="lab-user-avatar">{userInitials(user)}</div>
          <a className="lab-logout-link" href={LOGOUT_URL}>
            Odhlásit
          </a>
        </div>
      </header>

      {/* Hlavní layout */}
      <div className="lab-main">
        {/* Levý panel s agenty */}
        <div className={`lab-sidebar ${sidebarOpen ? "open" : "closed"}`}>
          <div className="lab-sidebar-toggle" onClick={() => setSidebarOpen(!sidebarOpen)}>
            {sidebarOpen ? "⟨" : "⟩"}
          </div>

          {sidebarOpen && (
            <>
              <div className="lab-sidebar-title">Agenti</div>
              <div className="lab-sidebar-list">
                {AGENTS.map((agent) => (
                  <button
                    key={agent.id}
                    className={
                      "lab-agent-item" +
                      (selectedAgent.id === agent.id ? " lab-agent-item-active" : "")
                    }
                    onClick={() =>
                      agent.href ? (window.location.href = agent.href) : setSelectedAgent(agent)
                    }
                  >
                    <div className="lab-agent-name">
                      {agent.name}
                      {agent.comingSoon && (
                        <span className="lab-agent-badge">Připravujeme</span>
                      )}
                    </div>
                    <div className="lab-agent-desc">{agent.description}</div>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Střední panel – chat s generálem */}
        <div className="lab-center">
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
                    <div className="lab-chat-label">
                      {m.from === "user" ? "Ty" : "Generál"}
                    </div>
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

        {/* Pravý panel – detail vybraného agenta */}
        <div className="lab-right">
          <div className="lab-panel lab-detail-panel">
            <div className="lab-panel-header">
              <div>
                <div className="lab-panel-title">Detail agenta</div>
                <div className="lab-panel-subtitle">{selectedAgent.name}</div>
              </div>
            </div>

            {/* Obsah podle typu agenta. `access`/`rbac`/`projects` sem nikdy
                nedorazí – jejich kliknutí naviguje pryč (mají `href`). */}
            {selectedAgent.id === "machines" ? (
              <MachinesOverview />
            ) : selectedAgent.id === "inventory" ? (
              <InventoryOverview />
            ) : (
              <GenericAgentOverview agent={selectedAgent} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/** Přehled strojů pro Machines Agenta */
function MachinesOverview() {
  return (
    <div className="lab-detail-content">
      <h3 className="lab-section-title">Stroje v laboratoři</h3>
      <div className="lab-machines-grid">
        {MOCK_MACHINES.map((m) => (
          <div key={m.id} className="lab-card">
            <div className="lab-card-header">
              <span className="lab-card-title">{m.name}</span>
              <span
                className="lab-card-status-dot"
                style={{ backgroundColor: statusColor(m.status) }}
              />
            </div>
            <div className="lab-card-body">
              <div className="lab-card-row">
                <span className="lab-card-label">Typ:</span>
                <span>{m.type}</span>
              </div>
              <div className="lab-card-row">
                <span className="lab-card-label">Stav:</span>
                <span>{m.status}</span>
              </div>
              <div className="lab-card-row">
                <span className="lab-card-label">Uživatel:</span>
                <span>{m.currentUser || "—"}</span>
              </div>
            </div>
            <div className="lab-card-footer">
              <button className="lab-card-btn">Detail</button>
              <button className="lab-card-btn lab-card-btn-outline">Lock</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Jednoduchý placeholder pro Inventory Agenta */
function InventoryOverview() {
  return (
    <div className="lab-detail-content">
      <h3 className="lab-section-title">Inventář (placeholder)</h3>
      <p>Sem přijde přehled materiálů, stav zásob a upozornění na potřebu doobjednat.</p>
      <ul className="lab-list">
        <li className="lab-list-item">
          <div>
            <div className="lab-list-title">PLA filament – červený</div>
            <div className="lab-list-subtitle">Zbývá: 3,2 kg (nad minimem)</div>
          </div>
        </li>
        <li className="lab-list-item">
          <div>
            <div className="lab-list-title">Pryskyřice – průhledná</div>
            <div className="lab-list-subtitle">Zbývá: 0,5 l (blízko minima)</div>
          </div>
          <button className="lab-list-btn lab-card-btn-outline">Navrhnout objednávku</button>
        </li>
      </ul>
    </div>
  );
}

/** Defaultní detail pro ostatní agenty */
function GenericAgentOverview({ agent }) {
  return (
    <div className="lab-detail-content">
      <h3 className="lab-section-title">{agent.name}</h3>
      <p>{agent.description}</p>
      <p style={{ marginTop: 8 }}>
        Tady může být speciální dashboard, grafy nebo nastavení pro tohohle agenta.
      </p>
    </div>
  );
}
