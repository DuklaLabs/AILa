import { useCallback, useEffect, useState } from 'react'
import './rbac.css'
import { api } from './api'
import PermissionsPanel from './panels/PermissionsPanel'
import RolesPanel from './panels/RolesPanel'
import UsersPanel from './panels/UsersPanel'
import AuditPanel from './panels/AuditPanel'

const TABS = [
  ['permissions', 'Oprávnění'],
  ['roles', 'Role'],
  ['users', 'Uživatelé'],
  ['audit', 'Audit'],
]

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

  if (!ready) return <div className="rbac"><p className="muted">Načítám…</p></div>

  if (me && !me.can_manage) {
    return (
      <div className="rbac">
        <h1>Role a oprávnění</h1>
        <p className="err">
          Přihlášen jako <strong>{me.user.username}</strong> (role {me.user.role}), ale chybí
          oprávnění <code>auth.role:manage</code>. Požádej administrátora.
        </p>
      </div>
    )
  }

  return (
    <div className="rbac">
      <h1>Role a oprávnění</h1>
      <p className="sub">
        Sdílené RBAC jádro (ailacore). {me && <>Přihlášen: <strong>{me.user.username}</strong></>}
      </p>

      {error && <div className="err">{error} <button className="btn" onClick={() => setError('')}>×</button></div>}

      <div className="rbac-tabs">
        {TABS.map(([id, label]) => (
          <button key={id} className={tab === id ? 'active' : ''} onClick={() => setTab(id)}>
            {label}
          </button>
        ))}
      </div>

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
  )
}
