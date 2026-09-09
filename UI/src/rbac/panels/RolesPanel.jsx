import { useState } from 'react'
import { api } from '../api'

function RoleCard({ role, allPermissions, reload, onError }) {
  const [sel, setSel] = useState(new Set(role.permissions))
  const [busy, setBusy] = useState(false)
  const dirty =
    sel.size !== role.permissions.length ||
    role.permissions.some((p) => !sel.has(p))

  function toggle(name) {
    const next = new Set(sel)
    next.has(name) ? next.delete(name) : next.add(name)
    setSel(next)
  }

  async function save() {
    setBusy(true)
    try {
      await api.setRolePermissions(role.name, [...sel])
      await reload()
    } catch (err) { onError(err.message) } finally { setBusy(false) }
  }

  async function del() {
    if (!confirm(`Smazat roli "${role.name}"?`)) return
    try { await api.deleteRole(role.name); await reload() }
    catch (err) { onError(err.message) }
  }

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h3>
          {role.name} {role.is_system && <span className="chip">systémová</span>}
        </h3>
        {!role.is_system && <button className="btn danger" onClick={del}>Smazat roli</button>}
      </div>
      {role.description && <p className="muted" style={{ marginTop: 0 }}>{role.description}</p>}
      <div className="perm-grid">
        {allPermissions.map((p) => (
          <label key={p.name} title={p.description || ''}>
            <input type="checkbox" checked={sel.has(p.name)} onChange={() => toggle(p.name)} />
            <code>{p.name}</code>
          </label>
        ))}
      </div>
      <div className="row" style={{ marginTop: '0.6rem' }}>
        <button className="btn primary" disabled={!dirty || busy} onClick={save}>Uložit oprávnění</button>
        {dirty && <span className="muted">neuložené změny</span>}
      </div>
    </div>
  )
}

export default function RolesPanel({ roles, permissions, reload, onError }) {
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [busy, setBusy] = useState(false)

  async function add(e) {
    e.preventDefault()
    if (!name.trim()) return
    setBusy(true)
    try {
      await api.createRole(name.trim(), desc.trim() || null)
      setName(''); setDesc('')
      await reload()
    } catch (err) { onError(err.message) } finally { setBusy(false) }
  }

  return (
    <div>
      <form className="card row" onSubmit={add}>
        <input type="text" placeholder="jméno role" value={name}
               onChange={(e) => setName(e.target.value)} />
        <input type="text" placeholder="popis (nepovinné)" value={desc}
               onChange={(e) => setDesc(e.target.value)} style={{ flex: 1, minWidth: 200 }} />
        <button className="btn primary" disabled={busy}>Přidat roli</button>
      </form>

      {roles.map((r) => (
        <RoleCard key={r.name} role={r} allPermissions={permissions} reload={reload} onError={onError} />
      ))}
    </div>
  )
}
