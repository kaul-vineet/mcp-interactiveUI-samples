import React from 'react';
import { Button, tokens } from '@fluentui/react-components';
import { OpenRegular } from '@fluentui/react-icons';
import { useMcpBridge } from '../../shared/McpBridge';
import { useStyles } from '../styles';

// ── HsFooter ───────────────────────────────────────────────────────────────
export function HsFooter({ theme }: { theme: 'light' | 'dark' }) {
  const styles = useStyles();
  const { openExternal } = useMcpBridge();
  return (
    <div className={styles.mcpFooter} style={{ background: tokens.colorNeutralBackground3, borderTop: `1px solid ${tokens.colorNeutralStroke2}` }}>
      <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: tokens.colorNeutralForeground3 }}>
        <span style={{ fontWeight: 600 }}>MCP</span>
        <span style={{ color: tokens.colorNeutralStroke1 }}>·</span>
        <span>HubSpot CRM</span>
      </span>
      <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
        <Button appearance="transparent" size="small" icon={<OpenRegular />} onClick={() => openExternal('https://app.hubspot.com')} aria-label="Open in HubSpot">
          Open in HubSpot
        </Button>
      </div>
    </div>
  );
}
