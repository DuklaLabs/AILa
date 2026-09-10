import RbacConsole from "./rbac/RbacConsole";

// Orchestrator dashboard (./LabOrchestratorDashboard) zůstává v repu, ale zatím
// se nemountuje – tenhle build servíruje RBAC konzoli pod /admin/rbac/.
function App() {
  return <RbacConsole />;
}

export default App;
