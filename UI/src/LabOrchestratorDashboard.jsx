import React, { useState } from "react";
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
    description: "Chat s asistentem – zatím ukázkový, čeká na napojení na backend (General).",
    comingSoon: true,
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

export default function LabOrchestratorDashboard() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState(AGENTS[0]);
  const [messages, setMessages] = useState([
    { from: "agent", text: "Zdravím, jsem Generál. Jak ti dnes můžu pomoct v laboratoři?" },
  ]);
  const [input, setInput] = useState("");

  // Chat zatím nemá skutečný backend (General je jen nenasazený prototyp bez
  // /api/chat) – místo síťového volání jen zobrazíme, že asistent zatím čeká
  // na napojení. Až bude General rozšířený o tool-calling, přijde sem znovu
  // fetch na `assistant.aila.localhost`.
  const handleSend = () => {
    if (!input.trim()) return;
    const userMessage = { from: "user", text: input.trim() };
    const agentMessage = {
      from: "agent",
      text: "Asistent zatím není napojen na backend – bude dostupný v příští fázi.",
    };
    setMessages((prev) => [...prev, userMessage, agentMessage]);
    setInput("");
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="lab-shell">
      {/* Horní lišta */}
      <header className="lab-header">
        <div className="lab-header-left">
          <div className="lab-logo">LAB CONTROL</div>
          <div className="lab-header-title">Agentní orchestrátor laboratoře</div>
        </div>
        <div className="lab-header-right">
          <span className="lab-user-role">Admin</span>
          <div className="lab-user-avatar">JD</div>
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
                    <div>{m.text}</div>
                  </div>
                </div>
              ))}
            </div>

            <div className="lab-chat-input-row">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Zeptej se generála – např. „Kdo je aktuálně v laborce?“ nebo „Povol FDM tiskárnu 1 pro Jana Nováka“..."
                className="lab-chat-textarea"
              />
              <button
                className="lab-chat-send-btn"
                onClick={handleSend}
                disabled={!input.trim()}
              >
                Odeslat
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
