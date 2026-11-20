import { useEffect, useState } from 'react'
import { api, userName } from '../api'
import { Modal } from '../../aila-ui'

export default function ProposalsPanel({ users, onClose, onReviewed, onError }) {
  const [items, setItems] = useState([])
  const [busy, setBusy] = useState(null)
  const [rejecting, setRejecting] = useState(null)
  const [note, setNote] = useState('')

  const reload = () =>
    api.listProposals('pending').then(setItems).catch((e) => onError(e.message))
  useEffect(() => { reload() }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function approve(id) {
    setBusy(id)
    try { await api.approveProposal(id); await reload(); onReviewed() }
    catch (err) { onError(err.message) } finally { setBusy(null) }
  }
  async function reject(id) {
    setBusy(id)
    try {
      await api.rejectProposal(id, note || undefined)
      setRejecting(null); setNote('')
      await reload(); onReviewed()
    } catch (err) { onError(err.message) } finally { setBusy(null) }
  }

  return (
    <Modal onClose={onClose} label="Návrhy změn od AI">
        <div className="pj-modal-head">
          <div>
            <h3>Návrhy změn od AI</h3>
            <span className="muted">
              Nevratné / citlivé akce z MCP. Provedou se až po schválení.
            </span>
          </div>
          <button type="button" className="btn sm" onClick={onClose}>✕</button>
        </div>
          {items.length === 0 && <div className="empty">Žádné čekající návrhy.</div>}
          {items.map((p) => (
            <div key={p.id} className="panel pj-prop">
              <div className="kind">{p.kind} · {p.target_type} #{p.target_id ?? '—'}</div>
              {p.summary && <div style={{ margin: '0.35rem 0' }}>{p.summary}</div>}
              <pre>{JSON.stringify(p.payload, null, 2)}</pre>
              <div className="muted" style={{ fontSize: '0.8rem' }}>
                navrhl {userName(users, p.requested_by_user_id)} · {String(p.created_at).slice(0, 16).replace('T', ' ')}
              </div>
              {rejecting === p.id ? (
                <div style={{ marginTop: '0.5rem' }}>
                  <textarea rows={2} placeholder="Důvod zamítnutí (nepovinné)"
                            value={note} onChange={(e) => setNote(e.target.value)} />
                  <div className="row" style={{ marginTop: '0.4rem' }}>
                    <button type="button" className="btn danger" disabled={busy === p.id} onClick={() => reject(p.id)}>Zamítnout</button>
                    <button type="button" className="btn" onClick={() => { setRejecting(null); setNote('') }}>Zpět</button>
                  </div>
                </div>
              ) : (
                <div className="row" style={{ marginTop: '0.5rem' }}>
                  <button type="button" className="btn primary" disabled={busy === p.id} onClick={() => approve(p.id)}>
                    Schválit a provést
                  </button>
                  <button type="button" className="btn danger" disabled={busy === p.id} onClick={() => setRejecting(p.id)}>
                    Zamítnout
                  </button>
                </div>
              )}
            </div>
          ))}
    </Modal>
  )
}
