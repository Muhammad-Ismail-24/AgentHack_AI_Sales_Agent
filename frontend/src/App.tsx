import { createElement } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import DashboardLayout from './components/layout/DashboardLayout';
import { PipelineProvider, usePipeline } from './hooks/usePipeline';
import ICP from './pages/ICP';
import Inbox from './pages/Inbox';
import Landing from './pages/Landing';
import LeadDetail from './pages/LeadDetail';
import Leads from './pages/Leads';
import Meetings from './pages/Meetings';
import Onboarding from './pages/Onboarding';
import Pipeline from './pages/Pipeline';
import { loadSessionId } from './lib/utils';

export default function App() {
  // One poller for the whole dashboard, shared through context so the sidebar
  // and every top bar report the same status.
  const pipeline = usePipeline(loadSessionId());

  return createElement(
    PipelineProvider,
    { value: pipeline },
    <Routes>
      {/* Marketing front door — full screen, its own terracotta theme. */}
      <Route path="/" element={<Landing />} />
      <Route path="/onboarding" element={<Onboarding />} />
      <Route path="/icp" element={<ICP />} />

      <Route element={<DashboardLayout />}>
        <Route path="/pipeline" element={<Pipeline />} />
        <Route path="/leads" element={<Leads />} />
        <Route path="/leads/:id" element={<LeadDetail />} />
        <Route path="/inbox" element={<Inbox />} />
        <Route path="/meetings" element={<Meetings />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>,
  );
}
