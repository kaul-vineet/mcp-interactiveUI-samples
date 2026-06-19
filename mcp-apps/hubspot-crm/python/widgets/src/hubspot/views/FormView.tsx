import React, { useState } from 'react';
import { Button, Field, Input, tokens } from '@fluentui/react-components';
import { ArrowLeftRegular, SaveRegular, AddRegular } from '@fluentui/react-icons';
import { useStyles } from '../styles';
import { hs } from '../theme';
import { FormSelect } from '../components/FormSelect';
import { HsFooter } from '../components/HsFooter';

// ── FkHint — conditional footer for FK fields ──────────────────────────────
function FkHint({ fields, theme }: { fields: any[]; theme: 'light' | 'dark' }) {
  const t = hs(theme);
  const hasFk = fields.some(f => f.label?.includes('🔗'));
  if (!hasFk) return null;
  return (
    <div style={{
      marginTop: '12px', paddingTop: '8px', fontSize: '11px',
      color: t.textWeak, borderTop: `1px solid ${t.border}`, lineHeight: 1.4,
    }}>
      🔗 Lookup fields link to other HubSpot records. Type the full name — we look up on save and show suggestions if no exact match.
    </div>
  );
}

// ── FormView — standalone create/edit form (schema-driven) ─────────────────
export function FormView({ data, callTool, toast, theme }: {
  data: any; callTool: (n: string, a?: any) => Promise<any>;
  toast: (m: string, t?: any) => void; theme: 'light' | 'dark';
}) {
  const styles = useStyles();
  const t = hs(theme);
  const isEdit = data.mode === 'edit';
  const entity = data.entity || 'company';
  const prefill = data.prefill || {};
  const schema = data._schema || {};
  const formFields: any[] = schema.formFields || [];

  const [form, setForm] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    formFields.forEach((f: any) => { init[f.name] = prefill[f.name] || ''; });
    return init;
  });
  const [saving, setSaving] = useState(false);

  const setF = (k: string, v: string) => setForm(p => ({ ...p, [k]: v }));

  const getToolName = (action: 'create' | 'update' | 'get') => {
    if (action === 'create') return `hs__create_${entity}`;
    if (action === 'update') return `hs__update_${entity}`;
    return `hs__get_${entity === 'company' ? 'companies' : 'contacts'}`;
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      let result: any;
      if (isEdit) {
        result = await callTool(getToolName('update'), { [`${entity}_id`]: data.recordId, ...form });
      } else {
        result = await callTool(getToolName('create'), form);
      }
      // FK alert pattern — persistent toast, stay on form
      if (result && result.type === 'alert') {
        toast(result.message || 'Cannot complete — please correct and retry.', { intent: 'error', duration: 0 });
        setSaving(false);
        return;
      }
      toast(`${entity === 'company' ? 'Company' : 'Contact'} ${isEdit ? 'updated' : 'created'}`);
    } catch (e: any) { toast(e.message || 'Failed', { intent: 'error' }); }
    finally { setSaving(false); }
  };

  const handleBack = () => { callTool(getToolName('get'), {}); };

  const entityLabel = entity === 'company' ? 'Company' : 'Contact';

  return (
    <div className={styles.card}>
      <div style={{ padding: '16px', borderBottom: `1px solid ${tokens.colorNeutralStroke2}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Button appearance="subtle" size="small" icon={<ArrowLeftRegular />} onClick={handleBack} aria-label="Back to list" />
          <h2 style={{ margin: 0, fontSize: '15px', fontWeight: 600, color: tokens.colorNeutralForeground1 }}>
            {isEdit ? `Edit ${entityLabel}` : `New ${entityLabel}`}
          </h2>
        </div>
      </div>
      <div className={styles.formPanel}>
        <div className={styles.formGrid}>
          {formFields.map((f: any) =>
            f.picklist ? (
              <FormSelect key={f.name} label={f.label} value={form[f.name]} options={f.picklist} onChange={v => setF(f.name, v)} />
            ) : (
              <Field key={f.name} label={f.label} size="small" required={f.required}>
                <Input size="small" value={form[f.name]} onChange={(_, d) => setF(f.name, d.value)} aria-label={f.label} />
              </Field>
            )
          )}
        </div>
        <FkHint fields={formFields} theme={theme} />
        <div className={styles.formActions}>
          <Button appearance="secondary" onClick={handleBack} disabled={saving}>Cancel</Button>
          <Button appearance="primary" onClick={handleSave} disabled={saving}
            icon={isEdit ? <SaveRegular /> : <AddRegular />}>
            {saving ? 'Saving…' : isEdit ? 'Save' : 'Create'}
          </Button>
        </div>
      </div>
      <HsFooter theme={theme} />
    </div>
  );
}
