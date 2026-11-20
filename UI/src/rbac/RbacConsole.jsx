import { useCallback, useEffect, useRef, useState } from 'react'
import './rbac.css'
import { api } from './api'
import ConfirmProvider from './ConfirmDialog'
import { useTabIndicator } from './useAilaUI'
import PermissionsPanel from './panels/PermissionsPanel'
import RolesPanel from './panels/RolesPanel'
import UsersPanel from './panels/UsersPanel'
import AuditPanel from './panels/AuditPanel'

const icon = (children) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {children}
  </svg>
)

const TABS = [
  ['permissions', 'Oprávnění', icon(<><circle cx="8" cy="15" r="4" /><path d="M10.8 12.2 20 3m-4 4 3 3m-6-1 2 2" /></>)],
  ['roles', 'Role', icon(<path d="M12 3 4 6v6c0 4.5 3.2 7.8 8 9 4.8-1.2 8-4.5 8-9V6l-8-3Z" />)],
  ['users', 'Uživatelé', icon(<><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20c.6-3.6 3.3-5.5 6.5-5.5s5.9 1.9 6.5 5.5M16 4.8a3.5 3.5 0 0 1 0 6.4M18 14.8c2 .7 3.2 2.4 3.5 5.2" /></>)],
  ['audit', 'Audit', icon(<path d="M8 6h12M8 12h12M8 18h12M3.5 6h.01M3.5 12h.01M3.5 18h.01" />)],
]

const GEAR = "M164.2 76.2 L186.6 79.9 L186.6 112.1 L164.2 115.8 L163.2 119 L162.1 122 L160.9 125.1 L159.5 128 L158 130.9 L171.2 149.3 L148.3 172.2 L129.9 159 L127 160.5 L124.1 161.9 L121 163.1 L118 164.2 L114.8 165.2 L111.1 187.6 L78.9 187.6 L75.2 165.2 L72 164.2 L69 163.1 L65.9 161.9 L63 160.5 L60.1 159 L41.7 172.2 L18.8 149.3 L32 130.9 L30.5 128 L29.1 125.1 L27.9 122 L26.8 119 L25.8 115.8 L3.4 112.1 L3.4 79.9 L25.8 76.2 L26.8 73 L27.9 70 L29.1 66.9 L30.5 64 L32 61.1 L18.8 42.7 L41.7 19.8 L60.1 33 L63 31.5 L65.9 30.1 L69 28.9 L72 27.8 L75.2 26.8 L78.9 4.4 L111.1 4.4 L114.8 26.8 L118 27.8 L121 28.9 L124.1 30.1 L127 31.5 L129.9 33 L148.3 19.8 L171.2 42.7 L158 61.1 L159.5 64 L160.9 66.9 L162.1 70 L163.2 73Z"

function Logo() {
  return (
    <div className="logo" role="img" aria-label="Logo DuklaLabs">
      <svg viewBox="0 0 192 192" aria-hidden="true">
        <defs>
          <mask id="rbacLogoMask">
            <rect width="192" height="192" fill="#fff" />
            <polygon points="24,0 69,0 40,74 76,74 14,188 27,110 4,110" fill="#000" stroke="#000" strokeWidth="18" />
            <circle cx="95" cy="96" r="38" fill="#000" />
          </mask>
        </defs>
        <g mask="url(#rbacLogoMask)"><path className="gear" d={GEAR} /></g>
        <polygon className="bolt" points="24,0 69,0 40,74 76,74 14,188 27,110 4,110" />
      </svg>
    </div>
  )
}

function Header({ me }) {
  return (
    <header className="top">
      <div className="wrap">
        <div className="brand">
          <Logo />
          <div>
            <h1>Správa <span>oprávnění</span></h1>
            <p>Sdílené RBAC jádro (ailacore) · role, oprávnění a uživatelé</p>
          </div>
          {me && (
            <div className="tools">
              <span className="pill">Přihlášen: <strong>{me.user.username}</strong></span>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}

const HEADS = {
  permissions: { title: 'Oprávnění', hint: 'Katalog oprávnění ve tvaru schema.resource:action.', reload: true },
  roles: { title: 'Role', hint: 'Role a oprávnění, která jim jsou přidělena.', reload: true },
  users: { title: 'Uživatelé', hint: 'Vyhledej uživatele a spravuj jeho role a přímá oprávnění.' },
  audit: { title: 'Audit', hint: 'Záznam změn rolí a oprávnění.' },
}

function Tabs({ tab, setTab }) {
  const barRef = useRef(null)
  useTabIndicator(barRef, tab)
  return (
    <nav className="tabs" aria-label="Sekce">
      <div className="wrap">
        <div className="tabbar" data-ui ref={barRef}>
          <span className="ind" />
          {TABS.map(([id, label, svg]) => (
            <a key={id} href={`#${id}`} aria-current={tab === id ? 'page' : undefined}
               onClick={(e) => { e.preventDefault(); setTab(id) }}>
              {svg}<span>{label}</span>
            </a>
          ))}
        </div>
      </div>
    </nav>
  )
}

export default function RbacConsole() {
  const [me, setMe] = useState(null)
  const [tab, setTab] = useState('roles')
  const [permissions, setPermissions] = useState([])
  const [roles, setRoles] = useState([])
  const [error, setError] = useState('')
  const [ready, setReady] = useState(false)

  const reloadCatalog = useCallback(async () => {
    const [p, r] = await Promise.all([api.listPermissions(), api.listRoles()])
    setPermissions(p)
    setRoles(r)
  }, [])

  useEffect(() => {
    (async () => {
      try {
        const eff = await api.effective()
        setMe(eff)
        if (eff.can_manage) await reloadCatalog()
      } catch (err) {
        setError(err.message)
      } finally {
        setReady(true)
      }
    })()
  }, [reloadCatalog])

  if (!ready) {
    return (
      <>
        <Header />
        <main>
          <div className="wrap rbac" aria-busy="true">
            <div className="sk" style={{ height: 44, width: 320 }} />
            <div className="sk" style={{ height: 52 }} />
            <div className="sk" style={{ height: 160 }} />
          </div>
        </main>
      </>
    )
  }

  if (me && !me.can_manage) {
    return (
      <>
        <Header me={me} />
        <main className="rbac">
          <div className="wrap">
            <section className="view">
              <div className="head"><h2>Přístup odepřen</h2></div>
              <p className="err">
                <span>
                  Přihlášen jako <strong>{me.user.username}</strong> (role {me.user.role}), ale chybí
                  oprávnění <code>auth.role:manage</code>. Požádej administrátora.
                </span>
              </p>
            </section>
          </div>
        </main>
      </>
    )
  }

  const current = HEADS[tab]

  return (
    <ConfirmProvider>
      <Header me={me} />
      <Tabs tab={tab} setTab={setTab} />
      <main className="rbac">
        <div className="wrap">
          <section className="view" key={tab}>
            <div className="head">
              <h2>{current.title}</h2>
              {current.reload && (
                <div className="actions">
                  <button className="btn" onClick={() => reloadCatalog().catch((err) => setError(err.message))}>Obnovit</button>
                </div>
              )}
              <p>{current.hint}</p>
            </div>

            {error && (
              <div className="err" role="alert">
                <span>{error}</span>
                <button className="btn" onClick={() => setError('')} aria-label="Zavřít">×</button>
              </div>
            )}

            {tab === 'permissions' && (
              <PermissionsPanel permissions={permissions} reload={reloadCatalog} onError={setError} />
            )}
            {tab === 'roles' && (
              <RolesPanel roles={roles} permissions={permissions} reload={reloadCatalog} onError={setError} />
            )}
            {tab === 'users' && (
              <UsersPanel roles={roles} permissions={permissions} onError={setError} />
            )}
            {tab === 'audit' && <AuditPanel onError={setError} />}
          </section>
        </div>
      </main>
    </ConfirmProvider>
  )
}
