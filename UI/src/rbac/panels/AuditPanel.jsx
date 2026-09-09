import { useEffect, useState } from 'react'
import { api } from '../api'

export default function AuditPanel({ onError }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(false)

  async function load() {
    setLoading(true)
    try { setRows(await api.listAudit(200)) }
    catch (err) { onError(err.message) } finally { setLoading(false) }
  }

  useEffect(() => { load() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div>
      <button className="btn" onClick={load} disabled={loading}>Obnovit</button>
      <table style={{ marginTop: '0.75rem' }}>
        <thead>
          <tr><th>Kdy</th><th>Kdo</th><th>Akce</th><th>Cíl</th><th>Detail</th></tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td className="muted" style={{ whiteSpace: 'nowrap' }}>{r.created_at}</td>
              <td>{r.actor_name || r.actor_id || '—'}</td>
              <td><code>{r.action}</code></td>
              <td>{r.target_type} <code>{r.target_id}</code></td>
              <td><pre>{JSON.stringify(r.detail)}</pre></td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length === 0 && !loading && <p className="muted">Zatím žádné záznamy.</p>}
    </div>
  )
}
