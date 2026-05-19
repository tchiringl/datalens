import { Routes, Route } from 'react-router-dom'
import Layout from './components/layout/Layout'
import Dashboard from './pages/Dashboard'
import Sources from './pages/Sources'
import Pipelines from './pages/Pipelines'
import CDMExplorer from './pages/CDMExplorer'
import DataQuality from './pages/DataQuality'
import Governance from './pages/Governance'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/sources" element={<Sources />} />
        <Route path="/pipelines" element={<Pipelines />} />
        <Route path="/cdm" element={<CDMExplorer />} />
        <Route path="/data-quality" element={<DataQuality />} />
        <Route path="/governance" element={<Governance />} />
      </Routes>
    </Layout>
  )
}
