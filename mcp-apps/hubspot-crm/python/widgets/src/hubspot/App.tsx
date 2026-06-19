import React from 'react';
import { useToolData, useMcpBridge, useTheme } from '../shared/McpBridge';
import { useToast } from '../shared/Toast';
import { useStyles } from './styles';
import { SkeletonTable } from './components/SkeletonTable';
import { CompaniesView } from './views/CompaniesView';
import { FormView } from './views/FormView';

// ── HubSpotApp — top-level router ─────────────────────────────────────────
export default function HubSpotApp() {
  const styles = useStyles();
  const data = useToolData<any>();
  const { callTool, isFullscreen } = useMcpBridge();
  const theme = useTheme();
  const { ToastContainer, toast } = useToast();

  // No data yet — skeleton loading state
  if (!data) {
    return (
      <div className={styles.shell}>
        <SkeletonTable />
        <ToastContainer />
      </div>
    );
  }

  // Error from server
  if (data.error) {
    return (
      <div className={styles.shell}>
        <div className={styles.card} style={{ padding: '24px', textAlign: 'center' }}>
          <p style={{ fontSize: '14px', fontWeight: 600, marginBottom: '8px' }}>⚠️ Error</p>
          <p style={{ fontSize: '13px' }}>{data.message || data.error}</p>
        </div>
        <ToastContainer />
      </div>
    );
  }

  // Route based on data.type
  let content: React.ReactNode;
  switch (data.type) {
    case 'form':
      content = <FormView data={data} callTool={callTool} toast={toast} theme={theme} />;
      break;
    case 'companies':
    default:
      content = (
        <CompaniesView
          items={data.items || []}
          callTool={callTool}
          toast={toast}
          theme={theme}
          cacheInfo={data._cache}
          isFullscreen={isFullscreen}
        />
      );
      break;
  }

  return (
    <div className={styles.shell}>
      {content}
      <ToastContainer />
    </div>
  );
}
