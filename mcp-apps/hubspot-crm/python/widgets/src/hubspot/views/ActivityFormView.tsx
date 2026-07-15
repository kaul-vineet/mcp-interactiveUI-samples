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
  const [entityTypeInput, setEntityTypeInput] = useState(entity_type || '');
  const [ownerInput, setOwnerInput] = useState('');
  const [saving, setSaving] = useState(false);

  const setF = (k: string, v: string) => setForm(p => ({ ...p, [k]: v }));

  const handleSave = async () => {
    setSaving(true);
    try {
      let result: any;
      if (isEdit) {
        const params: Record<string, string> = { activity_type, activity_id: recordId, ...form };
        if (ownerInput) params.owner_name = ownerInput;
        result = await callTool('hs__update_activity', params);
      } else {
        const params: Record<string, string> = { activity_type, ...form };
        if (entityInput && entityTypeInput) {
          params.entity_type = entityTypeInput;
          params.entity_name = entityInput;
        }
        if (ownerInput) params.owner_name = ownerInput;
        result = await callTool('hs__create_activity', params);
      }
      if (result?.type === 'error' || result?.type === 'alert') {
        toast(result.message || 'Save failed', { intent: 'error' });
        setSaving(false);
        return;
      }
      toast(`${TYPE_LABELS[activity_type] || 'Activity'} ${isEdit ? 'updated' : 'created'}`);
      // Navigate back to list
      callTool('hs__get_activities', { activity_type });
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
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <Label style={{ fontSize: 12, fontWeight: 600, color: t.textWeak }}>
              Associate with
            </Label>
            <div style={{ display: 'flex', gap: 8 }}>
              <Select
                value={entityTypeInput}
                onChange={(_, d) => setEntityTypeInput(d.value)}
                size="small"
                style={{ flex: '0 0 130px' }}
              >
                <option value="">— Type —</option>
                <option value="company">Company</option>
                <option value="contact">Contact</option>
                <option value="deal">Deal</option>
              </Select>
              <Input
                value={entityInput}
                onChange={(_, d) => setEntityInput(d.value)}
                placeholder={entityTypeInput ? `Type ${entityTypeInput} name...` : 'Select type first'}
                size="small"
                disabled={!entityTypeInput}
                style={{ flex: 1 }}
              />
            </div>
          </div>
        )}

        {/* Assigned To (owner) field */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <Label style={{ fontSize: 12, fontWeight: 600, color: t.textWeak }}>
            Assigned To
          </Label>
          <Input
            value={ownerInput}
            onChange={(_, d) => setOwnerInput(d.value)}
            placeholder="Type owner name..."
            size="small"
          />
        </div>

        {/* Dynamic form fields — narrow in 2-col grid, wide below */}
        {(() => {
          const narrow = formFields.filter((ff: any) => !ff.multiline && !ff.fullWidth);
          const wide = formFields.filter((ff: any) => ff.multiline || ff.fullWidth);
          return (
            <>
              {narrow.length > 0 && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px 16px' }}>
                  {narrow.map((ff: any) => (
                    <div key={ff.name} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <Label style={{ fontSize: 12, fontWeight: 600, color: t.textWeak }}>
                        {ff.label}{ff.required ? ' *' : ''}
                      </Label>
                      {ff.picklist ? (
                        <Select value={form[ff.name] || ''} onChange={(_, d) => setF(ff.name, d.value)} size="small">
                          <option value="">— Select —</option>
                          {ff.picklist.map((opt: string) => <option key={opt} value={opt}>{opt}</option>)}
                        </Select>
                      ) : (
                        <Input value={form[ff.name] || ''} onChange={(_, d) => setF(ff.name, d.value)} size="small" type={ff.inputType || 'text'} placeholder={ff.label} />
                      )}
                    </div>
                  ))}
                </div>
              )}
              {wide.map((ff: any) => (
                <div key={ff.name} style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <Label style={{ fontSize: 12, fontWeight: 600, color: t.textWeak }}>
                    {ff.label}{ff.required ? ' *' : ''}
                  </Label>
                  <Textarea
                    value={form[ff.name] || ''}
                    onChange={(_, d) => setF(ff.name, d.value)}
                    rows={8}
                    resize="vertical"
                    size="small"
                  />
                </div>
              ))}
            </>
          );
        })()}
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
