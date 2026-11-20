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
      <div className="rbac" aria-busy="true">
        <div className="sk" style={{ height: 44, width: 320 }} />
        <div className="sk" style={{ height: 52 }} />
        <div className="sk" style={{ height: 160 }} />
      </div>
    )
  }

  if (me && !me.can_manage) {
    return (
      <div className="rbac">
        <h1>Role a oprávnění</h1>
        <p className="err">
          <span>
            Přihlášen jako <strong>{me.user.username}</strong> (role {me.user.role}), ale chybí
            oprávnění <code>auth.role:manage</code>. Požádej administrátora.
          </span>
        </p>
      </div>
    )
  }

  return (
    <ConfirmProvider>
      <div className="rbac">
        <h1>Role a oprávnění</h1>
        <p className="sub">
          Sdílené RBAC jádro (ailacore). {me && <>Přihlášen: <strong>{me.user.username}</strong></>}
        </p>

        {error && (
          <div className="err" role="alert">
            <span>{error}</span>
            <button className="btn" onClick={() => setError('')} aria-label="Zavřít">×</button>
          </div>
        )}

        <Tabs tab={tab} setTab={setTab} />

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
      </div>
    </ConfirmProvider>
  )
}
