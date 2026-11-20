// React bindings for the shared DuklaLabs component library (Shared/webui/ui.css).
// Same sliding-highlight logic as Shared/webui/ui.js (offsetLeft/offsetWidth of the
// active item), but driven by React state instead of DOM click handlers.
import { useLayoutEffect, useEffect, useRef } from 'react'

function place(el, item, instant) {
  if (!el || !item) return
  if (instant) el.style.transition = 'none'
  el.style.width = item.offsetWidth + 'px'
  el.style.transform = 'translateX(' + item.offsetLeft + 'px)'
  if (instant) {
    void el.offsetWidth // flush, so the first placement doesn't animate from 0
    el.style.transition = ''
  }
}

// Keeps `marker` (.knob / .ind) under the active item inside the element behind `ref`.
function useSlider(ref, marker, active) {
  const placed = useRef(false)
  useLayoutEffect(() => {
    const root = ref.current
    if (!root) return
    const run = () => {
      place(root.querySelector(marker), root.querySelector(active), !placed.current)
      placed.current = true
    }
    run()
    window.addEventListener('resize', run)
    if (document.fonts) document.fonts.ready.then(run)
    return () => window.removeEventListener('resize', run)
  })
}

// Segmented switch (.grp + sliding .knob). options: [[value, label], ...]
export function Switch({ value, options, onChange, label, className = '' }) {
  const ref = useRef(null)
  useSlider(ref, '.knob', 'button[aria-pressed="true"]')
  return (
    <div className={'grp ' + className} ref={ref} role="group" aria-label={label}
         style={{ gridTemplateColumns: `repeat(${options.length}, 1fr)` }}>
      <span className="knob" />
      {options.map(([v, l]) => (
        <button key={v} type="button" aria-pressed={value === v} onClick={() => onChange(v)}>{l}</button>
      ))}
    </div>
  )
}

// Sliding tab bar (nav.tabs > .tabbar > .ind). items: [{ id, label, badge? }]
export function TabBar({ items, current, onSelect, className = '' }) {
  const ref = useRef(null)
  useSlider(ref, '.ind', 'a[aria-current]')
  return (
    <nav className={'tabs ' + className}>
      <div className="wrap">
        <div className="tabbar" ref={ref}>
          <span className="ind" />
          {items.map((it) => (
            <a key={it.id} href="#" aria-current={it.id === current ? 'page' : undefined}
               onClick={(e) => { e.preventDefault(); onSelect(it.id) }}>
              {it.label}
              {it.badge ? <small className="tab-badge">{it.badge}</small> : null}
            </a>
          ))}
        </div>
      </div>
    </nav>
  )
}

// Modal on the native <dialog> (shared dialog / dialog form styling).
// Children go inside the form: use <h3>, fields and a <div className="dlg-actions">.
// Buttons inside must be type="button" (the form never submits).
export function Modal({ onClose, label, width, children }) {
  const ref = useRef(null)
  useEffect(() => {
    const el = ref.current
    if (el && !el.open) el.showModal()
  }, [])
  return (
    <dialog ref={ref} aria-label={label} style={width ? { width } : undefined}
            onCancel={(e) => { e.preventDefault(); onClose() }}
            onClick={(e) => { if (e.target === ref.current) onClose() }}>
      <form onSubmit={(e) => e.preventDefault()}>{children}</form>
    </dialog>
  )
}
