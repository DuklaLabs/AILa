import { useCallback, useEffect, useState } from 'react'
import { api, can, folderColor } from './api'
import ProjectTree from './panels/ProjectTree'
import BoardView from './panels/BoardView'
import TaskDrawer from './panels/TaskDrawer'
import CostSummary from './panels/CostSummary'
import ProposalsPanel from './panels/ProposalsPanel'
import RunningTimer from './panels/TimerPanel'
import GanttView from './panels/GanttView'

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
  const [sideOpen, setSideOpen] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

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

  if (!ready) return <div className="pj"><div className="empty">Načítám…</div></div>

  const perms = me?.permissions || []
  const canReviewProposals = can(perms, 'projects.proposal:review')
  const canFinance = can(perms, 'projects.finance:read')

  function pickProject(id) {
    setProjectId(id)
    setSideOpen(false)
  }

  const fc = folderColor(project?.folder_kind)

  return (
    <div className="pj" style={{ '--fc': fc }}>
      <div className="pj-top">
        <button
          className="pj-hamburger ghost"
          aria-label="Menu"
          onClick={() => setSideOpen((v) => !v)}
        >☰</button>
        <div className="brand"><span className="logo">DL</span> Projekty</div>
        <RunningTimer reloadKey={reloadKey} users={users} onChange={bump} onError={setError} />
        <div className="spacer" />
        {canReviewProposals && (
          <button className="ghost" onClick={() => setShowProposals(true)}>⚑ Návrhy AI</button>
        )}
        {me?.user && <span className="who">{me.user.full_name || me.user.username}</span>}
        <a href="/logout" className="ghost" style={{ padding: '0.45rem 0.7rem', border: '1px solid transparent' }}>Odhlásit</a>
      </div>

      {error && (
        <div style={{ padding: '0 1rem' }}>
          <div className="err"><span>{error}</span><button className="sm ghost" onClick={() => setError('')}>×</button></div>
        </div>
      )}

      <div className={'pj-body' + (sideOpen ? ' side-open' : '')}>
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

        <div className="pj-main">
          <div className="pj-viewbar">
            <div className="pj-seg">
              <button className={view === 'board' ? 'on' : ''} onClick={() => setView('board')}>Nástěnka</button>
              <button className={view === 'timeline' ? 'on' : ''} onClick={() => setView('timeline')}>Timeline</button>
            </div>
            {project && <span className="pj-status-pill">{project.name}</span>}
          </div>

          {project && (
            <div className="pj-proj-head" style={{ marginBottom: '0.2rem' }}>
              <h1>{project.name}</h1>
              <span className="pj-status-pill">{project.status}</span>
              {project.due_on && <span className="pj-status-pill">termín {project.due_on}</span>}
            </div>
          )}
          {project?.description && view === 'board' && (
            <p className="muted" style={{ margin: '0.3rem 0 0' }}>{project.description}</p>
          )}

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
                project={project}
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
        </div>
      </div>

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
    </div>
  )
}
