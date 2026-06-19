import React from 'react';
import { useMcpBridge } from './McpBridge';

export function McpFooter({ label, openInUrl, openInLabel }: { label: string; openInUrl?: string; openInLabel?: string }) {
  const { openExternal } = useMcpBridge();

  return (
    <div style={{
      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      padding: '8px 0', marginTop: '12px', borderTop: '1px solid #e0e0e0',
      fontSize: '11px', opacity: 0.7, color: '#605e5c'
    }}>
      <span>⚡ <strong>MCP Widget</strong> · {label}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        {openInUrl && (
          <span
            style={{ cursor: 'pointer', textDecoration: 'underline' }}
            onClick={() => openExternal(openInUrl)}
          >
            {openInLabel || 'Open in portal'} ↗
          </span>
        )}
        <span>⚓ GTC</span>
      </div>
    </div>
  );
}
