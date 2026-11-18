import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './theme.css'
import './theme-toggle.js'
import LabOrchestratorDashboard from './LabOrchestratorDashboard.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <LabOrchestratorDashboard />
  </StrictMode>,
)
