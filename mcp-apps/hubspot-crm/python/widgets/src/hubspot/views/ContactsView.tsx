import React, { useCallback, useState } from 'react';
import { Button, Dialog, DialogActions, DialogBody, DialogContent, DialogSurface, DialogTitle, Table, TableBody, TableCell, TableHeader, TableHeaderCell, TableRow, Text, tokens } from '@fluentui/react-components';
import { ChevronDownRegular, ChevronRightRegular, DismissRegular, EditRegular, EyeRegular, PersonRegular } from '@fluentui/react-icons';
import { useStyles, H_CELL, D_CELL } from '../styles';
import { hs } from '../theme';
import { HsViewHeader } from '../components/ViewHeader';
import { RecordDialog } from '../components/RecordDialog';
import { HsFooter } from '../components/HsFooter';

interface ContactDetails { companies: any[]; deals: any[]; tickets: any[]; }

// ── ContactsView (list + RO detail with drill-down) ───────────────────────
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
  const [form, setForm] = useState<Record<string, string>>({});
  const [viewingContact, setViewingContact] = useState<any | null>(null);
  const [contactDetails, setContactDetails] = useState<Record<string, ContactDetails>>({});
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [loadingExpand, setLoadingExpand] = useState<string | null>(null);

  // ── Edit dialog field definitions ─────────────────────────────────────────
  const CONTACT_EDIT_FIELDS = [
    { key: 'firstname', label: 'First Name' },
    { key: 'lastname', label: 'Last Name' },
    { key: 'email', label: 'Email' },
    { key: 'phone', label: 'Phone' },
    { key: 'jobtitle', label: 'Job Title' },
    { key: 'lifecyclestage', label: 'Lifecycle Stage', type: 'select' as const, options: ['subscriber', 'lead', 'marketingqualifiedlead', 'salesqualifiedlead', 'opportunity', 'customer', 'evangelist', 'other'] },
    { key: 'city', label: 'City' },
  ];

  const setF = (k: string, v: string) => setForm(p => ({ ...p, [k]: v }));
  const fFields = CONTACT_EDIT_FIELDS.map(f => ({
    ...f,
    value: form[f.key] || '',
    onChange: (v: string) => setF(f.key, v),
  }));

  // ── Load associated records ────────────────────────────────────────────────
  const loadContactDetails = useCallback(async (ctId: string) => {
    if (contactDetails[ctId]) return contactDetails[ctId];
    try {
      const [rc, rd, rt] = await Promise.all([
        callTool('hs__get_associations', { entity_type: 'contacts', entity_id: ctId, association_type: 'companies' }),
        callTool('hs__get_associations', { entity_type: 'contacts', entity_id: ctId, association_type: 'deals' }),
        callTool('hs__get_associations', { entity_type: 'contacts', entity_id: ctId, association_type: 'tickets' }),
      ]);
      const details = { companies: rc?.items || [], deals: rd?.items || [], tickets: rt?.items || [] };
      setContactDetails(p => ({ ...p, [ctId]: details }));
      return details;
    } catch {
      const empty = { companies: [], deals: [], tickets: [] };
      setContactDetails(p => ({ ...p, [ctId]: empty }));
      return empty;
    }
  }, [contactDetails, callTool]);

  const toggleExpand = useCallback(async (ctId: string) => {
    if (expandedId === ctId) { setExpandedId(null); return; }
    setExpandedId(ctId);
    if (contactDetails[ctId]) return;
    setLoadingExpand(ctId);
    try { await loadContactDetails(ctId); }
    finally { setLoadingExpand(null); }
  }, [expandedId, contactDetails, loadContactDetails]);

  const openView = (ct: any) => { setViewingContact(ct); };

  // ── Refresh ───────────────────────────────────────────────────────────────
  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const res = await callTool('hs__get_contacts', { refresh: true });
      if (res?.items) { setLocalItems(res.items); setCacheInfo(res._cache); }
    } catch { toast('Refresh failed', { intent: 'error' }); }
    setRefreshing(false);
  };

  // ── Save (edit) ───────────────────────────────────────────────────────────
  const handleSave = async () => {
    if (!editingId) return;
    setSaving(true);
    try {
      const res = await callTool('hs__update_contact', { contact_id: editingId, ...form });
      if (res?.type === 'error' || res?.type === 'alert') {
        toast(res.message || 'Update failed', { intent: 'error' });
        setSaving(false);
        return;
      }
      if (res?.items) { setLocalItems(res.items); setCacheInfo(res._cache); }
      setLastSavedId(editingId);
      setTimeout(() => setLastSavedId(null), 2200);
      toast('Contact updated');
      setEditingId(null);
    } catch { toast('Save failed', { intent: 'error' }); }
    finally { setSaving(false); }
  };

  const openEdit = (ct: any) => {
    setViewingContact(null);
    setForm({
      firstname: ct.firstname || '',
      lastname: ct.lastname || '',
      email: ct.email || '',
      phone: ct.phone || '',
      jobtitle: ct.jobtitle || '',
      lifecyclestage: ct.lifecyclestage || '',
      city: ct.city || '',
    });
    setEditingId(ct.id);
  };

  const editingRecord = localItems.find((c: any) => c.id === editingId);
  const contactViewFields = viewingContact ? [
    { label: 'First Name', value: viewingContact.firstname },
    { label: 'Last Name', value: viewingContact.lastname },
    { label: 'Email', value: viewingContact.email },
    { label: 'Phone', value: viewingContact.phone },
    { label: 'Job Title', value: viewingContact.jobtitle },
    { label: 'City', value: viewingContact.city },
    { label: 'Lifecycle Stage', value: viewingContact.lifecyclestage },
    { label: 'Company', value: viewingContact.company },
  ] : [];

  // ── Sub-table for drill-down sections ──────────────────────────────────────
  const SubTable = ({ headers, rows }: { headers: string[]; rows: React.ReactNode[][] }) => (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }} role="table">
      <thead>
        <tr style={{ backgroundColor: tokens.colorNeutralBackground3 }}>
          {headers.map(h => <th key={h} style={{ padding: '4px 10px', textAlign: 'left', color: tokens.colorNeutralForeground3, borderBottom: `1px solid ${tokens.colorNeutralStroke2}`, fontWeight: 600 }}>{h}</th>)}
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 ? (
          <tr><td colSpan={headers.length} style={{ padding: '6px 10px', color: tokens.colorNeutralForeground3, fontStyle: 'italic' }}>None</td></tr>
        ) : rows.map((cells, i) => (
          <tr key={i} style={{ borderBottom: `1px solid ${tokens.colorNeutralStroke2}` }}>
            {cells.map((cell, j) => <td key={j} style={{ padding: '4px 10px', color: j === 0 ? tokens.colorNeutralForeground1 : tokens.colorNeutralForeground3 }}>{cell}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  );

  return (
    <div className={styles.root} style={loadingExpand ? { cursor: 'wait', pointerEvents: 'none' } : undefined}>
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
            <TableHeaderCell style={{ ...H_CELL, width: 32 }} />
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '16%' }}>Name</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '18%' }}>Email</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '12%' }}>Phone</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '14%' }}>Job Title</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '10%' }}>City</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '10%' }}>Stage</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '12%' }}>Company</TableHeaderCell>
            {isFullscreen && <TableHeaderCell style={{ ...H_CELL, width: 50, color: t.textWeak }} />}
          </TableRow>
        </TableHeader>
        <TableBody>
          {localItems.length === 0 && (
            <TableRow><TableCell colSpan={99} className={styles.empty}><Text>No contacts found.</Text></TableCell></TableRow>
          )}
          {localItems.map((ct: any) => (
            <React.Fragment key={ct.id}>
              <TableRow className="hs-row"
                style={{ borderBottom: `1px solid ${tokens.colorNeutralStroke2}`, ...(lastSavedId === ct.id ? { animation: 'hsRowFlash 2s ease-out' } : {}) }}
                aria-label={`Contact: ${ct.firstname} ${ct.lastname}`}
              >
                <TableCell style={{ ...D_CELL, width: 32, padding: '6px 8px' }}>
                  <Button appearance="subtle" size="small"
                    icon={loadingExpand === ct.id ? undefined : expandedId === ct.id ? <ChevronDownRegular /> : <ChevronRightRegular />}
                    onClick={() => toggleExpand(ct.id)}
                    aria-expanded={expandedId === ct.id}
                    aria-label={`Expand ${ct.firstname} ${ct.lastname}`}
                    style={{ minWidth: 22, width: 22, height: 22, padding: 0 }}
                  >
                    {loadingExpand === ct.id ? '…' : null}
                  </Button>
                </TableCell>
                <TableCell style={{ ...D_CELL, fontWeight: 600 }}>{`${ct.firstname || ''} ${ct.lastname || ''}`.trim() || '—'}</TableCell>
                <TableCell style={{ ...D_CELL, fontSize: 12 }}>{ct.email || '—'}</TableCell>
                <TableCell style={D_CELL}>{ct.phone || '—'}</TableCell>
                <TableCell style={D_CELL}>{ct.jobtitle || '—'}</TableCell>
                <TableCell style={D_CELL}>{ct.city || '—'}</TableCell>
                <TableCell style={D_CELL}>{ct.lifecyclestage || '—'}</TableCell>
                <TableCell style={{ ...D_CELL, color: tokens.colorBrandForeground1 }}>{ct.company || '—'}</TableCell>
                {isFullscreen && (
                  <TableCell style={D_CELL}>
                    <Button appearance="subtle" icon={<EyeRegular />} size="small" onClick={() => openView(ct)} aria-label={`View ${ct.firstname} ${ct.lastname}`} title="View" />
                  </TableCell>
                )}
              </TableRow>
              {expandedId === ct.id && contactDetails[ct.id] && (
                <TableRow>
                  <TableCell colSpan={99} style={{ padding: 0, background: t.expandedBg }}>
                    <div style={{ padding: '12px 20px 16px', borderTop: `2px solid ${tokens.colorBrandBackground}`, display: 'flex', flexDirection: 'column', gap: 16 }}>
                      <div>
                        <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: tokens.colorNeutralForeground3, marginBottom: 6 }}>Companies</div>
                        <SubTable headers={['Name', 'Domain', 'City', 'Industry']}
                          rows={contactDetails[ct.id].companies.map((co: any) => [co.name || '—', co.domain || '—', co.city || '—', co.industry || '—'])} />
                      </div>
                      <div>
                        <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: tokens.colorNeutralForeground3, marginBottom: 6 }}>Deals</div>
                        <SubTable headers={['Deal', 'Amount', 'Stage', 'Close Date']}
                          rows={contactDetails[ct.id].deals.map((d: any) => [d.dealname || '—', d.amount != null && d.amount !== '' ? '$' + Number(d.amount).toLocaleString() : '—', d.dealstage || '—', d.closedate ? new Date(d.closedate).toLocaleDateString() : '—'])} />
                      </div>
                      <div>
                        <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: tokens.colorNeutralForeground3, marginBottom: 6 }}>Tickets</div>
                        <SubTable headers={['Subject', 'Status', 'Priority']}
                          rows={contactDetails[ct.id].tickets.map((tk: any) => [tk.subject || '—', tk.status || '—', tk.priority || '—'])} />
                      </div>
                    </div>
                  </TableCell>
                </TableRow>
              )}
            </React.Fragment>
          ))}
        </TableBody>
      </Table>
      <HsFooter />

      {editingRecord && (
        <RecordDialog
          open={!!editingId}
          title={`Edit Contact: ${editingRecord.firstname} ${editingRecord.lastname}`}
          fields={fFields}
          saving={saving}
          onSave={handleSave}
          onCancel={() => setEditingId(null)}
          mode="edit"
        />
      )}
      <Dialog open={!!viewingContact} onOpenChange={(_, data) => { if (!data.open) setViewingContact(null); }}>
        <DialogSurface style={{ maxWidth: '720px', width: '90vw', padding: '24px' }}>
          <DialogBody>
            <DialogTitle style={{ fontSize: '18px', fontWeight: 700, color: tokens.colorBrandForeground1 }}>
              {`${viewingContact?.firstname || ''} ${viewingContact?.lastname || ''}`.trim() || 'Contact'}
            </DialogTitle>
            <DialogContent style={{ paddingTop: '16px' }}>
              {viewingContact && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '10px 12px' }}>
                    {contactViewFields.map(field => (
                      <React.Fragment key={field.label}>
                        <div style={{ color: t.textWeak, fontSize: 12, fontWeight: 600 }}>{field.label}</div>
                        <div style={{ color: field.label === 'Company' ? tokens.colorBrandForeground1 : t.text, fontSize: 13 }}>{field.value || '—'}</div>
                      </React.Fragment>
                    ))}
                  </div>
                </div>
              )}
            </DialogContent>
            <DialogActions style={{ paddingTop: '16px' }}>
              <Button appearance="secondary" icon={<DismissRegular />} onClick={() => setViewingContact(null)}>Close</Button>
              {viewingContact && (
                <Button appearance="primary" icon={<EditRegular />} onClick={() => openEdit(viewingContact)}>Edit</Button>
              )}
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </div>
  );
}
