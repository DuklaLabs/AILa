import React, { useState } from "react";
import "./LabOrchestratorDashboard.css";


/**
 * Jednoduchá dashboardová stránka:
 * - horní černý header
 * - levý výsuvný panel s agenty
 * - střed: chat s "generálem"
 * - pravý panel: detail vybraného agenta (např. stroje)
 */

const AGENTS = [
  { id: "orchestrator", name: "AILa", description: "Hlavní agent, který rozděluje práci." },
  { id: "access", name: "Vrátný", description: "Řeší přístupy, RFID, sessions." },
  { id: "machines", name: "Strojník", description: "Správa strojů a jejich stavů." },
  { id: "inventory", name: "Skladník", description: "Materiál, sklady, zásoby." },
  { id: "orders", name: "Nákupčík", description: "Objednávky materiálu." },
  { id: "analytics", name: "Analytik", description: "Přehledy, statistiky, reporty." },
];

const MOCK_MACHINES = [
  { id: 1, name: "FDM tiskárna 1", type: "FDM", status: "running", currentUser: "Jan Novák" },
  { id: 2, name: "FDM tiskárna 2", type: "FDM", status: "idle", currentUser: null },
  { id: 3, name: "Laser 1", type: "Laser", status: "error", currentUser: "Petr Svoboda" },
  { id: 4, name: "SLA tiskárna 1", type: "SLA", status: "running", currentUser: "Eva Dvořáková" },
];

const MOCK_USERS_IN_LAB = [
  { id: 1, name: "Jan Novák", since: "10:12" },
  { id: 2, name: "Eva Dvořáková", since: "10:45" },
  { id: 3, name: "Petr Svoboda", since: "11:05" },
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
  const [isSending, setIsSending] = useState(false);

  const handleSend = async () => {
    if (!input.trim()) return;
    const userMessage = { from: "user", text: input.trim() };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsSending(true);

    try {
      // Volání backendu – přizpůsob si URL podle toho, kde poběží agent
      const resp = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage.text }),
      });

      let replyText = "Něco se pokazilo na straně generála.";
      if (resp.ok) {
        const data = await resp.json();
        replyText = data.reply || replyText;
      }

      const agentMessage = { from: "agent", text: replyText };
      setMessages((prev) => [...prev, agentMessage]);
    } catch (err) {
      const agentMessage = {
        from: "agent",
        text: "Nepodařilo se kontaktovat backend agenta. Zkontroluj server.",
      };
      setMessages((prev) => [...prev, agentMessage]);
    } finally {
      setIsSending(false);
    }
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
                    onClick={() => setSelectedAgent(agent)}
                  >
                    <div className="lab-agent-name">{agent.name}</div>
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
                disabled={isSending || !input.trim()}
              >
                {isSending ? "Odesílám..." : "Odeslat"}
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

            {/* Obsah podle typu agenta */}
            {selectedAgent.id === "machines" ? (
              <MachinesOverview />
            ) : selectedAgent.id === "access" ? (
              <AccessOverview />
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

/** Přehled lidí v laboratoři pro Access Agenta */
function AccessOverview() {
  return (
    <div className="lab-detail-content">
      <h3 className="lab-section-title">Aktuálně v laboratoři</h3>
      <ul className="lab-list">
        {MOCK_USERS_IN_LAB.map((u) => (
          <li key={u.id} className="lab-list-item">
            <div>
              <div className="lab-list-title">{u.name}</div>
              <div className="lab-list-subtitle">Od {u.since}</div>
            </div>
            <button className="lab-list-btn">Detail uživatele</button>
          </li>
        ))}
      </ul>
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
