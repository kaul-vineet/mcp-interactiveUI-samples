import React, { useState } from 'react';
import { Button, Input, Label, Select, Textarea, tokens } from '@fluentui/react-components';
import { ArrowLeftRegular, CalendarRegular, CheckmarkRegular } from '@fluentui/react-icons';
import { useStyles } from '../styles';
import { hs } from '../theme';
import { HsFooter } from '../components/HsFooter';

const TYPE_LABELS: Record<string, string> = {
  note: 'Note', call: 'Call', task: 'Task', meeting: 'Meeting', email: 'Email',
};

// ── ActivityFormView — create/edit form for activities ─────────────────────
export function ActivityFormView({ data, callTool, toast, theme }: {
  data: any; callTool: (n: string, a?: any) => Promise<any>;
  toast: (m: string, t?: any) => void; theme: 'light' | 'dark';
}) {
  const styles = useStyles();
  const t = hs(theme);
  const { activity_type, entity_type, entity_name, mode, recordId, prefill, _schema } = data;
  const formFields = _schema?.formFields || [];
  const isEdit = mode === 'edit';

  const [form, setForm] = useState<Record<string, string>>(() => {
    const f: Record<string, string> = {};
    formFields.forEach((ff: any) => { f[ff.name] = prefill?.[ff.name] || ''; });
    return f;
  });
  const [entityInput, setEntityInput] = useState(entity_name || '');
  const [entityTypeInput] = useState(entity_type || '');
  const [saving, setSaving] = useState(false);

  const setF = (k: string, v: string) => setForm(p => ({ ...p, [k]: v }));

  const handleSave = async () => {
    setSaving(true);
    try {
      let result: any;
      if (isEdit) {
        result = await callTool('hs__update_activity', { activity_type, activity_id: recordId, ...form });
      } else {
        const params: Record<string, string> = { activity_type, ...form };
        if (entityInput && entityTypeInput) {
          params.entity_type = entityTypeInput;
          params.entity_name = entityInput;
        }
        result = await callTool('hs__create_activity', params);
      }
      if (result?.type === 'error' || result?.type === 'alert') {
        toast(result.message || 'Save failed', { intent: 'error' });
        setSaving(false);
        return;
      }
      toast(`${TYPE_LABELS[activity_type] || 'Activity'} ${isEdit ? 'updated' : 'created'}`);
      // Redirect to list
      callTool('hs__get_activities', { activity_type, refresh: true });
    } catch (e: any) { toast(e.message || 'Failed', 'error'); }
    finally { setSaving(false); }
  };

  const handleBack = () => { callTool('hs__get_activities', { activity_type }); };

  const title = `${isEdit ? 'Edit' : 'New'} ${TYPE_LABELS[activity_type] || 'Activity'}`;

  return (
    <div className={styles.card} style={{ padding: '20px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20 }}>
        <Button appearance="subtle" icon={<ArrowLeftRegular />} size="small" onClick={handleBack} aria-label="Back" />
        <CalendarRegular style={{ fontSize: 18, color: tokens.colorBrandForeground1 }} />
        <span style={{ fontSize: 16, fontWeight: 700, color: t.text }}>{title}</span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* Entity association field (only for create) */}
        {!isEdit && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <Label style={{ fontSize: 12, fontWeight: 600, color: t.textWeak }}>
              Associate with ({entityTypeInput || 'entity'})
            </Label>
            <Input
              value={entityInput}
              onChange={(_, d) => setEntityInput(d.value)}
              placeholder={`Type ${entityTypeInput || 'entity'} name...`}
              size="small"
            />
          </div>
        )}

        {/* Dynamic form fields from schema */}
        {formFields.map((ff: any) => (
          <div key={ff.name} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <Label style={{ fontSize: 12, fontWeight: 600, color: t.textWeak }}>
              {ff.label}{ff.required ? ' *' : ''}
            </Label>
            {ff.picklist ? (
              <Select
                value={form[ff.name] || ''}
                onChange={(_, d) => setF(ff.name, d.value)}
                size="small"
              >
                <option value="">— Select —</option>
                {ff.picklist.map((opt: string) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </Select>
            ) : ff.multiline ? (
              <Textarea
                value={form[ff.name] || ''}
                onChange={(_, d) => setF(ff.name, d.value)}
                rows={4}
                resize="vertical"
                size="small"
              />
            ) : (
              <Input
                value={form[ff.name] || ''}
                onChange={(_, d) => setF(ff.name, d.value)}
                size="small"
                placeholder={ff.label}
              />
            )}
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 20 }}>
        <Button appearance="secondary" onClick={handleBack} disabled={saving}>Cancel</Button>
        <Button appearance="primary" icon={<CheckmarkRegular />} onClick={handleSave} disabled={saving}>
          {saving ? 'Saving…' : 'Save'}
        </Button>
      </div>

      <HsFooter theme={theme} />
    </div>
  );
}
