import React, { useCallback, useState } from 'react';
import { Button, Dialog, DialogActions, DialogBody, DialogContent, DialogSurface, DialogTitle, Table, TableBody, TableCell, TableHeader, TableHeaderCell, TableRow, Text, tokens } from '@fluentui/react-components';
import { ChevronDownRegular, ChevronRightRegular, DismissRegular, EditRegular, EyeRegular, MoneyRegular } from '@fluentui/react-icons';
import { useStyles, H_CELL, D_CELL } from '../styles';
import { hs } from '../theme';
import { HsViewHeader } from '../components/ViewHeader';
import { RecordDialog } from '../components/RecordDialog';
import { HsFooter } from '../components/HsFooter';

interface DealDetails { contacts: any[]; companies: any[]; tickets: any[]; }

// Stage ID → label mapping (matches server stageLabels)
const STAGE_LABELS: Record<string, string> = {
  '3442945774': 'Lead Captured',
  '3442945775': 'Qualified',
  '3442945776': 'Proposal Sent',
  '3442945777': 'Negotiation',
  'closedwon': 'Closed Won',
  'closedlost': 'Closed Lost',
};

function stageLabel(id: string): string {
  return STAGE_LABELS[id] || id;
}

function fmtAmount(amt: string | number | undefined): string {
  if (amt == null || amt === '') return '—';
  const n = Number(amt);
  return isNaN(n) ? String(amt) : '$' + n.toLocaleString();
}

function fmtDate(d: string | undefined): string {
  if (!d) return '—';
  try { return new Date(d).toLocaleDateString(); } catch { return d; }
}

