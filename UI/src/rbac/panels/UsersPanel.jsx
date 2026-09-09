import { useEffect, useState } from 'react'
import { api } from '../api'

function UserCard({ user, roles, permissions, onError, refresh }) {
  const [primary, setPrimary] = useState(user.primary_role)
  const [secondary, setSecondary] = useState(new Set(user.secondary_roles))
  const [grants, setGrants] = useState(new Set(user.direct_permissions))
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setPrimary(user.primary_role)
    setSecondary(new Set(user.secondary_roles))
    setGrants(new Set(user.direct_permissions))
  }, [user])

  function toggle(setObj, setFn, value) {
    const next = new Set(setObj)
    next.has(value) ? next.delete(value) : next.add(value)
    setFn(next)
  }

  async function saveRoles() {
    setBusy(true)
    try {
      await api.setUserRoles(user.id, primary, [...secondary].filter((r) => r !== primary))
      await refresh()
    } catch (err) { onError(err.message) } finally { setBusy(false) }
  }

  async function saveGrants() {
    setBusy(true)
    try {
      await api.setUserPermissions(user.id, [...grants])
      await refresh()
    } catch (err) { onError(err.message) } finally { setBusy(false) }
  }

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h3>{user.full_name || user.username} <span className="muted">#{user.id} · {user.username}</span></h3>
      </div>

      <div className="row" style={{ marginBottom: '0.5rem' }}>
        <label>Primární role:&nbsp;
          <select value={primary} onChange={(e) => setPrimary(e.target.value)}>
            {roles.map((r) => <option key={r.name} value={r.name}>{r.name}</option>)}
          </select>
        </label>
      </div>

      <div style={{ marginBottom: '0.4rem' }}>
        <div className="muted">Sekundární role</div>
        <div className="row">
          {roles.filter((r) => r.name !== primary).map((r) => (
            <label key={r.name} className="chip">
              <input type="checkbox" checked={secondary.has(r.name)}
                     onChange={() => toggle(secondary, setSecondary, r.name)} /> {r.name}
            </label>
          ))}
        </div>
      </div>
      <button className="btn primary" disabled={busy} onClick={saveRoles}>Uložit role</button>

      <details style={{ marginTop: '0.75rem' }}>
        <summary>Přímé granty ({grants.size})</summary>
        <div className="perm-grid" style={{ marginTop: '0.4rem' }}>
          {permissions.filter((p) => p.name !== '*').map((p) => (
            <label key={p.name} title={p.description || ''}>
              <input type="checkbox" checked={grants.has(p.name)}
                     onChange={() => toggle(grants, setGrants, p.name)} />
              <code>{p.name}</code>
            </label>
          ))}
        </div>
        <button className="btn primary" disabled={busy} onClick={saveGrants}
                style={{ marginTop: '0.4rem' }}>Uložit granty</button>
      </details>
    </div>
  )
}

export default function UsersPanel({ roles, permissions, onError }) {
  const [q, setQ] = useState('')
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(false)

  async function search() {
    setLoading(true)
    try { setUsers(await api.listUsers(q)) }
    catch (err) { onError(err.message) } finally { setLoading(false) }
  }

  useEffect(() => { search() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div>
      <form className="card row" onSubmit={(e) => { e.preventDefault(); search() }}>
        <input type="text" placeholder="hledat jméno / username" value={q}
               onChange={(e) => setQ(e.target.value)} style={{ flex: 1 }} />
        <button className="btn" disabled={loading}>Hledat</button>
      </form>
      {users.length === 0 && !loading && <p className="muted">Nic nenalezeno.</p>}
      {users.map((u) => (
        <UserCard key={u.id} user={u} roles={roles} permissions={permissions}
                  onError={onError} refresh={search} />
      ))}
    </div>
  )
}
