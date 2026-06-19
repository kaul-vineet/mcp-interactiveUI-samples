import React, { useCallback, useEffect, useState } from 'react';
import { Button, Table, TableBody, TableCell, TableHeader, TableHeaderCell, TableRow, Text, tokens } from '@fluentui/react-components';
import { BuildingRegular, ChevronDownRegular, ChevronRightRegular, EditRegular } from '@fluentui/react-icons';
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
  const [creating, setCreating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({ name: '', domain: '', phone: '', city: '', industry: '' });
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [loadingExpand, setLoadingExpand] = useState<string | null>(null);
  const [companyDetails, setCompanyDetails] = useState<Record<string, CompanyDetails>>({});
  const [lastSavedId, setLastSavedId] = useState<string | null>(null);

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

  const toggleExpand = useCallback(async (coId: string) => {
    if (expandedId === coId) { setExpandedId(null); return; }
    setExpandedId(coId);
    if (companyDetails[coId]) return;
    setLoadingExpand(coId);
    try {
      const [rc, rd, rt] = await Promise.all([
        callTool('hs__get_company_contacts', { company_id: coId }),
        callTool('hs__get_company_deals', { company_id: coId }),
        callTool('hs__get_company_tickets', { company_id: coId }),
      ]);
      setCompanyDetails(p => ({ ...p, [coId]: { contacts: rc?.items || [], deals: rd?.items || [], tickets: rt?.items || [] } }));
    } catch { setCompanyDetails(p => ({ ...p, [coId]: { contacts: [], deals: [], tickets: [] } })); }
    finally { setLoadingExpand(null); }
  }, [expandedId, companyDetails, callTool]);

  const openEdit = (co: any) => { setCreating(false); setExpandedId(null); setEditingId(co.id); setForm({ name: co.name || '', domain: co.domain || '', phone: co.phone || '', city: co.city || '', industry: co.industry || '' }); };
  const openCreate = () => { setEditingId(null); setCreating(true); setForm({ name: '', domain: '', phone: '', city: '', industry: '' }); };
  const cancel = () => { setEditingId(null); setCreating(false); };

  const handleSave = async () => {
    setSaving(true);
    try {
      let result: any;
      if (creating) { result = await callTool('hs__create_company', form); toast('Company created'); }
      else { result = await callTool('hs__update_company', { company_id: editingId, ...form }); toast('Company updated'); setLastSavedId(editingId); }
      if (result?.items) { setLocalItems(result.items); setCacheInfo(result?._cache); }
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
    <div className={styles.card}>
      <HsViewHeader
        icon={<BuildingRegular style={{ fontSize: '18px', color: tokens.colorBrandForeground1 }} />}
        title="Companies"
        count={localItems.length}
        theme={theme}
        cacheInfo={cacheInfo}
        onRefresh={isFullscreen ? handleRefresh : undefined}
        refreshing={refreshing}
      />
      <Table size="small" aria-label="Companies" style={{ borderCollapse: 'collapse' }}>
        <TableHeader>
          <TableRow style={{ background: t.headerBg }}>
            <TableHeaderCell style={{ ...H_CELL, width: 28 }} />
            {['Name', 'Type', 'City', 'Lifecycle Stage'].map(h => (
              <TableHeaderCell key={h} style={{ ...H_CELL, color: t.textWeak }}>{h}</TableHeaderCell>
            ))}
            {isFullscreen && <TableHeaderCell style={{ ...H_CELL, width: 80, color: t.textWeak }} />}
          </TableRow>
        </TableHeader>
        <TableBody>
          {localItems.length === 0 && !creating && (
            <TableRow><TableCell colSpan={99} className={styles.empty}><Text>No companies found.</Text></TableCell></TableRow>
          )}
          {localItems.map((co: any) => (
            <React.Fragment key={co.id}>
              <TableRow className="hs-row"
                style={{ borderBottom: `1px solid ${tokens.colorNeutralStroke2}`, ...(lastSavedId === co.id ? { animation: 'hsRowFlash 2s ease-out' } : {}) }}
                aria-label={`Company: ${co.name}`}
              >
                <TableCell style={{ ...D_CELL, width: 28, padding: '6px 8px' }}>
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
                <TableCell style={D_CELL}><StatusPill status={co.type || ''} /></TableCell>
                <TableCell style={D_CELL}>{co.city || '—'}</TableCell>
                <TableCell style={D_CELL}>{co.lifecyclestage || '—'}</TableCell>
                {isFullscreen && (
                  <TableCell style={D_CELL}>
                    <Button appearance="subtle" icon={<EditRegular />} size="small" onClick={() => openEdit(co)} aria-label={`Edit ${co.name}`} title="Edit" />
                  </TableCell>
                )}
              </TableRow>
              {expandedId === co.id && companyDetails[co.id] && (
                <TableRow>
                  <TableCell colSpan={99} style={{ padding: 0, background: t.expandedBg }}>
                    <div style={{ padding: '12px 20px 16px', borderTop: `2px solid ${tokens.colorBrandBackground}`, display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16 }}>
                      <div>
                        <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: tokens.colorNeutralForeground3, marginBottom: 6 }}>Contacts</div>
                        <SubTable headers={['Name', 'Email']}
                          rows={companyDetails[co.id].contacts.map((ct: any) => [`${ct.firstname || ''} ${ct.lastname || ''}`.trim() || '—', ct.email || '—'])} />
                      </div>
                      <div>
                        <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: tokens.colorNeutralForeground3, marginBottom: 6 }}>Deals</div>
                        <SubTable headers={['Deal', 'Amount']}
                          rows={companyDetails[co.id].deals.map((d: any) => [d.dealname || '—', d.amount != null ? '$' + Number(d.amount).toLocaleString() : '—'])} />
                      </div>
                      <div>
                        <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: tokens.colorNeutralForeground3, marginBottom: 6 }}>Tickets</div>
                        <SubTable headers={['Subject', 'Status']}
                          rows={companyDetails[co.id].tickets.map((tk: any) => [tk.subject || '—', tk.status || '—'])} />
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
        open={editingId !== null || creating}
        title={creating ? 'New Company' : 'Edit Company'}
        fields={fFields}
        onSave={handleSave}
        onCancel={cancel}
        saving={saving}
      />
      <HsFooter theme={theme} />
    </div>
  );
}
