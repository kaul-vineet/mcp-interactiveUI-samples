import React from 'react';
import { Button, Dialog, DialogActions, DialogBody, DialogContent, DialogSurface, DialogTitle, Field, Input } from '@fluentui/react-components';
import { AddRegular, SaveRegular } from '@fluentui/react-icons';
import { FormSelect } from './FormSelect';

// ── RecordDialog — inline edit/create form ─────────────────────────────────
export function RecordDialog({ open, title, fields, onSave, onCancel, saving }: {
  open: boolean; title: string;
  fields: { label: string; key: string; value: string; onChange: (v: string) => void; type?: 'select'; options?: string[]; inputType?: string }[];
  onSave: () => void; onCancel: () => void; saving: boolean;
}) {
  return (
    <Dialog open={open} onOpenChange={(_, data) => { if (!data.open) onCancel(); }}>
      <DialogSurface style={{ maxWidth: '480px', padding: '24px' }}>
        <DialogBody>
          <DialogTitle style={{ fontSize: '16px', fontWeight: 600 }}>{title}</DialogTitle>
          <DialogContent style={{ paddingTop: '16px' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px 16px' }}>
              {fields.map(f =>
                f.type === 'select' ? (
                  <FormSelect key={f.key} label={f.label} value={f.value} options={f.options || []} onChange={f.onChange} />
                ) : (
                  <Field key={f.key} label={f.label} size="small">
                    <Input size="small" type={f.inputType || 'text'} value={f.value} onChange={(_, d) => f.onChange(d.value)} aria-label={f.label} />
                  </Field>
                )
              )}
            </div>
          </DialogContent>
          <DialogActions style={{ paddingTop: '16px' }}>
            <Button appearance="secondary" onClick={onCancel} disabled={saving}>Cancel</Button>
            <Button appearance="primary" onClick={onSave} disabled={saving}
              icon={title.includes('Edit') ? <SaveRegular /> : <AddRegular />}>
              {saving ? 'Saving…' : title.includes('Edit') ? 'Save' : 'Create'}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}