// ── DealsView ──────────────────────────────────────────────────────────────
export function DealsView({ items: initItems, callTool, toast, theme, cacheInfo: initCacheInfo, isFullscreen }: {
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
  const [viewingDeal, setViewingDeal] = useState<any | null>(null);
  const [dealDetails, setDealDetails] = useState<Record<string, DealDetails>>({});
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [loadingExpand, setLoadingExpand] = useState<string | null>(null);

  const DEAL_EDIT_FIELDS = [
    { key: 'dealname', label: 'Deal Name' },
    { key: 'amount', label: 'Amount' },
    { key: 'pipeline', label: 'Pipeline', type: 'select' as const, options: ['default'] },
    { key: 'dealstage', label: 'Stage', type: 'select' as const, options: Object.keys(STAGE_LABELS) },
    { key: 'closedate', label: 'Close Date' },
    { key: 'dealtype', label: 'Deal Type', type: 'select' as const, options: ['newbusiness', 'existingbusiness'] },
    { key: 'description', label: 'Description' },
  ];

  const setF = (k: string, v: string) => setForm(p => ({ ...p, [k]: v }));
  const fFields = DEAL_EDIT_FIELDS.map(f => ({
    ...f,
    value: form[f.key] || '',
    onChange: (v: string) => setF(f.key, v),
  }));

  // ── Load associated records ────────────────────────────────────────────────
  const loadDealDetails = useCallback(async (dealId: string) => {
    if (dealDetails[dealId]) return dealDetails[dealId];
    try {
      const [rc, rco, rt] = await Promise.all([
        callTool('hs__get_associations', { entity_type: 'deals', entity_id: dealId, association_type: 'contacts' }),
        callTool('hs__get_associations', { entity_type: 'deals', entity_id: dealId, association_type: 'companies' }),
        callTool('hs__get_associations', { entity_type: 'deals', entity_id: dealId, association_type: 'tickets' }),
      ]);
      const details = { contacts: rc?.items || [], companies: rco?.items || [], tickets: rt?.items || [] };
      setDealDetails(p => ({ ...p, [dealId]: details }));
      return details;
    } catch {
      const empty = { contacts: [], companies: [], tickets: [] };
      setDealDetails(p => ({ ...p, [dealId]: empty }));
      return empty;
    }
  }, [dealDetails, callTool]);

  const toggleExpand = useCallback(async (dealId: string) => {
    if (expandedId === dealId) { setExpandedId(null); return; }
    setExpandedId(dealId);
    if (dealDetails[dealId]) return;
    setLoadingExpand(dealId);
    try { await loadDealDetails(dealId); }
    finally { setLoadingExpand(null); }
  }, [expandedId, dealDetails, loadDealDetails]);

  const openView = (deal: any) => { setViewingDeal(deal); };

  // ── Refresh ───────────────────────────────────────────────────────────────
  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const res = await callTool('hs__get_deals', { refresh: true });
      if (res?.items) { setLocalItems(res.items); setCacheInfo(res._cache); }
    } catch { toast('Refresh failed', { intent: 'error' }); }
    setRefreshing(false);
  };

  // ── Save (edit) ───────────────────────────────────────────────────────────
  const handleSave = async () => {
    if (!editingId) return;
    setSaving(true);
    try {
      const res = await callTool('hs__update_deal', { deal_id: editingId, ...form });
      if (res?.type === 'error' || res?.type === 'alert') {
        toast(res.message || 'Update failed', { intent: 'error' });
        setSaving(false);
        return;
      }
      if (res?.items) { setLocalItems(res.items); setCacheInfo(res._cache); }
      setLastSavedId(editingId);
      setTimeout(() => setLastSavedId(null), 2200);
      toast('Deal updated');
      setEditingId(null);
    } catch { toast('Save failed', { intent: 'error' }); }
    finally { setSaving(false); }
  };

  const openEdit = (deal: any) => {
    setViewingDeal(null);
    setForm({
      dealname: deal.dealname || '',
      amount: deal.amount || '',
      pipeline: deal.pipeline || 'default',
      dealstage: deal.dealstage || '',
      closedate: deal.closedate || '',
      dealtype: deal.dealtype || '',
      description: deal.description || '',
    });
    setEditingId(deal.id);
  };

  const editingRecord = localItems.find((d: any) => d.id === editingId);
  const dealViewFields = viewingDeal ? [
    { label: 'Deal Name', value: viewingDeal.dealname },
    { label: 'Amount', value: fmtAmount(viewingDeal.amount) },
    { label: 'Stage', value: stageLabel(viewingDeal.dealstage || '') },
    { label: 'Pipeline', value: viewingDeal.pipeline },
    { label: 'Close Date', value: fmtDate(viewingDeal.closedate) },
    { label: 'Deal Type', value: viewingDeal.dealtype || '—' },
    { label: 'Company', value: viewingDeal.company },
    { label: 'Description', value: viewingDeal.description },
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
        icon={<MoneyRegular style={{ fontSize: 18, color: tokens.colorBrandForeground1 }} />}
        title="Deals"
        count={localItems.length}
        cacheInfo={cacheInfo}
        onRefresh={isFullscreen ? handleRefresh : undefined}
        refreshing={refreshing}
      />
      <Table size="small" aria-label="Deals" style={{ borderCollapse: 'collapse', tableLayout: 'fixed', width: '100%' }}>
        <TableHeader>
          <TableRow style={{ background: t.headerBg }}>
            <TableHeaderCell style={{ ...H_CELL, width: 32 }} />
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '22%' }}>Deal Name</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '14%' }}>Amount</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '16%' }}>Stage</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '12%' }}>Pipeline</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '14%' }}>Close Date</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '16%' }}>Company</TableHeaderCell>
            {isFullscreen && <TableHeaderCell style={{ ...H_CELL, width: 50, color: t.textWeak }} />}
          </TableRow>
        </TableHeader>
        <TableBody>
          {localItems.length === 0 && (
            <TableRow><TableCell colSpan={99} className={styles.empty}><Text>No deals found.</Text></TableCell></TableRow>
          )}
          {localItems.map((deal: any) => (
            <React.Fragment key={deal.id}>
              <TableRow className="hs-row"
                style={{ borderBottom: `1px solid ${tokens.colorNeutralStroke2}`, ...(lastSavedId === deal.id ? { animation: 'hsRowFlash 2s ease-out' } : {}) }}
                aria-label={`Deal: ${deal.dealname}`}
              >
                <TableCell style={{ ...D_CELL, width: 32, padding: '6px 8px' }}>
                  <Button appearance="subtle" size="small"
                    icon={loadingExpand === deal.id ? undefined : expandedId === deal.id ? <ChevronDownRegular /> : <ChevronRightRegular />}
                    onClick={() => toggleExpand(deal.id)}
                    aria-expanded={expandedId === deal.id}
                    aria-label={`Expand ${deal.dealname}`}
                    style={{ minWidth: 22, width: 22, height: 22, padding: 0 }}
                  >
                    {loadingExpand === deal.id ? '…' : null}
                  </Button>
                </TableCell>
                <TableCell style={{ ...D_CELL, fontWeight: 600 }}>{deal.dealname || '—'}</TableCell>
                <TableCell style={D_CELL}>{fmtAmount(deal.amount)}</TableCell>
                <TableCell style={D_CELL}>{stageLabel(deal.dealstage || '')}</TableCell>
                <TableCell style={D_CELL}>{deal.pipeline || '—'}</TableCell>
                <TableCell style={D_CELL}>{fmtDate(deal.closedate)}</TableCell>
                <TableCell style={{ ...D_CELL, color: tokens.colorBrandForeground1 }}>{deal.company || '—'}</TableCell>
                {isFullscreen && (
                  <TableCell style={D_CELL}>
                    <Button appearance="subtle" icon={<EyeRegular />} size="small" onClick={() => openView(deal)} aria-label={`View ${deal.dealname}`} title="View" />
                  </TableCell>
                )}
              </TableRow>
              {expandedId === deal.id && dealDetails[deal.id] && (
                <TableRow>
                  <TableCell colSpan={99} style={{ padding: 0, background: t.expandedBg }}>
                    <div style={{ padding: '12px 20px 16px', borderTop: `2px solid ${tokens.colorBrandBackground}`, display: 'flex', flexDirection: 'column', gap: 16 }}>
                      <div>
                        <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: tokens.colorNeutralForeground3, marginBottom: 6 }}>Contacts</div>
                        <SubTable headers={['Name', 'Email', 'Phone']}
                          rows={dealDetails[deal.id].contacts.map((ct: any) => [`${ct.firstname || ''} ${ct.lastname || ''}`.trim() || '—', ct.email || '—', ct.phone || '—'])} />
                      </div>
                      <div>
                        <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: tokens.colorNeutralForeground3, marginBottom: 6 }}>Companies</div>
                        <SubTable headers={['Name', 'Domain', 'City', 'Industry']}
                          rows={dealDetails[deal.id].companies.map((co: any) => [co.name || '—', co.domain || '—', co.city || '—', co.industry || '—'])} />
                      </div>
                      <div>
                        <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: tokens.colorNeutralForeground3, marginBottom: 6 }}>Tickets</div>
                        <SubTable headers={['Subject', 'Status', 'Priority']}
                          rows={dealDetails[deal.id].tickets.map((tk: any) => [tk.subject || '—', tk.status || '—', tk.priority || '—'])} />
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
          title={`Edit Deal: ${editingRecord.dealname}`}
          fields={fFields}
          saving={saving}
          onSave={handleSave}
          onCancel={() => setEditingId(null)}
          mode="edit"
        />
      )}
      <Dialog open={!!viewingDeal} onOpenChange={(_, data) => { if (!data.open) setViewingDeal(null); }}>
        <DialogSurface style={{ maxWidth: '720px', width: '90vw', padding: '24px' }}>
          <DialogBody>
            <DialogTitle style={{ fontSize: '18px', fontWeight: 700, color: tokens.colorBrandForeground1 }}>
              {viewingDeal?.dealname || 'Deal'}
            </DialogTitle>
            <DialogContent style={{ paddingTop: '16px' }}>
              {viewingDeal && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '10px 12px' }}>
                    {dealViewFields.map(field => (
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
              <Button appearance="secondary" icon={<DismissRegular />} onClick={() => setViewingDeal(null)}>Close</Button>
              {viewingDeal && (
                <Button appearance="primary" icon={<EditRegular />} onClick={() => openEdit(viewingDeal)}>Edit</Button>
              )}
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
    </div>
  );
}
