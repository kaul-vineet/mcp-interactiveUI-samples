import React, { useEffect, useState } from 'react';
import { Button, Dialog, DialogActions, DialogBody, DialogContent, DialogSurface, DialogTitle, Table, TableBody, TableCell, TableHeader, TableHeaderCell, TableRow, Text, tokens } from '@fluentui/react-components';
import { BoxRegular, DismissRegular, EditRegular, EyeRegular } from '@fluentui/react-icons';
import { useStyles, H_CELL, D_CELL } from '../styles';
import { hs } from '../theme';
import { StatusPill } from '../components/StatusPill';
import { HsViewHeader } from '../components/ViewHeader';
import { RecordDialog } from '../components/RecordDialog';
import { HsFooter } from '../components/HsFooter';

const PRODUCT_FORM_FIELDS = [
  { label: 'Product Name *', key: 'name' },
  { label: 'SKU', key: 'hs_sku' },
  { label: 'Unit Price', key: 'price' },
  { label: 'Status', key: 'hs_status', type: 'select' as const, options: ['active', 'inactive'] },
  { label: 'Product Type', key: 'hs_product_type', type: 'select' as const, options: ['inventory', 'non_inventory', 'service'] },
  { label: 'Billing Frequency', key: 'recurringbillingfrequency', type: 'select' as const, options: ['weekly', 'biweekly', 'monthly', 'quarterly', 'per_six_months', 'annually', 'per_two_years', 'per_three_years', 'per_four_years', 'per_five_years'] },
  { label: 'Term', key: 'hs_recurring_billing_period' },
  { label: 'Description', key: 'description', type: 'textarea' as const },
];

