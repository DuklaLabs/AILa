import { useCallback, useEffect, useState } from 'react'
import { api, can, initials, userName, STATUSES, COST_TYPES, ORDER_STATUSES } from '../api'
import { TaskTime } from './TimerPanel'

// pole ukládaná přes spodní lištu "Uložit změny"
const FORM_KEYS = [
  'title', 'description', 'start_on', 'due_on', 'estimated_hours', 'proto_version',
  'cost_type', 'order_status', 'estimated_cost_czk', 'actual_cost_czk',
]

export default function TaskDrawer({ taskId, perms, users, onClose, onChanged, onError }) {
  const [task, setTask] = useState(null)
  const [form, setForm] = useState({})
  const [projectTasks, setProjectTasks] = useState([])
  const [busy, setBusy] = useState(false)
  const [confirmDel, setConfirmDel] = useState(false)

  const canWrite = can(perms, 'projects.task:write')
  const canAssign = can(perms, 'projects.task:assign')
  const canFinance = can(perms, 'projects.finance:write')

  const load = useCallback(() => {
    api.getTask(taskId).then((t) => {
      setTask(t)
      setForm(Object.fromEntries(FORM_KEYS.map((k) => [k, t[k] ?? ''])))
      api.listProjectTasks(t.project_id).then(setProjectTasks).catch(() => {})
    }).catch((e) => onError(e.message))
  }, [taskId, onError])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  if (!task) return null
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }))
  const ro = !canWrite

  const dirty = FORM_KEYS.some((k) => {
    const cur = form[k] === '' ? null : form[k]
    const orig = task[k] ?? null
    return String(cur) !== String(orig)
  })

  async function run(fn) {
    setBusy(true)
    try { await fn(); onChanged() } catch (err) { onError(err.message) } finally { setBusy(false) }
  }

  async function save() {
    const patch = {}
    FORM_KEYS.forEach((k) => {
      const v = form[k] === '' ? null : form[k]
      if (String(v) !== String(task[k] ?? null)) {
        patch[k] = v === null ? null
          : (['estimated_hours', 'estimated_cost_czk', 'actual_cost_czk'].includes(k) ? Number(v) : v)
      }
    })
    if (!Object.keys(patch).length) return
    await run(async () => { await api.updateTask(taskId, patch); load() })
  }

  const changeStatus = (status) => run(async () => { await api.setTaskStatus(taskId, status); load() })
  const changeAssignee = (val) =>
    run(async () => { await api.setTaskAssignee(taskId, val ? Number(val) : null); load() })
  const setCollabs = (ids) =>
    run(async () => { await api.setTaskCollaborators(taskId, ids); load() })
  const addDep = (depId) => run(async () => { await api.addDependency(taskId, Number(depId)); load() })
  const removeDep = (depId) => run(async () => { await api.removeDependency(taskId, depId); load() })
  const del = () => run(async () => { await api.deleteTask(taskId); onClose() })

  const collabs = task.collaborator_user_ids || []
  const deps = task.depends_on_task_ids || []
  const depCandidates = projectTasks.filter(
    (t) => t.id !== taskId && !deps.includes(t.id),
  )
  const collabCandidates = users.filter(
    (u) => u.id !== task.assignee_user_id && !collabs.includes(u.id),
  )

  return (
    <>
      <div className="pj-scrim" onClick={onClose} />
      <div className="pj-drawer" role="dialog" aria-label="Detail úkolu">
        <div className="pj-drawer-head">
          <h2>Úkol <span className="muted">#{task.id}</span></h2>
          <button className="ghost" onClick={onClose} aria-label="Zavřít">✕</button>
        </div>

        <div className="pj-drawer-body">
          <label className="fld">
            <span>Název úkolu</span>
            <input value={form.title} disabled={ro} onChange={(e) => set('title', e.target.value)} />
          </label>
          <label className="fld">
            <span>Popis</span>
            <textarea rows={3} value={form.description} disabled={ro}
                      placeholder="Co je potřeba udělat…"
                      onChange={(e) => set('description', e.target.value)} />
          </label>

          <div className="pj-sec">
            <h3>Stav a plán</h3>
            <label className="fld">
              <span>Stav (semafor)</span>
              <select value={task.status} disabled={ro} onChange={(e) => changeStatus(e.target.value)}>
                {STATUSES.map(([s, l]) => <option key={s} value={s}>{l}</option>)}
              </select>
            </label>
            <div className="grid2">
              <label className="fld"><span>Od</span>
                <input type="date" value={form.start_on || ''} disabled={ro}
                       onChange={(e) => set('start_on', e.target.value)} /></label>
              <label className="fld"><span>Do</span>
                <input type="date" value={form.due_on || ''} disabled={ro}
                       onChange={(e) => set('due_on', e.target.value)} /></label>
              <label className="fld"><span>Odhad (hodin)</span>
                <input type="number" step="0.5" min="0" value={form.estimated_hours} disabled={ro}
                       onChange={(e) => set('estimated_hours', e.target.value)} /></label>
              <label className="fld"><span>Verze prototypu</span>
                <input value={form.proto_version} disabled={ro} placeholder="Proto-V1"
                       onChange={(e) => set('proto_version', e.target.value)} /></label>
            </div>
          </div>

          <div className="pj-sec">
            <h3>Řešitel a tým</h3>
            <label className="fld">
              <span>Hlavní řešitel</span>
              <select value={task.assignee_user_id || ''} disabled={!canAssign}
                      onChange={(e) => changeAssignee(e.target.value)}>
                <option value="">— nikdo —</option>
                {users.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
              </select>
            </label>
            <span className="muted" style={{ fontSize: '0.8rem' }}>Spolupracovníci</span>
            <div className="row" style={{ margin: '0.3rem 0 0.4rem', gap: '0.35rem' }}>
              {collabs.length === 0 && <span className="muted" style={{ fontSize: '0.85rem' }}>nikdo</span>}
              {collabs.map((id) => (
                <span key={id} className="chip">
                  <span className="pj-avatar" style={{ width: 16, height: 16, fontSize: '0.6rem' }}>{initials(userName(users, id))}</span>
                  {userName(users, id)}
                  {canAssign && <button onClick={() => setCollabs(collabs.filter((x) => x !== id))} aria-label="Odebrat">✕</button>}
                </span>
              ))}
            </div>
            {canAssign && collabCandidates.length > 0 && (
              <select value="" onChange={(e) => e.target.value && setCollabs([...collabs, Number(e.target.value)])}>
                <option value="">+ přidat spolupracovníka…</option>
                {collabCandidates.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}
              </select>
            )}
          </div>

          <div className="pj-sec">
            <h3>Finanční modul (Fáze 3 – Nákupy)</h3>
            <div className="grid2">
              <label className="fld"><span>Typ nákladu</span>
                <select value={form.cost_type} disabled={ro} onChange={(e) => set('cost_type', e.target.value)}>
                  <option value="">—</option>
                  {COST_TYPES.map(([s, l]) => <option key={s} value={s}>{l}</option>)}
                </select></label>
              <label className="fld"><span>Stav objednávky</span>
                <select value={form.order_status} disabled={ro} onChange={(e) => set('order_status', e.target.value)}>
                  <option value="">—</option>
                  {ORDER_STATUSES.map(([s, l]) => <option key={s} value={s}>{l}</option>)}
                </select></label>
              <label className="fld"><span>Předpokládaná cena (Kč)</span>
                <input type="number" min="0" value={form.estimated_cost_czk} disabled={ro}
                       onChange={(e) => set('estimated_cost_czk', e.target.value)} /></label>
              <label className="fld"><span>Skutečná cena (Kč)</span>
                <input type="number" min="0" value={form.actual_cost_czk}
                       disabled={!canFinance}
                       title={canFinance ? '' : 'Vyžaduje oprávnění projects.finance:write'}
                       onChange={(e) => set('actual_cost_czk', e.target.value)} /></label>
            </div>
          </div>

          <div className="pj-sec">
            <h3>Závislosti</h3>
            {deps.length === 0 && <p className="muted" style={{ fontSize: '0.85rem', margin: '0 0 0.4rem' }}>Na ničem nezávisí.</p>}
            {deps.map((d) => {
              const dt = projectTasks.find((x) => x.id === d)
              return (
                <div key={d} className="row" style={{ justifyContent: 'space-between', padding: '0.2rem 0' }}>
                  <span>⛓ {dt ? dt.title : `úkol #${d}`}</span>
                  {canWrite && <button className="sm ghost" onClick={() => removeDep(d)}>odebrat</button>}
                </div>
              )
            })}
            {canWrite && depCandidates.length > 0 && (
              <select value="" onChange={(e) => e.target.value && addDep(e.target.value)} style={{ marginTop: '0.3rem' }}>
                <option value="">+ přidat závislost…</option>
                {depCandidates.map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}
              </select>
            )}
          </div>

          <div className="pj-sec">
            <h3>Čas</h3>
            <TaskTime taskId={taskId} perms={perms} onChanged={onChanged} onError={onError} />
          </div>

          {canWrite && (
            <div className="pj-sec">
              <h3>Odstranění</h3>
              {confirmDel ? (
                <div className="pj-inline-confirm">
                  <span>Opravdu smazat tento úkol? Nevratné.</span>
                  <button className="danger" disabled={busy} onClick={del}>Ano, smazat</button>
                  <button className="ghost" onClick={() => setConfirmDel(false)}>Zpět</button>
                </div>
              ) : (
                <button className="danger" onClick={() => setConfirmDel(true)}>Smazat úkol</button>
              )}
            </div>
          )}
        </div>

        {canWrite && (
          <div className="pj-save-bar">
            {dirty && <span className="muted" style={{ marginRight: 'auto', alignSelf: 'center', fontSize: '0.83rem' }}>neuložené změny</span>}
            <button onClick={load} disabled={!dirty || busy}>Zahodit</button>
            <button className="primary" onClick={save} disabled={!dirty || busy}>Uložit změny</button>
          </div>
        )}
      </div>
    </>
  )
}
