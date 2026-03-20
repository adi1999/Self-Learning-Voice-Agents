import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from '@/components/Layout'
import Personas from '@/pages/Personas'
import Evolution from '@/pages/Evolution'
import Conversations from '@/pages/Conversations'
import Archive from '@/pages/Archive'
import VoiceAgent from '@/pages/VoiceAgent'
import Playbook from '@/pages/Playbook'
import Story from '@/pages/Story'
import BasePrompt from '@/pages/BasePrompt'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Story />} />
        <Route path="/personas" element={<Personas />} />
        <Route path="/evolution" element={<Evolution />} />
        <Route path="/conversations" element={<Conversations />} />
        <Route path="/archive" element={<Archive />} />
        <Route path="/voice" element={<VoiceAgent />} />
        <Route path="/playbook" element={<Playbook />} />
        <Route path="/prompt" element={<BasePrompt />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  )
}
