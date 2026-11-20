import { useState } from 'react'
import { api } from '../api'
import { useConfirm } from '../confirmContext'

function RoleCard({ role, allPermissions, reload, onError }) {
  const confirm = useConfirm()
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
    if (!(await confirm(`Smazat roli "${role.name}"?`, { title: 'Smazat roli', okLabel: 'Smazat', danger: true }))) return
    try { await api.deleteRole(role.name); await reload() }
    catch (err) { onError(err.message) }
  }

  return (
    <div className="panel">
      <div className="row between">
        <h3>
          {role.name} {role.is_system && <span className="pill s-x">systémová</span>}
        </h3>
        {!role.is_system && <button className="btn danger" onClick={del}>Smazat roli</button>}
      </div>
      {role.description && <p className="muted">{role.description}</p>}
      <div className="perm-grid">
        {allPermissions.map((p) => (
          <label key={p.name} title={p.description || ''}>
            <input type="checkbox" checked={sel.has(p.name)} onChange={() => toggle(p.name)} />
            <code>{p.name}</code>
          </label>
        ))}
      </div>
      <div className="row">
        <button className="btn primary" disabled={!dirty || busy} onClick={save}>Uložit oprávnění</button>
        {dirty && <span className="pill st-pause">neuložené změny</span>}
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
    <div className="stack">
      <form className="panel row" onSubmit={add}>
        <input type="text" placeholder="jméno role" value={name}
               onChange={(e) => setName(e.target.value)} />
        <input type="text" className="grow" placeholder="popis (nepovinné)" value={desc}
               onChange={(e) => setDesc(e.target.value)} />
        <button className="btn primary" disabled={busy}>Přidat roli</button>
      </form>

      {roles.length === 0 && (
        <div className="empty"><b>Žádné role</b><span>Vytvoř první roli výše.</span></div>
      )}
      {roles.map((r) => (
        <RoleCard key={r.name} role={r} allPermissions={permissions} reload={reload} onError={onError} />
      ))}
    </div>
  )
}
