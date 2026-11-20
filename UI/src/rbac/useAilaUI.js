import { useEffect, useLayoutEffect } from 'react'

// Keeps the shared sliding indicator (.ind in .tabbar) under the active tab,
// using the AilaUI helper from the shared ui.js (same offsetLeft/offsetWidth logic).
export function useTabIndicator(barRef, activeKey) {
  useLayoutEffect(() => {
    if (barRef.current) window.AilaUI?.tabs(barRef.current)
  }, [barRef, activeKey])

  useEffect(() => {
    const place = () => barRef.current && window.AilaUI?.tabs(barRef.current)
    window.addEventListener('resize', place)
    document.fonts?.ready.then(place)
    return () => window.removeEventListener('resize', place)
  }, [barRef])
}
