import { Outlet } from 'react-router-dom';

import { usePipelineContext } from '../../hooks/usePipeline';
import Sidebar from './Sidebar';

/**
 * Shell for every page behind the sidebar. The pipeline's live status is read
 * once here and shared, so the sidebar dot and each page's top bar always
 * agree rather than polling independently.
 */
export default function DashboardLayout() {
  const { isRunning } = usePipelineContext();

  return (
    <div className="min-h-full bg-slate-900">
      <Sidebar isRunning={isRunning} />
      <div className="pl-60">
        <Outlet />
      </div>
    </div>
  );
}
