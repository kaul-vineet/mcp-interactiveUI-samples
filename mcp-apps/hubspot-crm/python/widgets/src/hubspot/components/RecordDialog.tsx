import React from 'react';
import { Button, Dialog, DialogActions, DialogBody, DialogContent, DialogSurface, DialogTitle, Field, Input, Textarea } from '@fluentui/react-components';
import { AddRegular, SaveRegular } from '@fluentui/react-icons';
import { FormSelect } from './FormSelect';

// ── RecordDialog — inline edit/create form ─────────────────────────────────
export function RecordDialog({ open, title, fields, onSave, onCancel, saving, mode }: {
  open: boolean; title: string;
  fields: { label: string; key: string; value: string; onChange: (v: string) => void; type?: 'select' | 'textarea'; options?: string[]; inputType?: string; readonly?: boolean }[];
  onSave: () => void; onCancel: () => void; saving: boolean; mode?: 'edit' | 'create';
}) {
  const isEdit = mode ? mode === 'edit' : title.includes('Edit');
  const narrow = fields.filter(f => f.type !== 'textarea');
  const wide = fields.filter(f => f.type === 'textarea');
  return (
    <Dialog open={open} onOpenChange={(_, data) => { if (!data.open) onCancel(); }}>
      <DialogSurface style={{ maxWidth: '480px', padding: '24px' }}>
        <DialogBody>
          <DialogTitle style={{ fontSize: '16px', fontWeight: 600 }}>{title}</DialogTitle>
          <DialogContent style={{ paddingTop: '16px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px 16px' }}>
              {narrow.map(f =>
                f.type === 'select' && !f.readonly ? (
                  <FormSelect key={f.key} label={f.label} value={f.value} options={f.options || []} onChange={f.onChange} />
                ) : (
                  <Field key={f.key} label={f.label} size="small">
                    <Input size="small" type={f.inputType || 'text'} value={f.value} onChange={(_, d) => f.onChange(d.value)} aria-label={f.label} readOnly={f.readonly} style={f.readonly ? { opacity: 0.7, fontStyle: 'italic' } : undefined} />
                  </Field>
                )
              )}
            </div>
            {wide.map(f => (
              <Field key={f.key} label={f.label} size="small" style={{ marginTop: 12 }}>
                <Textarea value={f.value} onChange={(_, d) => f.onChange(d.value)} rows={4} resize="vertical" size="small" aria-label={f.label} readOnly={f.readonly} style={f.readonly ? { opacity: 0.7, fontStyle: 'italic' } : undefined} />
              </Field>
            ))}
          </DialogContent>
          <DialogActions style={{ paddingTop: '16px' }}>
            <Button appearance="secondary" onClick={onCancel} disabled={saving}>Cancel</Button>
            <Button appearance="primary" onClick={onSave} disabled={saving}
              icon={isEdit ? <SaveRegular /> : undefined}>
              {saving ? 'Saving…' : isEdit ? 'Save' : 'Create'}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}
