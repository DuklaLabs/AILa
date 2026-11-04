import React, { useEffect, useState } from "react";
import "./LabOrchestratorDashboard.css";

// Portálový shell na kořeni domény (aila.localhost) – navigační rozcestník
// pod jednotným přihlášením. Session cookie dl_session je společná pro
// všechny *.aila.localhost služby (SESSION_COOKIE_DOMAIN), takže se sem
// člověk přihlásí jednou (na access.aila.localhost/login) a dál už jen
// naviguje. Stav přihlášení si portál čte přes CORS fetch na
// access-request-server (PORTAL_ORIGINS v jeho konfiguraci).
const ACCESS_ORIGIN = "http://access.aila.localhost";
const PROJECTS_ORIGIN = "http://projects.aila.localhost";
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

        {status === "ok" && (
          <>
            <div className="portal-grid">
              {buildTiles(user?.role).map((tile) => (
                <PortalTile key={tile.id} tile={tile} />
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

function PortalTile({ tile }) {
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
  return (
    <a className="portal-tile" href={tile.href}>
      {body}
    </a>
  );
}
