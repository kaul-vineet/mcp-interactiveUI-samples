import React, { useState } from 'react';
import { Button, Field, Input, tokens } from '@fluentui/react-components';
import { ArrowLeftRegular, SaveRegular, AddRegular } from '@fluentui/react-icons';
import { useStyles } from '../styles';
import { hs } from '../theme';
import { COMPANY_FORM_FIELDS } from '../constants';
import { FormSelect } from '../components/FormSelect';
import { HsFooter } from '../components/HsFooter';

// ── FormView — standalone create/edit form ─────────────────────────────────
export function FormView({ data, callTool, toast, theme }: {
  data: any; callTool: (n: string, a?: any) => Promise<any>;
  toast: (m: string, t?: any) => void; theme: 'light' | 'dark';
}) {
  const styles = useStyles();
  const t = hs(theme);
  const isEdit = data.mode === 'edit';
  const prefill = data.prefill || {};
  const [form, setForm] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    COMPANY_FORM_FIELDS.forEach(f => { init[f.key] = prefill[f.key] || ''; });
    return init;
  });
  const [saving, setSaving] = useState(false);

  const setF = (k: string, v: string) => setForm(p => ({ ...p, [k]: v }));

  const handleSave = async () => {
    setSaving(true);
    try {
      if (isEdit) {
        await callTool('hs__update_company', { company_id: data.recordId, ...form });
        toast('Company updated');
      } else {
        await callTool('hs__create_company', form);
        toast('Company created');
      }
    } catch (e: any) { toast(e.message || 'Failed', 'error'); }
    finally { setSaving(false); }
  };

  const handleBack = () => { callTool('hs__get_companies', {}); };

  return (
    <div className={styles.card}>
      <div style={{ padding: '16px', borderBottom: `1px solid ${tokens.colorNeutralStroke2}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Button appearance="subtle" size="small" icon={<ArrowLeftRegular />} onClick={handleBack} aria-label="Back to list" />
          <h2 style={{ margin: 0, fontSize: '15px', fontWeight: 600, color: tokens.colorNeutralForeground1 }}>
            {isEdit ? `Edit Company` : 'New Company'}
          </h2>
        </div>
      </div>
      <div className={styles.formPanel}>
        <div className={styles.formGrid}>
          {COMPANY_FORM_FIELDS.map(f =>
            f.type === 'select' ? (
              <FormSelect key={f.key} label={f.label} value={form[f.key]} options={f.options || []} onChange={v => setF(f.key, v)} />
            ) : (
              <Field key={f.key} label={f.label} size="small">
                <Input size="small" value={form[f.key]} onChange={(_, d) => setF(f.key, d.value)} aria-label={f.label} />
              </Field>
            )
          )}
        </div>
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
