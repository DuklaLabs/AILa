import { useEffect, useMemo, useState } from 'react'
import {
  addDays, api, daysBetween, folderColor, FOLDER_LABELS,
  parseDate, readyToStart, today0, STATUSES,
} from '../api'

const ROW_H = 34
const LABEL_W = 230
const ZOOMS = [3, 6, 11]

const monthStart = (d) => new Date(d.getFullYear(), d.getMonth(), 1)
const monthEnd = (d) => new Date(d.getFullYear(), d.getMonth() + 1, 0)
const daysInMonth = (d) => new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate()
const MONTHS = ['led', 'úno', 'bře', 'dub', 'kvě', 'čvn', 'čvc', 'srp', 'zář', 'říj', 'lis', 'pro']

export default function GanttView({ project, onOpenTask, onSelectProject, onError }) {
  const mode = project ? 'tasks' : 'portfolio'
  const [tasks, setTasks] = useState([])
  const [projects, setProjects] = useState([])
  const [zoom, setZoom] = useState(1)
  const dayW = ZOOMS[zoom]

  useEffect(() => {
    if (mode === 'tasks') {
      api.listProjectTasks(project.id).then(setTasks).catch((e) => onError(e.message))
    } else {
      api.listProjects().then(setProjects).catch((e) => onError(e.message))
    }
  }, [mode, project?.id, onError])

  const model = useMemo(() => {
    const t0 = today0()
    // 1) sesbírej položky s intervalem
    let items = []
    if (mode === 'tasks') {
      const projStart = parseDate(project.started_on) || t0
      items = tasks.map((tk) => {
        const s = parseDate(tk.start_on) || (tk.due_on ? addDays(parseDate(tk.due_on), -5) : projStart)
        const e = parseDate(tk.due_on) || addDays(s, 5)
        return { ...tk, _s: s, _e: e < s ? addDays(s, 3) : e, _dateless: !tk.start_on && !tk.due_on }
      })
    } else {
      items = projects.map((p) => {
        const s = parseDate(p.started_on) || t0
        const e = parseDate(p.due_on) || addDays(s, 90)
        return { ...p, _s: s, _e: e < s ? addDays(s, 30) : e }
      })
    }

    if (!items.length) return null

    let minD = monthStart(items.reduce((m, i) => (i._s < m ? i._s : m), items[0]._s))
    let maxD = monthEnd(items.reduce((m, i) => (i._e > m ? i._e : m), items[0]._e))
    if (t0 < minD) minD = monthStart(t0)
    if (t0 > maxD) maxD = monthEnd(t0)

    const totalDays = daysBetween(minD, maxD) + 1
    const chartW = totalDays * dayW

    // měsíční hlavička
    const months = []
    for (let d = new Date(minD); d <= maxD; d = new Date(d.getFullYear(), d.getMonth() + 1, 1)) {
      months.push({ label: `${MONTHS[d.getMonth()]} ${String(d.getFullYear()).slice(2)}`, w: daysInMonth(d) * dayW })
    }

    const byId = new Map(items.map((i) => [i.id, i]))

    // 2) řádky (skupiny + položky) s Y-pozicí
    const rows = []
    let y = 0
    const push = (r) => { rows.push({ ...r, y }); y += ROW_H }

    if (mode === 'tasks') {
      const phases = project.phases || []
      for (const ph of phases) {
        const inPhase = items.filter((i) => i.phase_id === ph.id)
        if (!inPhase.length) continue
        push({ type: 'group', label: `${ph.position}. ${ph.name}` })
        for (const it of inPhase) {
          push({
            type: 'task', item: it,
            x: daysBetween(minD, it._s) * dayW,
            w: Math.max(dayW * 3, daysBetween(it._s, it._e) * dayW),
            ready: readyToStart(it, byId),
          })
        }
      }
    } else {
      const groups = {}
      items.forEach((i) => (groups[i.folder_kind] = groups[i.folder_kind] || []).push(i))
      for (const kind of Object.keys(FOLDER_LABELS)) {
        const inG = groups[kind] || []
        if (!inG.length) continue
        push({ type: 'group', label: FOLDER_LABELS[kind] })
        for (const it of inG) {
          push({
            type: 'project', item: it, kind,
            x: daysBetween(minD, it._s) * dayW,
            w: Math.max(dayW * 3, daysBetween(it._s, it._e) * dayW),
          })
        }
      }
    }

    // 3) spojnice závislostí (jen task mode)
    const links = []
    if (mode === 'tasks') {
      const rowByTask = new Map(rows.filter((r) => r.type === 'task').map((r) => [r.item.id, r]))
      for (const r of rowByTask.values()) {
        for (const depId of r.item.depends_on_task_ids || []) {
          const from = rowByTask.get(depId)
          if (from) links.push({ from, to: r })
        }
      }
    }

    const todayX = daysBetween(minD, t0) * dayW
    return { rows, months, chartW, height: y, links, todayX, totalDays }
  }, [mode, tasks, projects, project, dayW])

  if (!model) return <div className="empty">Žádná data pro timeline.</div>

  const { rows, months, chartW, height, links, todayX } = model

  return (
    <div className="pj-gantt">
      <div className="pj-gantt-toolbar">
        <span className="muted" style={{ fontSize: '0.83rem' }}>
          {mode === 'tasks' ? 'Úkoly projektu na časové ose – šipky = závislosti, ▶ = lze spustit' : 'Projekty na časové ose'}
        </span>
        <div className="row" style={{ marginLeft: 'auto', gap: '0.3rem' }}>
          <button className="sm" disabled={zoom === 0} onClick={() => setZoom((z) => Math.max(0, z - 1))}>−</button>
          <button className="sm" disabled={zoom === ZOOMS.length - 1} onClick={() => setZoom((z) => Math.min(ZOOMS.length - 1, z + 1))}>+</button>
        </div>
      </div>

      <div className="pj-gantt-scroll">
        <div className="pj-gantt-inner" style={{ width: LABEL_W + chartW }}>
          {/* hlavička měsíců */}
          <div className="pj-gantt-head" style={{ height: ROW_H }}>
            <div className="pj-gantt-corner" style={{ width: LABEL_W }} />
            {months.map((m, i) => (
              <div key={i} className="pj-gantt-month" style={{ width: m.w }}>{m.label}</div>
            ))}
          </div>

          {/* tělo */}
          <div className="pj-gantt-body" style={{ height: Math.max(height, ROW_H) }}>
            {/* dnešní čára */}
            {todayX >= 0 && todayX <= chartW && (
              <div className="pj-gantt-today" style={{ left: LABEL_W + todayX }} title="dnes" />
            )}

            {/* spojnice závislostí */}
            {links.length > 0 && (
              <svg className="pj-gantt-links" width={LABEL_W + chartW} height={Math.max(height, ROW_H)}>
                <defs>
                  <marker id="pj-arrow" viewBox="0 0 8 8" refX="6" refY="4" markerWidth="7" markerHeight="7" orient="auto">
                    <path d="M0 0 L8 4 L0 8 z" fill="currentColor" />
                  </marker>
                </defs>
                {links.map((l, i) => {
                  const x1 = LABEL_W + l.from.x + l.from.w
                  const y1 = l.from.y + ROW_H / 2
                  const x2 = LABEL_W + l.to.x
                  const y2 = l.to.y + ROW_H / 2
                  const mx = Math.max(x1 + 8, x2 - 10)
                  return (
                    <path key={i} className="pj-gantt-link"
                          d={`M${x1} ${y1} H${mx} V${y2} H${x2 - 2}`}
                          markerEnd="url(#pj-arrow)" />
                  )
                })}
              </svg>
            )}

            {/* řádky */}
            {rows.map((r, i) => {
              if (r.type === 'group') {
                return (
                  <div key={i} className="pj-gantt-row group" style={{ top: r.y, height: ROW_H }}>
                    <div className="pj-gantt-label" style={{ width: LABEL_W }}>{r.label}</div>
                  </div>
                )
              }
              const it = r.item
              const isTask = r.type === 'task'
              const color = isTask ? `var(--st-${it.status})` : folderColor(r.kind)
              return (
                <div key={i} className="pj-gantt-row" style={{ top: r.y, height: ROW_H }}
                     onClick={() => (isTask ? onOpenTask(it.id) : onSelectProject(it.id))}>
                  <div className="pj-gantt-label" style={{ width: LABEL_W }} title={isTask ? it.title : it.name}>
                    {r.ready && <span className="pj-ready" title="všechny závislosti hotové – lze spustit">▶</span>}
                    <span className="pj-gantt-name">{isTask ? it.title : it.name}</span>
                  </div>
                  <div className="pj-gantt-track">
                    <div className={'pj-gantt-bar' + (r.ready ? ' ready' : '') + (it._dateless ? ' dateless' : '')}
                         style={{ left: r.x, width: r.w, '--bc': color }}>
                      <span className="pj-gantt-bar-txt">{isTask ? it.title : it.name}</span>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      <div className="pj-gantt-legend">
        {mode === 'tasks'
          ? STATUSES.map(([s, l]) => (
              <span key={s}><i style={{ background: `var(--st-${s})` }} />{l}</span>
            ))
          : Object.entries(FOLDER_LABELS).map(([k, l]) => (
              <span key={k}><i style={{ background: `var(--cat-${k})` }} />{l}</span>
            ))}
        <span><i className="pj-ready-dot" />lze spustit</span>
        <span><i className="pj-today-dot" />dnes</span>
      </div>
    </div>
  )
}
