import { useEffect, useMemo, useState } from 'react'
import { api, can, initials, isOverdue, userName, STATUSES } from '../api'

// Aktivní fáze (záložky nav.tabs) vybírá ProjectsApp, deska ukazuje její úkoly.
export default function BoardView({ phaseId, perms, users, reloadKey, onOpenTask, onChanged, onError }) {
  const [tasks, setTasks] = useState([])
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState({ title: '', assignee: '' })
  const [draggingId, setDraggingId] = useState(null)
  const [dropCol, setDropCol] = useState(null)

  const canWrite = can(perms, 'projects.task:write')
  const canAssign = can(perms, 'projects.task:assign')

  useEffect(() => {
    if (!phaseId) return
    api.listPhaseTasks(phaseId).then(setTasks).catch((e) => onError(e.message))
  }, [phaseId, reloadKey, onError])

  const byStatus = useMemo(() => {
    const m = Object.fromEntries(STATUSES.map(([s]) => [s, []]))
    tasks.forEach((t) => (m[t.status] || (m[t.status] = [])).push(t))
    return m
  }, [tasks])

  async function move(taskId, status) {
    const t = tasks.find((x) => x.id === taskId)
    if (!t || t.status === status) return
    setTasks((prev) => prev.map((x) => (x.id === taskId ? { ...x, status } : x)))
    try {
      await api.setTaskStatus(taskId, status)
      onChanged()
    } catch (err) {
      onError(err.message)
      api.listPhaseTasks(phaseId).then(setTasks).catch(() => {})
    }
  }

  async function addTask(e) {
    e.preventDefault()
    try {
      const body = { phase_id: phaseId, title: form.title.trim() }
      if (canAssign && form.assignee) body.assignee_user_id = Number(form.assignee)
      await api.createTask(body)
      setForm({ title: '', assignee: '' })
      setAdding(false)
      onChanged()
    } catch (err) { onError(err.message) }
  }

  function endDrag() {
    setDraggingId(null)
    setDropCol(null)
  }

  if (!phaseId) return <div className="empty">Projekt nemá žádné fáze.</div>

  return (
    <div>
      {canWrite && (
        adding ? (
          <form onSubmit={addTask} className="card pj-card pj-card-form">
            <input autoFocus placeholder="Název úkolu (např. Návrh napájecí kaskády 5V/3.3V)"
                   value={form.title} required
                   onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <div className="row">
              {canAssign && (
                <select value={form.assignee} onChange={(e) => setForm({ ...form, assignee: e.target.value })} style={{ flex: 1 }}>
                  <option value="">Bez řešitele</option>
                  {users.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
                </select>
              )}
              <button className="btn sm primary" type="submit">Přidat</button>
              <button type="button" className="btn sm" onClick={() => setAdding(false)}>Zrušit</button>
            </div>
          </form>
        ) : (
          <button type="button" className="btn sm pj-add" onClick={() => setAdding(true)}>
            + Přidat úkol do fáze
          </button>
        )
      )}

      <div className="pj-board">
        {STATUSES.map(([s, label]) => (
          <div key={s}
               className={'panel pj-col' + (dropCol === s && draggingId ? ' drop-target' : '')}
               onDragOver={(e) => { if (draggingId != null) { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; setDropCol(s) } }}
               onDrop={(e) => {
                 e.preventDefault()
                 const id = Number(e.dataTransfer.getData('text/plain')) || draggingId
                 endDrag()
                 if (id) move(id, s)
               }}>
            <div className="pj-col-head">
              <i className="dot" style={{ '--c': `var(--st-${s})`, '--cs': `var(--st-${s})` }} />
              {label}
              <span className="n">{byStatus[s]?.length || 0}</span>
            </div>
            <div className="pj-col-scroll">
              {(byStatus[s] || []).map((t, i) => (
                <div key={t.id}
                     className={'card pj-card' + (draggingId === t.id ? ' dragging' : '')}
                     style={{ '--st': `var(--st-${t.status})`, '--i': i }}
                     draggable={canWrite}
                     onDragStart={(e) => {
                       e.dataTransfer.effectAllowed = 'move'
                       e.dataTransfer.setData('text/plain', String(t.id))
                       setDraggingId(t.id)
                     }}
                     onDragEnd={endDrag}
                     onClick={() => onOpenTask(t.id)}>
                  <div className="t">{t.title}</div>
                  <div className="row">
                    {t.assignee_user_id
                      ? <span className="avatar pj-avatar" title={userName(users, t.assignee_user_id)}>{initials(userName(users, t.assignee_user_id))}</span>
                      : <span className="chip">bez řešitele</span>}
                    {t.proto_version && <span className="chip">{t.proto_version}</span>}
                    {t.due_on && <span className={isOverdue(t.due_on, t.status) ? 'pill s-a' : 'chip'}>do {t.due_on}</span>}
                    {t.estimated_hours ? <span className="chip">{t.estimated_hours} h</span> : null}
                  </div>
                  {canWrite && (
                    <div className="pj-card-move" onClick={(e) => e.stopPropagation()}>
                      <select value={t.status} onChange={(e) => move(t.id, e.target.value)}>
                        {STATUSES.map(([sv, sl]) => <option key={sv} value={sv}>{sl}</option>)}
                      </select>
                    </div>
                  )}
                </div>
              ))}
              {(byStatus[s] || []).length === 0 && (
                <div className="muted pj-col-empty">—</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
