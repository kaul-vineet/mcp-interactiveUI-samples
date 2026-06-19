import React, { useCallback, useState } from 'react';
import { Button, Table, TableBody, TableCell, TableHeader, TableHeaderCell, TableRow, Text, tokens } from '@fluentui/react-components';
import { EditRegular, PersonRegular } from '@fluentui/react-icons';
import { useStyles, H_CELL, D_CELL } from '../styles';
import { hs } from '../theme';
import { HsViewHeader } from '../components/ViewHeader';
import { RecordDialog } from '../components/RecordDialog';
import { HsFooter } from '../components/HsFooter';

// ── ContactsView (flat list, no drill-down) ───────────────────────────────
export function ContactsView({ items: initItems, callTool, toast, theme, cacheInfo: initCacheInfo, isFullscreen }: {
  items: any[]; callTool: (n: string, a?: any) => Promise<any>;
  toast: (m: string, t?: any) => void; theme: 'light' | 'dark';
  cacheInfo?: { hit: boolean; cached_at: string }; isFullscreen?: boolean;
}) {
  const styles = useStyles();
  const t = hs(theme);
  const [localItems, setLocalItems] = useState(initItems);
  const [cacheInfo, setCacheInfo] = useState(initCacheInfo);
  const [refreshing, setRefreshing] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [lastSavedId, setLastSavedId] = useState<string | null>(null);

  // ── Refresh ───────────────────────────────────────────────────────────────
  const handleRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      const res = await callTool('hs__get_contacts', { refresh: true });
      if (res?.items) { setLocalItems(res.items); setCacheInfo(res._cache); }
    } catch { toast('Refresh failed', { intent: 'error' }); }
    setRefreshing(false);
  }, [callTool, toast]);

  // ── Save (edit) ───────────────────────────────────────────────────────────
  const handleSave = useCallback(async (fields: Record<string, string>) => {
    if (!editingId) return;
    setSaving(true);
    try {
      const res = await callTool('hs__update_contact', { contact_id: editingId, ...fields });
      if (res?.items) { setLocalItems(res.items); setCacheInfo(res._cache); }
      setLastSavedId(editingId);
      setTimeout(() => setLastSavedId(null), 2200);
      toast('Contact updated');
      setEditingId(null);
    } catch { toast('Save failed', { intent: 'error' }); }
    setSaving(false);
  }, [editingId, callTool, toast]);

  const openEdit = (co: any) => setEditingId(co.id);

  // ── Edit dialog field definitions ─────────────────────────────────────────
  const CONTACT_EDIT_FIELDS = [
    { name: 'firstname', label: 'First Name', required: true },
    { name: 'lastname', label: 'Last Name', required: true },
    { name: 'email', label: 'Email', required: true },
    { name: 'phone', label: 'Phone' },
    { name: 'jobtitle', label: 'Job Title' },
    { name: 'lifecyclestage', label: 'Lifecycle Stage', picklist: ['subscriber', 'lead', 'marketingqualifiedlead', 'salesqualifiedlead', 'opportunity', 'customer', 'evangelist', 'other'] },
    { name: 'city', label: 'City' },
  ];

  const editingRecord = localItems.find((c: any) => c.id === editingId);

  return (
    <div className={styles.root}>
      <HsViewHeader
        icon={<PersonRegular style={{ fontSize: 18, color: tokens.colorBrandForeground1 }} />}
        title="Contacts"
        count={localItems.length}
        cacheInfo={cacheInfo}
        onRefresh={isFullscreen ? handleRefresh : undefined}
        refreshing={refreshing}
      />
      <Table size="small" aria-label="Contacts" style={{ borderCollapse: 'collapse', tableLayout: 'fixed', width: '100%' }}>
        <TableHeader>
          <TableRow style={{ background: t.headerBg }}>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '22%' }}>Name</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '28%' }}>Email</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '18%' }}>Phone</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '22%' }}>Company</TableHeaderCell>
            {isFullscreen && <TableHeaderCell style={{ ...H_CELL, width: 60, color: t.textWeak }} />}
          </TableRow>
        </TableHeader>
        <TableBody>
          {localItems.length === 0 && (
            <TableRow><TableCell colSpan={99} className={styles.empty}><Text>No contacts found.</Text></TableCell></TableRow>
          )}
          {localItems.map((ct: any) => (
            <TableRow key={ct.id} className="hs-row"
              style={{ borderBottom: `1px solid ${tokens.colorNeutralStroke2}`, ...(lastSavedId === ct.id ? { animation: 'hsRowFlash 2s ease-out' } : {}) }}
              aria-label={`Contact: ${ct.firstname} ${ct.lastname}`}
            >
              <TableCell style={{ ...D_CELL, fontWeight: 600 }}>{`${ct.firstname || ''} ${ct.lastname || ''}`.trim() || '—'}</TableCell>
              <TableCell style={{ ...D_CELL, fontSize: 12 }}>{ct.email || '—'}</TableCell>
              <TableCell style={D_CELL}>{ct.phone || '—'}</TableCell>
              <TableCell style={{ ...D_CELL, color: tokens.colorBrandForeground1 }}>{ct.company || '—'}</TableCell>
              {isFullscreen && (
                <TableCell style={D_CELL}>
                  <Button appearance="subtle" icon={<EditRegular />} size="small" onClick={() => openEdit(ct)} aria-label={`Edit ${ct.firstname} ${ct.lastname}`} title="Edit" />
                </TableCell>
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <HsFooter />

      {editingRecord && (
        <RecordDialog
          open={!!editingId}
          title={`Edit Contact: ${editingRecord.firstname} ${editingRecord.lastname}`}
          fields={CONTACT_EDIT_FIELDS}
          initialValues={editingRecord}
          saving={saving}
          onSave={handleSave}
          onCancel={() => setEditingId(null)}
        />
      )}
    </div>
  );
}
