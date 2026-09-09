import { useState } from 'react'
import { api } from '../api'

export default function PermissionsPanel({ permissions, reload, onError }) {
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [busy, setBusy] = useState(false)

  async function add(e) {
    e.preventDefault()
    if (!name.trim()) return
    setBusy(true)
    try {
      await api.createPermission(name.trim(), desc.trim() || null)
      setName(''); setDesc('')
      await reload()
    } catch (err) { onError(err.message) } finally { setBusy(false) }
  }

  async function remove(pName) {
    if (!confirm(`Smazat oprávnění "${pName}"?`)) return
    try {
      await api.deletePermission(pName)
      await reload()
    } catch (err) {
      if (String(err.message).includes('cascade')) {
        if (confirm(`${err.message}\n\nSmazat i s vazbami?`)) {
          try { await api.deletePermission(pName, true); await reload() }
          catch (e2) { onError(e2.message) }
        }
      } else { onError(err.message) }
    }
  }

  return (
    <div>
      <form className="card row" onSubmit={add}>
        <input type="text" placeholder="schema.resource:action" value={name}
               onChange={(e) => setName(e.target.value)} style={{ minWidth: 240 }} />
        <input type="text" placeholder="popis (nepovinné)" value={desc}
               onChange={(e) => setDesc(e.target.value)} style={{ flex: 1, minWidth: 200 }} />
        <button className="btn primary" disabled={busy}>Přidat</button>
      </form>

      <table>
        <thead><tr><th>Oprávnění</th><th>Popis</th><th></th></tr></thead>
        <tbody>
          {permissions.map((p) => (
            <tr key={p.name}>
              <td><code>{p.name}</code></td>
              <td className="muted">{p.description}</td>
              <td style={{ textAlign: 'right' }}>
                {p.name !== '*' && (
                  <button className="btn danger" onClick={() => remove(p.name)}>Smazat</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
