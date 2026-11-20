import { useCallback, useEffect, useState } from 'react'
import { api, can, folderColor } from './api'
import ProjectTree from './panels/ProjectTree'
import BoardView from './panels/BoardView'
import TaskDrawer from './panels/TaskDrawer'
import CostSummary from './panels/CostSummary'
import ProposalsPanel from './panels/ProposalsPanel'
import PocketPanel from './panels/PocketPanel'
import RunningTimer from './panels/TimerPanel'
import GanttView from './panels/GanttView'
import { Icon, Switch, TabBar } from '../aila-ui'

const LOGO = (
  <svg viewBox="0 0 192 192" aria-hidden="true">
    <defs>
      <mask id="pjLogoMask">
        <rect width="192" height="192" fill="#fff" />
        <polygon points="24,0 69,0 40,74 76,74 14,188 27,110 4,110" fill="#000" stroke="#000" strokeWidth="18" />
        <circle cx="95" cy="96" r="38" fill="#000" />
      </mask>
    </defs>
    <g mask="url(#pjLogoMask)">
      <path className="gear" d="M164.2 76.2 L186.6 79.9 L186.6 112.1 L164.2 115.8 L163.2 119 L162.1 122 L160.9 125.1 L159.5 128 L158 130.9 L171.2 149.3 L148.3 172.2 L129.9 159 L127 160.5 L124.1 161.9 L121 163.1 L118 164.2 L114.8 165.2 L111.1 187.6 L78.9 187.6 L75.2 165.2 L72 164.2 L69 163.1 L65.9 161.9 L63 160.5 L60.1 159 L41.7 172.2 L18.8 149.3 L32 130.9 L30.5 128 L29.1 125.1 L27.9 122 L26.8 119 L25.8 115.8 L3.4 112.1 L3.4 79.9 L25.8 76.2 L26.8 73 L27.9 70 L29.1 66.9 L30.5 64 L32 61.1 L18.8 42.7 L41.7 19.8 L60.1 33 L63 31.5 L65.9 30.1 L69 28.9 L72 27.8 L75.2 26.8 L78.9 4.4 L111.1 4.4 L114.8 26.8 L118 27.8 L121 28.9 L124.1 30.1 L127 31.5 L129.9 33 L148.3 19.8 L171.2 42.7 L158 61.1 L159.5 64 L160.9 66.9 L162.1 70 L163.2 73Z" />
    </g>
    <polygon className="bolt" points="24,0 69,0 40,74 76,74 14,188 27,110 4,110" />
  </svg>
)

const PHASE_ICON = (
  <Icon>
    <path d="M12 3l9 5-9 5-9-5 9-5z" />
    <path d="M3 13l9 5 9-5" />
  </Icon>
)

