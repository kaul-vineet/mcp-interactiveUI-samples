import React, { useEffect, useState } from 'react';
import { Button, Dialog, DialogActions, DialogBody, DialogContent, DialogSurface, DialogTitle, Table, TableBody, TableCell, TableHeader, TableHeaderCell, TableRow, Text, tokens } from '@fluentui/react-components';
import { CalendarRegular, DismissRegular, EditRegular, EyeRegular } from '@fluentui/react-icons';
import { useStyles, H_CELL, D_CELL } from '../styles';
import { hs } from '../theme';
import { StatusPill } from '../components/StatusPill';
import { HsViewHeader } from '../components/ViewHeader';
import { RecordDialog } from '../components/RecordDialog';
import { HsFooter } from '../components/HsFooter';

const TYPE_LABELS: Record<string, string> = {
  note: 'Notes', call: 'Calls', task: 'Tasks', meeting: 'Meetings', email: 'Emails',
};

function formatCell(apiName: string, value: any): string {
  if (!value || value === '') return '—';
  if (apiName === 'hs_timestamp' || apiName === 'hs_meeting_start_time' || apiName === 'hs_meeting_end_time') {
    try { return new Date(value).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' }); } catch { return value; }
  }
  // Truncate long bodies
  if (typeof value === 'string' && value.length > 60) return value.slice(0, 57) + '…';
  return String(value);
}

// ── ActivitiesView — schema-driven ────────────────────────────────────────
export function ActivitiesView({ items: initItems, callTool, toast, theme, cacheInfo: initCacheInfo, isFullscreen, activityType, schema }: {
  items: any[]; callTool: (n: string, a?: any) => Promise<any>;
  toast: (m: string, t?: any) => void; theme: 'light' | 'dark';
  cacheInfo?: { hit: boolean; cached_at: string }; isFullscreen?: boolean;
  activityType: string; schema: any;
}) {
  const styles = useStyles();
  const t = hs(theme);
  const [localItems, setLocalItems] = useState(initItems);
  const [cacheInfo, setCacheInfo] = useState(initCacheInfo);
  const [refreshing, setRefreshing] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});
  const [lastSavedId, setLastSavedId] = useState<string | null>(null);
  const [viewingItem, setViewingItem] = useState<any | null>(null);

  const columns = schema?.columns || [];
  const hiddenColumns = schema?.hiddenColumns || [];
  const formFields = schema?.formFields || [];
  const allViewFields = [...columns, ...hiddenColumns];

  useEffect(() => { setLocalItems(initItems); setCacheInfo(initCacheInfo); }, [initItems]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const res = await callTool('hs__get_activities', { activity_type: activityType, refresh: true });
      setLocalItems(res?.items || []);
      setCacheInfo(res?._cache);
    } catch (e: any) { toast(e.message || 'Refresh failed', 'error'); }
    finally { setRefreshing(false); }
  };

  const openView = (item: any) => { setViewingItem(item); };

  const openEdit = (item: any) => {
    setViewingItem(null);
    setEditingId(item.id);
    const f: Record<string, string> = {};
    formFields.forEach((ff: any) => { f[ff.name] = item[ff.name] || ''; });
    setForm(f);
  };
  const cancel = () => { setEditingId(null); };

  const handleSave = async () => {
    if (!editingId) return;
    setSaving(true);
    try {
      const result = await callTool('hs__update_activity', { activity_type: activityType, activity_id: editingId, ...form });
      if (result?.type === 'error' || result?.type === 'alert') {
        toast(result.message || 'Update failed', { intent: 'error' });
        setSaving(false);
        return;
      }
      if (result?.items) { setLocalItems(result.items); setCacheInfo(result?._cache); }
      toast(`${activityType} updated`); setLastSavedId(editingId);
      cancel();
    } catch (e: any) { toast(e.message || 'Failed', 'error'); }
    finally { setSaving(false); }
  };

  useEffect(() => { if (lastSavedId) { const x = setTimeout(() => setLastSavedId(null), 4800); return () => clearTimeout(x); } }, [lastSavedId]);

  const setF = (k: string, v: string) => setForm(p => ({ ...p, [k]: v }));
  const fFields = formFields.map((f: any) => ({
    label: f.label,
    key: f.name,
    value: form[f.name] || '',
    type: f.picklist ? 'select' as const : f.multiline ? 'textarea' as const : 'text' as const,
    options: f.picklist,
    onChange: (v: string) => setF(f.name, v),
  }));

  const viewFields = viewingItem ? allViewFields.map((col: any) => ({
    label: col.label, value: formatCell(col.apiName, viewingItem[col.apiName]),
  })) : [];

  const title = TYPE_LABELS[activityType] || 'Activities';

  return (
    <div className={styles.card}>
      <HsViewHeader
        icon={<CalendarRegular style={{ fontSize: '18px', color: tokens.colorBrandForeground1 }} />}
        title={title}
        count={localItems.length}
        theme={theme}
        cacheInfo={cacheInfo}
        onRefresh={isFullscreen ? handleRefresh : undefined}
        refreshing={refreshing}
      />
      <Table size="small" aria-label={title} style={{ borderCollapse: 'collapse', tableLayout: 'fixed', width: '100%' }}>
        <TableHeader>
          <TableRow style={{ background: t.headerBg }}>
            {columns.map((col: any) => (
              <TableHeaderCell key={col.apiName} style={{ ...H_CELL, color: t.textWeak }}>{col.label}</TableHeaderCell>
            ))}
            {isFullscreen && <TableHeaderCell style={{ ...H_CELL, width: 50, color: t.textWeak }} />}
          </TableRow>
        </TableHeader>
        <TableBody>
          {localItems.length === 0 && (
            <TableRow><TableCell colSpan={99} className={styles.empty}><Text>No {activityType}s found.</Text></TableCell></TableRow>
          )}
          {localItems.map((item: any) => (
            <TableRow key={item.id} className="hs-row"
              style={{ borderBottom: `1px solid ${tokens.colorNeutralStroke2}`, ...(lastSavedId === item.id ? { animation: 'hsRowFlash 2s ease-out' } : {}) }}
            >
              {columns.map((col: any) => (
                <TableCell key={col.apiName} style={{ ...D_CELL, ...(col.apiName.includes('body') || col.apiName.includes('subject') || col.apiName.includes('title') ? { fontWeight: 600 } : {}) }}>
                  {col.apiName.includes('status') || col.apiName.includes('direction') || col.apiName.includes('outcome') || col.apiName.includes('priority')
                    ? <StatusPill status={item[col.apiName] || ''} />
                    : formatCell(col.apiName, item[col.apiName])
                  }
                </TableCell>
              ))}
              {isFullscreen && (
                <TableCell style={D_CELL}>
                  <Button appearance="subtle" icon={<EyeRegular />} size="small" onClick={() => openView(item)} aria-label="View" title="View" />
                </TableCell>
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <RecordDialog
        open={editingId !== null}
        title={`Edit ${activityType}`}
        fields={fFields}
        onSave={handleSave}
        onCancel={cancel}
        saving={saving}
      />
      <Dialog open={!!viewingItem} onOpenChange={(_, data) => { if (!data.open) setViewingItem(null); }}>
        <DialogSurface style={{ maxWidth: '720px', width: '90vw', padding: '24px' }}>
          <DialogBody>
            <DialogTitle style={{ fontSize: '18px', fontWeight: 700, color: tokens.colorBrandForeground1 }}>
              {title.slice(0, -1)} Details
            </DialogTitle>
            <DialogContent style={{ paddingTop: '16px' }}>
              {viewingItem && (
                <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '10px 12px' }}>
                  {viewFields.map((field: any) => (
                    <React.Fragment key={field.label}>
                      <div style={{ color: t.textWeak, fontSize: 12, fontWeight: 600 }}>{field.label}</div>
                      <div style={{ color: t.text, fontSize: 13, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{field.value || '—'}</div>
                    </React.Fragment>
                  ))}
                </div>
              )}
            </DialogContent>
            <DialogActions style={{ paddingTop: '16px' }}>
              <Button appearance="secondary" icon={<DismissRegular />} onClick={() => setViewingItem(null)}>Close</Button>
              {viewingItem && (
                <Button appearance="primary" icon={<EditRegular />} onClick={() => openEdit(viewingItem)}>Edit</Button>
              )}
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
      <HsFooter theme={theme} />
    </div>
  );
}
