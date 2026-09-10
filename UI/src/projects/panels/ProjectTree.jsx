import { useEffect, useState } from 'react'
import { api, can, folderColor } from '../api'

export default function ProjectTree({ perms, activeId, onSelect, reloadKey, onCreated, onError }) {
  const [folders, setFolders] = useState([])
  const [projects, setProjects] = useState([])
  const [creating, setCreating] = useState(false)
  const [form, setForm] = useState({ folder_id: '', name: '', due_on: '', planned_budget_czk: '' })

  const canWrite = can(perms, 'projects.project:write')
  const canBudget = can(perms, 'projects.finance:write')

  useEffect(() => {
    Promise.all([api.listFolders(), api.listProjects()])
      .then(([f, p]) => { setFolders(f); setProjects(p) })
      .catch((e) => onError(e.message))
  }, [reloadKey, onError])

  async function submit(e) {
    e.preventDefault()
    try {
      const body = { folder_id: Number(form.folder_id), name: form.name.trim() }
      if (form.due_on) body.due_on = form.due_on
      if (canBudget && form.planned_budget_czk) body.planned_budget_czk = Number(form.planned_budget_czk)
      const proj = await api.createProject(body)
      setCreating(false)
      setForm({ folder_id: '', name: '', due_on: '', planned_budget_czk: '' })
      onCreated(proj.id)
    } catch (err) { onError(err.message) }
  }

  return (
    <div>
      <div className="side-head">
        <h2>Projekty</h2>
        {canWrite && (
          <button className="sm primary" onClick={() => setCreating((v) => !v)}>
            {creating ? 'Zrušit' : '+ Nový'}
          </button>
        )}
      </div>

      {creating && (
        <form onSubmit={submit} style={{ display: 'grid', gap: '0.4rem', margin: '0.4rem 0 0.8rem' }}>
          <select value={form.folder_id} required
                  onChange={(e) => setForm({ ...form, folder_id: e.target.value })}>
            <option value="">Vyber složku…</option>
            {folders.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
          </select>
          <input placeholder="Název projektu" value={form.name} required
                 onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <label className="fld" style={{ margin: 0 }}>
            <span>Termín dokončení</span>
            <input type="date" value={form.due_on}
                   onChange={(e) => setForm({ ...form, due_on: e.target.value })} />
          </label>
          {canBudget && (
            <label className="fld" style={{ margin: 0 }}>
              <span>Plánovaný rozpočet (Kč)</span>
              <input type="number" min="0" value={form.planned_budget_czk}
                     onChange={(e) => setForm({ ...form, planned_budget_czk: e.target.value })} />
            </label>
          )}
          <button className="primary" type="submit">Založit (vytvoří 5 fází)</button>
        </form>
      )}

      {folders.map((f) => {
        const inFolder = projects.filter((p) => p.folder_id === f.id)
        return (
          <div key={f.id} className="pj-folder" style={{ '--fc': folderColor(f.kind) }}>
            <div className="f-name">{f.name}</div>
            {inFolder.length === 0 && <div className="muted" style={{ fontSize: '0.8rem', padding: '0.1rem 0.5rem' }}>žádné projekty</div>}
            {inFolder.map((p) => (
              <button key={p.id}
                      className={'pj-proj' + (p.id === activeId ? ' active' : '')}
                      onClick={() => onSelect(p.id)}>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.name}</span>
                <span className="count">{p.task_count}</span>
              </button>
            ))}
          </div>
        )
      })}

      {folders.length > 0 && projects.length === 0 && !creating && (
        <p className="muted" style={{ fontSize: '0.82rem', marginTop: '1rem' }}>
          Zatím žádné projekty.{canWrite ? ' Klikni na „+ Nový".' : ''}
        </p>
      )}
    </div>
  )
}
