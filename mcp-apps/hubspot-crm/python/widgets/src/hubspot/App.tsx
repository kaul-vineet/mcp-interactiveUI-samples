import React from 'react';
import { tokens } from '@fluentui/react-components';
import { useToolData, useMcpBridge, useTheme } from '../shared/McpBridge';
import { useToast, ToastContainer } from '../shared/Toast';
import { useStyles } from './styles';
import { SkeletonTable } from './components/SkeletonTable';
import { CompaniesView } from './views/CompaniesView';
import { ContactsView } from './views/ContactsView';
import { DealsView } from './views/DealsView';
import { OrdersView } from './views/OrdersView';
import { ProductsView } from './views/ProductsView';
import { FormView } from './views/FormView';

// ── HubSpotApp — top-level router ─────────────────────────────────────────
export default function HubSpotApp() {
  const styles = useStyles();
  const data = useToolData<any>();
  const { callTool, isFullscreen } = useMcpBridge();
  const theme = useTheme();
  const toast = useToast();

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
    case 'alert':
      // FK alert — show message in error card (persistent)
      content = (
        <div className={styles.card} style={{ padding: '24px', textAlign: 'center' }}>
          <p style={{ fontSize: '14px', fontWeight: 600, marginBottom: '8px', color: tokens.colorPaletteRedForeground1 }}>
            ⚠️ {data.title || 'Alert'}
          </p>
          <p style={{ fontSize: '13px' }}>{data.message}</p>
          {data.suggestions?.length > 0 && (
            <p style={{ fontSize: '12px', color: tokens.colorBrandForeground1, marginTop: 8 }}>
              Did you mean: {data.suggestions.join(', ')}?
            </p>
          )}
        </div>
      );
      break;
    case 'contacts':
      content = (
        <ContactsView
          items={data.items || []}
          callTool={callTool}
          toast={toast}
          theme={theme}
          cacheInfo={data._cache}
          isFullscreen={isFullscreen}
        />
      );
      break;
    case 'deals':
      content = (
        <DealsView
          items={data.items || []}
          callTool={callTool}
          toast={toast}
          theme={theme}
          cacheInfo={data._cache}
          isFullscreen={isFullscreen}
        />
      );
      break;
    case 'orders':
      content = (
        <OrdersView
          items={data.items || []}
          callTool={callTool}
          toast={toast}
          theme={theme}
          cacheInfo={data._cache}
          isFullscreen={isFullscreen}
        />
      );
      break;
    case 'products':
      content = (
        <ProductsView
          items={data.items || []}
          callTool={callTool}
          toast={toast}
          theme={theme}
          cacheInfo={data._cache}
          isFullscreen={isFullscreen}
        />
      );
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