export default function ProjectsApp() {
  const [me, setMe] = useState(null)
  const [users, setUsers] = useState([])
  const [ready, setReady] = useState(false)
  const [error, setError] = useState('')
  const [projectId, setProjectId] = useState(null)
  const [project, setProject] = useState(null)
  const [taskId, setTaskId] = useState(null)
  const [view, setView] = useState('board')
  const [showProposals, setShowProposals] = useState(false)
  const [showPocket, setShowPocket] = useState(false)
  const [sideOpen, setSideOpen] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)
  const [phasePick, setPhasePick] = useState(null)
  const [counts, setCounts] = useState({})

  const bump = useCallback(() => setReloadKey((k) => k + 1), [])

  useEffect(() => {
    Promise.all([api.me(), api.listUsers().catch(() => [])])
      .then(([m, u]) => { setMe(m); setUsers(u) })
      .catch((e) => setError(e.message))
      .finally(() => setReady(true))
  }, [])

  useEffect(() => {
    if (!projectId) return
    api.getProject(projectId).then(setProject).catch((e) => setError(e.message))
    return () => setProject(null)
  }, [projectId, reloadKey])

  // počty úkolů na fázi (odznaky v záložkách fází)
  useEffect(() => {
    if (!projectId) return
    api.listProjectTasks(projectId)
      .then((all) => {
        const c = {}
        all.forEach((t) => { c[t.phase_id] = (c[t.phase_id] || 0) + 1 })
        setCounts(c)
      })
      .catch(() => {})
  }, [projectId, reloadKey])

  if (!ready) return <div className="pj"><main><div className="wrap"><div className="empty">Načítám…</div></div></main></div>

  const perms = me?.permissions || []
  const canReviewProposals = can(perms, 'projects.proposal:review')
  const canFinance = can(perms, 'projects.finance:read')
  const canUseAi = can(perms, 'projects.ai:use')

  function pickProject(id) {
    setProjectId(id)
    setSideOpen(false)
  }

  const fc = folderColor(project?.folder_kind)
  const phases = project?.phases || []
  // aktivní fáze: ruční volba, dokud patří k projektu, jinak první fáze
  const phaseId = phases.some((p) => p.id === phasePick) ? phasePick : (phases[0]?.id ?? null)

  return (
    <div className="pj" style={{ '--fc': fc }}>
      <header className="top">
        <div className="wrap">
          <div className="brand">
            <div className="logo" role="img" aria-label="Logo DuklaLabs">{LOGO}</div>
            <div>
              <h1>Projekty <span>DuklaLabs</span></h1>
              <p>Úkoly, fáze a time tracking</p>
            </div>
            <div className="tools">
              <button
                type="button"
                className="btn sm pj-hamburger"
                aria-label="Menu projektů"
                onClick={() => setSideOpen((v) => !v)}
              >☰ Projekty</button>
              <RunningTimer reloadKey={reloadKey} users={users} onChange={bump} onError={setError} />
              {canUseAi && (
                <button type="button" className="btn sm" onClick={() => setShowPocket(true)}>🎙 Pocket</button>
              )}
              {canReviewProposals && (
                <button type="button" className="btn sm" onClick={() => setShowProposals(true)}>⚑ Návrhy AI</button>
              )}
              {me?.user && <span className="pj-who">{me.user.full_name || me.user.username}</span>}
              <a href="/logout" className="btn sm">Odhlásit</a>
            </div>
          </div>
        </div>
      </header>

      {view === 'board' && project && phases.length > 0 && (
        <TabBar
          label="Fáze projektu"
          className="pj-phases"
          current={phaseId}
          onSelect={setPhasePick}
          items={phases.map((p) => ({
            id: p.id,
            label: `${p.position}. ${p.name}`,
            icon: PHASE_ICON,
            badge: counts[p.id],
          }))}
        />
      )}

      {error && (
        <div className="toast pj-toast-err" role="alert">
          <span>{error}</span>
          <button type="button" className="copy" aria-label="Zavřít" onClick={() => setError('')}>×</button>
        </div>
      )}

      <main>
        <div className={'wrap pj-body' + (sideOpen ? ' side-open' : '')}>
          {sideOpen && <div className="pj-side-scrim" onClick={() => setSideOpen(false)} />}
          <div className="pj-side">
            <ProjectTree
              perms={perms}
              users={users}
              activeId={projectId}
              onSelect={pickProject}
              reloadKey={reloadKey}
              onCreated={(id) => { bump(); pickProject(id) }}
              onError={setError}
            />
          </div>

          <section className="view pj-main">
            <div className="head">
              <h2 className={project ? 'pj-proj-title' : undefined}>{project ? project.name : 'Projekty'}</h2>
              {project && <span className="pill s-x">{project.status}</span>}
              {project?.due_on && <span className="pill st-run">termín {project.due_on}</span>}
              <div className="actions">
                <Switch
                  label="Zobrazení"
                  value={view}
                  onChange={setView}
                  options={[['board', 'Nástěnka'], ['timeline', 'Timeline']]}
                />
              </div>
              {project?.description && view === 'board' && <p>{project.description}</p>}
            </div>

            {view === 'board' && !project && (
              <div className="empty">
                {projectId ? 'Načítám projekt…' : 'Vyber projekt v postranním panelu, nebo přepni na Timeline pro přehled všech projektů.'}
              </div>
            )}
            {view === 'board' && project && (
              <>
                {canFinance && (
                  <CostSummary projectId={project.id} reloadKey={reloadKey} onError={setError} />
                )}
                <BoardView
                  key={project.id}
                  phaseId={phaseId}
                  perms={perms}
                  users={users}
                  reloadKey={reloadKey}
                  onOpenTask={setTaskId}
                  onChanged={bump}
                  onError={setError}
                />
              </>
            )}
            {view === 'timeline' && (
              <GanttView
                key={(project?.id || 'all') + ':' + reloadKey}
                project={project}
                onOpenTask={setTaskId}
                onSelectProject={pickProject}
                onError={setError}
              />
            )}
          </section>
        </div>
      </main>

      {taskId && (
        <TaskDrawer
          taskId={taskId}
          perms={perms}
          users={users}
          onClose={() => setTaskId(null)}
          onChanged={bump}
          onError={setError}
        />
      )}

      {showProposals && (
        <ProposalsPanel
          users={users}
          onClose={() => setShowProposals(false)}
          onReviewed={bump}
          onError={setError}
        />
      )}

      {showPocket && (
        <PocketPanel
          users={users}
          onClose={() => setShowPocket(false)}
          onProposed={() => { bump(); setShowPocket(false); setShowProposals(true) }}
          onError={setError}
        />
      )}
    </div>
  )
}
