import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import ProjectsApp from './ProjectsApp.jsx'
import './projects.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ProjectsApp />
  </StrictMode>,
)
