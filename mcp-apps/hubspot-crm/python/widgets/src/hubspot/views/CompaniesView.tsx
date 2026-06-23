import React, { useCallback, useEffect, useState } from 'react';
import { Button, Dialog, DialogActions, DialogBody, DialogContent, DialogSurface, DialogTitle, Table, TableBody, TableCell, TableHeader, TableHeaderCell, TableRow, Text, tokens } from '@fluentui/react-components';
import { BuildingRegular, ChevronDownRegular, ChevronRightRegular, DismissRegular, EditRegular, EyeRegular } from '@fluentui/react-icons';
import { useStyles, H_CELL, D_CELL } from '../styles';
import { hs } from '../theme';
import { COMPANY_FORM_FIELDS, HS_INDUSTRIES } from '../constants';
import { StatusPill } from '../components/StatusPill';
import { HsViewHeader } from '../components/ViewHeader';
import { RecordDialog } from '../components/RecordDialog';
import { HsFooter } from '../components/HsFooter';

interface CompanyDetails { contacts: any[]; deals: any[]; tickets: any[]; }

// ── CompaniesView ──────────────────────────────────────────────────────────
export function CompaniesView({ items: initItems, callTool, toast, theme, cacheInfo: initCacheInfo, isFullscreen }: {
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
  const [form, setForm] = useState({ name: '', domain: '', phone: '', city: '', industry: '' });
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [loadingExpand, setLoadingExpand] = useState<string | null>(null);
  const [companyDetails, setCompanyDetails] = useState<Record<string, CompanyDetails>>({});
  const [lastSavedId, setLastSavedId] = useState<string | null>(null);
  const [viewingCompany, setViewingCompany] = useState<any | null>(null);

  useEffect(() => { setLocalItems(initItems); setCacheInfo(initCacheInfo); }, [initItems]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const res = await callTool('hs__get_companies', { refresh: true });
      setLocalItems(res?.items || []);
      setCacheInfo(res?._cache);
    } catch (e: any) { toast(e.message || 'Refresh failed', 'error'); }
    finally { setRefreshing(false); }
  };

  const loadCompanyDetails = useCallback(async (coId: string) => {
    if (companyDetails[coId]) return companyDetails[coId];
    try {
      const [rc, rd, rt] = await Promise.all([
        callTool('hs__get_associations', { entity_type: 'companies', entity_id: coId, association_type: 'contacts' }),
        callTool('hs__get_associations', { entity_type: 'companies', entity_id: coId, association_type: 'deals' }),
        callTool('hs__get_associations', { entity_type: 'companies', entity_id: coId, association_type: 'tickets' }),
      ]);
      const details = { contacts: rc?.items || [], deals: rd?.items || [], tickets: rt?.items || [] };
      setCompanyDetails(p => ({ ...p, [coId]: details }));
      return details;
    } catch {
      const empty = { contacts: [], deals: [], tickets: [] };
      setCompanyDetails(p => ({ ...p, [coId]: empty }));
      return empty;
    }
  }, [companyDetails, callTool]);

  const toggleExpand = useCallback(async (coId: string) => {
    if (expandedId === coId) { setExpandedId(null); return; }
    setExpandedId(coId);
    if (companyDetails[coId]) return;
    setLoadingExpand(coId);
    try { await loadCompanyDetails(coId); }
    finally { setLoadingExpand(null); }
  }, [expandedId, companyDetails, loadCompanyDetails]);

  const openView = (co: any) => { setViewingCompany(co); };

  const openEdit = (co: any) => {
    setViewingCompany(null);
    setExpandedId(null);
    setEditingId(co.id);
    setForm({ name: co.name || '', domain: co.domain || '', phone: co.phone || '', city: co.city || '', industry: co.industry || '' });
  };
  const cancel = () => { setEditingId(null); };

  const handleSave = async () => {
    if (!editingId) return;
    setSaving(true);
    try {
      const result = await callTool('hs__update_company', { company_id: editingId, ...form });
      if (result?.type === 'error' || result?.type === 'alert') {
        toast(result.message || 'Update failed', { intent: 'error' });
        setSaving(false);
        return;
      }
      if (result?.items) { setLocalItems(result.items); setCacheInfo(result?._cache); }
      toast('Company updated'); setLastSavedId(editingId);
      cancel();
    } catch (e: any) { toast(e.message || 'Failed', 'error'); }
    finally { setSaving(false); }
  };

  useEffect(() => { if (lastSavedId) { const x = setTimeout(() => setLastSavedId(null), 4800); return () => clearTimeout(x); } }, [lastSavedId]);

  const setF = (k: string, v: string) => setForm(p => ({ ...p, [k]: v }));
  const fFields = COMPANY_FORM_FIELDS.map(f => ({
    ...f,
    value: (form as any)[f.key] || '',
    onChange: (v: string) => setF(f.key, v),
  }));

  const companyViewFields = viewingCompany ? [
    { label: 'Name', value: viewingCompany.name },
    { label: 'Domain', value: viewingCompany.domain },
    { label: 'Type', value: viewingCompany.type },
    { label: 'Lifecycle Stage', value: viewingCompany.lifecyclestage },
    { label: 'City', value: viewingCompany.city },
    { label: 'Phone', value: viewingCompany.phone },
    { label: 'Country', value: viewingCompany.country },
    { label: 'Description', value: viewingCompany.description },
  ] : [];

  // ── Drill-down sub-table ────────────────────────────────────────────────
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
    <div className={styles.card} style={loadingExpand ? { cursor: 'wait', pointerEvents: 'none' } : undefined}>
      <HsViewHeader
        icon={<BuildingRegular style={{ fontSize: '18px', color: tokens.colorBrandForeground1 }} />}
        title="Companies"
        count={localItems.length}
        theme={theme}
        cacheInfo={cacheInfo}
        onRefresh={isFullscreen ? handleRefresh : undefined}
        refreshing={refreshing}
      />
      <Table size="small" aria-label="Companies" style={{ borderCollapse: 'collapse', tableLayout: 'fixed', width: '100%' }}>
        <TableHeader>
          <TableRow style={{ background: t.headerBg }}>
            <TableHeaderCell style={{ ...H_CELL, width: 32 }} />
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '22%' }}>Name</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '18%' }}>Domain</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '14%' }}>Type</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '12%' }}>City</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '12%' }}>Country</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '14%' }}>Stage</TableHeaderCell>
            {isFullscreen && <TableHeaderCell style={{ ...H_CELL, width: 50, color: t.textWeak }} />}
          </TableRow>
        </TableHeader>
        <TableBody>
          {localItems.length === 0 && (
            <TableRow><TableCell colSpan={99} className={styles.empty}><Text>No companies found.</Text></TableCell></TableRow>
          )}
          {localItems.map((co: any) => (
            <React.Fragment key={co.id}>
              <TableRow className="hs-row"
                style={{ borderBottom: `1px solid ${tokens.colorNeutralStroke2}`, ...(lastSavedId === co.id ? { animation: 'hsRowFlash 2s ease-out' } : {}) }}
                aria-label={`Company: ${co.name}`}
              >
                <TableCell style={{ ...D_CELL, width: 32, padding: '6px 8px' }}>
                  <Button appearance="subtle" size="small"
                    icon={loadingExpand === co.id ? undefined : expandedId === co.id ? <ChevronDownRegular /> : <ChevronRightRegular />}
                    onClick={() => toggleExpand(co.id)}
                    aria-expanded={expandedId === co.id}
                    aria-label={`Expand ${co.name}`}
                    style={{ minWidth: 22, width: 22, height: 22, padding: 0 }}
                  >
                    {loadingExpand === co.id ? '…' : null}
                  </Button>
                </TableCell>
                <TableCell style={{ ...D_CELL, fontWeight: 600 }}>{co.name}</TableCell>
                <TableCell style={{ ...D_CELL, fontSize: 12 }}>{co.domain || '—'}</TableCell>
                <TableCell style={D_CELL}><StatusPill status={co.type || ''} /></TableCell>
                <TableCell style={D_CELL}>{co.city || '—'}</TableCell>
                <TableCell style={D_CELL}>{co.country || '—'}</TableCell>
                <TableCell style={D_CELL}>{co.lifecyclestage || '—'}</TableCell>
                {isFullscreen && (
                  <TableCell style={D_CELL}>
                    <Button appearance="subtle" icon={<EyeRegular />} size="small" onClick={() => openView(co)} aria-label={`View ${co.name}`} title="View" />
                  </TableCell>
                )}
              </TableRow>
              {expandedId === co.id && companyDetails[co.id] && (
                <TableRow>
                  <TableCell colSpan={99} style={{ padding: 0, background: t.expandedBg }}>
                    <div style={{ padding: '12px 20px 16px', borderTop: `2px solid ${tokens.colorBrandBackground}`, display: 'flex', flexDirection: 'column', gap: 16 }}>
                      <div>
                        <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: tokens.colorNeutralForeground3, marginBottom: 6 }}>Contacts</div>
                        <SubTable headers={['Name', 'Email', 'Phone']}
                          rows={companyDetails[co.id].contacts.map((ct: any) => [`${ct.firstname || ''} ${ct.lastname || ''}`.trim() || '—', ct.email || '—', ct.phone || '—'])} />
                      </div>
                      <div>
                        <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: tokens.colorNeutralForeground3, marginBottom: 6 }}>Deals</div>
                        <SubTable headers={['Deal', 'Amount', 'Stage', 'Close Date']}
                          rows={companyDetails[co.id].deals.map((d: any) => [d.dealname || '—', d.amount != null && d.amount !== '' ? '$' + Number(d.amount).toLocaleString() : '—', d.dealstage || '—', d.closedate ? new Date(d.closedate).toLocaleDateString() : '—'])} />
                      </div>
                      <div>
                        <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: tokens.colorNeutralForeground3, marginBottom: 6 }}>Tickets</div>
                        <SubTable headers={['Subject', 'Status', 'Priority']}
                          rows={companyDetails[co.id].tickets.map((tk: any) => [tk.subject || '—', tk.status || '—', tk.priority || '—'])} />
                      </div>
                    </div>
                  </TableCell>
                </TableRow>
              )}
            </React.Fragment>
          ))}
        </TableBody>
      </Table>
      <RecordDialog
        open={editingId !== null}
        title="Edit Company"
        fields={fFields}
        onSave={handleSave}
        onCancel={cancel}
        saving={saving}
      />
      <Dialog open={!!viewingCompany} onOpenChange={(_, data) => { if (!data.open) setViewingCompany(null); }}>
        <DialogSurface style={{ maxWidth: '720px', width: '90vw', padding: '24px' }}>
          <DialogBody>
            <DialogTitle style={{ fontSize: '18px', fontWeight: 700, color: tokens.colorBrandForeground1 }}>
              {viewingCompany?.name || 'Company'}
            </DialogTitle>
            <DialogContent style={{ paddingTop: '16px' }}>
              {viewingCompany && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '10px 12px' }}>
                    {companyViewFields.map(field => (
                      <React.Fragment key={field.label}>
                        <div style={{ color: t.textWeak, fontSize: 12, fontWeight: 600 }}>{field.label}</div>
                        <div style={{ color: t.text, fontSize: 13, whiteSpace: field.label === 'Description' ? 'normal' : 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{field.value || '—'}</div>
                      </React.Fragment>
                    ))}
                  </div>
                </div>
              )}
            </DialogContent>
            <DialogActions style={{ paddingTop: '16px' }}>
              <Button appearance="secondary" icon={<DismissRegular />} onClick={() => setViewingCompany(null)}>Close</Button>
              {viewingCompany && (
                <Button appearance="primary" icon={<EditRegular />} onClick={() => openEdit(viewingCompany)}>Edit</Button>
              )}
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
      <HsFooter theme={theme} />
    </div>
  );
}
