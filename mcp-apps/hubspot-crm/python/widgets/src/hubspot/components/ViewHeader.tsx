import React from 'react';
import { Badge, Button, tokens } from '@fluentui/react-components';
import { AddRegular, ArrowSyncRegular } from '@fluentui/react-icons';
import { ExpandButton } from '../../shared/ExpandButton';
import { timeAgo } from '../theme';

// ── ViewHeader ─────────────────────────────────────────────────────────────
export function HsViewHeader({ icon, title, count, onNew, newLabel, theme, cacheInfo, onRefresh, refreshing }: {
  icon: React.ReactNode; title: string; count: number;
  onNew?: () => void; newLabel?: string; theme: 'light' | 'dark';
  cacheInfo?: { hit: boolean; cached_at: string };
  onRefresh?: () => void; refreshing?: boolean;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderBottom: `1px solid ${tokens.colorNeutralStroke2}` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <span style={{ fontSize: '18px' }}>{icon}</span>
        <h2 style={{ margin: 0, fontSize: '14px', fontWeight: 600, color: tokens.colorNeutralForeground1 }}>{title}</h2>
        <Badge appearance="tint" color="informative" size="small" aria-label={`${count} record${count !== 1 ? 's' : ''}`}>
          {count} record{count !== 1 ? 's' : ''}
        </Badge>
        {cacheInfo && (
          <span style={{ fontSize: '12px', color: tokens.colorNeutralForeground3, display: 'flex', alignItems: 'center', gap: '8px' }}>
            {cacheInfo.hit ? `cached ${timeAgo(cacheInfo.cached_at)}` : `live ${timeAgo(cacheInfo.cached_at)}`}
            {onRefresh && (
              <Button appearance="subtle" size="small" icon={<ArrowSyncRegular />} onClick={onRefresh} disabled={refreshing} aria-label="Refresh data" title="Force refresh from HubSpot" />
            )}
          </span>
        )}
      </div>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        {onNew && (
          <Button appearance="primary" size="small" icon={<AddRegular />} onClick={onNew} aria-label={newLabel || 'New'}>
            {newLabel || 'New'}
          </Button>
        )}
        <ExpandButton />
      </div>
    </div>
  );
}