// ── ProductsView ──────────────────────────────────────────────────────────
export function ProductsView({ items: initItems, callTool, toast, theme, cacheInfo: initCacheInfo, isFullscreen }: {
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
  const [form, setForm] = useState<Record<string, string>>({});
  const [lastSavedId, setLastSavedId] = useState<string | null>(null);
  const [viewingProduct, setViewingProduct] = useState<any | null>(null);

  useEffect(() => { setLocalItems(initItems); setCacheInfo(initCacheInfo); }, [initItems]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const res = await callTool('hs__get_products', { refresh: true });
      setLocalItems(res?.items || []);
      setCacheInfo(res?._cache);
    } catch (e: any) { toast(e.message || 'Refresh failed', 'error'); }
    finally { setRefreshing(false); }
  };

  const openView = (p: any) => { setViewingProduct(p); };

  const openEdit = (p: any) => {
    setViewingProduct(null);
    setEditingId(p.id);
    setForm({
      name: p.name || '',
      hs_sku: p.hs_sku || '',
      price: p.price || '',
      hs_status: p.hs_status || '',
      hs_product_type: p.hs_product_type || '',
      recurringbillingfrequency: p.recurringbillingfrequency || '',
      hs_recurring_billing_period: p.hs_recurring_billing_period || '',
      description: p.description || '',
    });
  };
  const cancel = () => { setEditingId(null); };

  const handleSave = async () => {
    if (!editingId) return;
    setSaving(true);
    try {
      const result = await callTool('hs__update_product', { product_id: editingId, ...form });
      if (result?.type === 'error' || result?.type === 'alert') {
        toast(result.message || 'Update failed', { intent: 'error' });
        setSaving(false);
        return;
      }
      if (result?.items) { setLocalItems(result.items); setCacheInfo(result?._cache); }
      toast('Product updated'); setLastSavedId(editingId);
      cancel();
    } catch (e: any) { toast(e.message || 'Failed', 'error'); }
    finally { setSaving(false); }
  };

  useEffect(() => { if (lastSavedId) { const x = setTimeout(() => setLastSavedId(null), 4800); return () => clearTimeout(x); } }, [lastSavedId]);

  const setF = (k: string, v: string) => setForm(p => ({ ...p, [k]: v }));
  const fFields = PRODUCT_FORM_FIELDS.map(f => ({
    ...f,
    value: form[f.key] || '',
    onChange: (v: string) => setF(f.key, v),
  }));

  const productViewFields = viewingProduct ? [
    { label: 'Name', value: viewingProduct.name },
    { label: 'SKU', value: viewingProduct.hs_sku },
    { label: 'Unit Price', value: viewingProduct.price },
    { label: 'Status', value: viewingProduct.hs_status },
    { label: 'Product Type', value: viewingProduct.hs_product_type },
    { label: 'Billing Frequency', value: viewingProduct.recurringbillingfrequency },
    { label: 'Term', value: viewingProduct.hs_recurring_billing_period },
    { label: 'Description', value: viewingProduct.description },
  ] : [];

  return (
    <div className={styles.card}>
      <HsViewHeader
        icon={<BoxRegular style={{ fontSize: '18px', color: tokens.colorBrandForeground1 }} />}
        title="Products"
        count={localItems.length}
        theme={theme}
        cacheInfo={cacheInfo}
        onRefresh={isFullscreen ? handleRefresh : undefined}
        refreshing={refreshing}
      />
      <Table size="small" aria-label="Products" style={{ borderCollapse: 'collapse', tableLayout: 'fixed', width: '100%' }}>
        <TableHeader>
          <TableRow style={{ background: t.headerBg }}>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '22%' }}>Name</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '14%' }}>SKU</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '14%' }}>Price</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '14%' }}>Status</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '16%' }}>Type</TableHeaderCell>
            <TableHeaderCell style={{ ...H_CELL, color: t.textWeak, width: '14%' }}>Billing Freq</TableHeaderCell>
            {isFullscreen && <TableHeaderCell style={{ ...H_CELL, width: 50, color: t.textWeak }} />}
          </TableRow>
        </TableHeader>
        <TableBody>
          {localItems.length === 0 && (
            <TableRow><TableCell colSpan={99} className={styles.empty}><Text>No products found.</Text></TableCell></TableRow>
          )}
          {localItems.map((p: any) => (
            <TableRow key={p.id} className="hs-row"
              style={{ borderBottom: `1px solid ${tokens.colorNeutralStroke2}`, ...(lastSavedId === p.id ? { animation: 'hsRowFlash 2s ease-out' } : {}) }}
              aria-label={`Product: ${p.name}`}
            >
              <TableCell style={{ ...D_CELL, fontWeight: 600 }}>{p.name || '—'}</TableCell>
              <TableCell style={D_CELL}>{p.hs_sku || '—'}</TableCell>
              <TableCell style={D_CELL}>{p.price != null && p.price !== '' ? '$' + Number(p.price).toLocaleString() : '—'}</TableCell>
              <TableCell style={D_CELL}><StatusPill status={p.hs_status || ''} /></TableCell>
              <TableCell style={D_CELL}>{p.hs_product_type || '—'}</TableCell>
              <TableCell style={{ ...D_CELL, fontSize: 11 }}>{p.recurringbillingfrequency || '—'}</TableCell>
              {isFullscreen && (
                <TableCell style={D_CELL}>
                  <Button appearance="subtle" icon={<EyeRegular />} size="small" onClick={() => openView(p)} aria-label={`View ${p.name}`} title="View" />
                </TableCell>
              )}
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <RecordDialog
        open={editingId !== null}
        title="Edit Product"
        fields={fFields}
        onSave={handleSave}
        onCancel={cancel}
        saving={saving}
      />
      <Dialog open={!!viewingProduct} onOpenChange={(_, data) => { if (!data.open) setViewingProduct(null); }}>
        <DialogSurface style={{ maxWidth: '720px', width: '90vw', padding: '24px' }}>
          <DialogBody>
            <DialogTitle style={{ fontSize: '18px', fontWeight: 700, color: tokens.colorBrandForeground1 }}>
              {viewingProduct?.name || 'Product'}
            </DialogTitle>
            <DialogContent style={{ paddingTop: '16px' }}>
              {viewingProduct && (
                <div style={{ display: 'grid', gridTemplateColumns: '140px 1fr', gap: '10px 12px' }}>
                  {productViewFields.map(field => (
                    <React.Fragment key={field.label}>
                      <div style={{ color: t.textWeak, fontSize: 12, fontWeight: 600 }}>{field.label}</div>
                      <div style={{ color: t.text, fontSize: 13, whiteSpace: field.label === 'Description' ? 'normal' : 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{field.value || '—'}</div>
                    </React.Fragment>
                  ))}
                </div>
              )}
            </DialogContent>
            <DialogActions style={{ paddingTop: '16px' }}>
              <Button appearance="secondary" icon={<DismissRegular />} onClick={() => setViewingProduct(null)}>Close</Button>
              {viewingProduct && (
                <Button appearance="primary" icon={<EditRegular />} onClick={() => openEdit(viewingProduct)}>Edit</Button>
              )}
            </DialogActions>
          </DialogBody>
        </DialogSurface>
      </Dialog>
      <HsFooter theme={theme} />
    </div>
  );
}
