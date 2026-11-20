import { useState } from 'react'
import { api } from '../api'
import { useConfirm } from '../confirmContext'

export default function PermissionsPanel({ permissions, reload, onError }) {
  const confirm = useConfirm()
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
    if (!(await confirm(`Smazat oprávnění "${pName}"?`, { title: 'Smazat oprávnění', okLabel: 'Smazat', danger: true }))) return
    try {
      await api.deletePermission(pName)
      await reload()
    } catch (err) {
      if (String(err.message).includes('cascade')) {
        if (await confirm(`${err.message}\n\nSmazat i s vazbami?`, { title: 'Smazat s vazbami', okLabel: 'Smazat vše', danger: true })) {
          try { await api.deletePermission(pName, true); await reload() }
          catch (e2) { onError(e2.message) }
        }
      } else { onError(err.message) }
    }
  }

  return (
    <div className="stack">
      <form className="panel row" onSubmit={add}>
        <input type="text" placeholder="schema.resource:action" value={name}
               onChange={(e) => setName(e.target.value)} style={{ minWidth: 240 }} />
        <input type="text" className="grow" placeholder="popis (nepovinné)" value={desc}
               onChange={(e) => setDesc(e.target.value)} />
        <button className="btn primary" disabled={busy}>Přidat</button>
      </form>

      <div className="panel">
        {permissions.length === 0 ? (
          <div className="empty"><b>Žádná oprávnění</b><span>Přidej první oprávnění výše.</span></div>
        ) : (
          <div className="tbl">
            <table>
              <thead><tr><th>Oprávnění</th><th>Popis</th><th></th></tr></thead>
              <tbody>
                {permissions.map((p) => (
                  <tr key={p.name}>
                    <td><code>{p.name}</code></td>
                    <td className="muted">{p.description}</td>
                    <td className="actions">
                      {p.name !== '*' && (
                        <button className="btn danger" onClick={() => remove(p.name)}>Smazat</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
