import React, { useState, useEffect, useCallback } from 'react';
import { MessageBar, MessageBarBody, MessageBarActions, Button } from '@fluentui/react-components';
import { DismissRegular } from '@fluentui/react-icons';

type ToastType = 'success' | 'error' | 'info';

interface ToastMsg {
  message: string;
  type: ToastType;
  key: number;
  durationMs?: number;
}

let showToastGlobal: (msg: string, type?: ToastType, durationMs?: number) => void = () => {};

export function useToast() {
  return useCallback((msg: string, type: ToastType = 'success', durationMs?: number) => {
    showToastGlobal(msg, type, durationMs);
  }, []);
}

export function ToastContainer() {
  const [queue, setQueue] = useState<ToastMsg[]>([]);
  const visible = queue[0] ?? null;

  useEffect(() => {
    showToastGlobal = (msg, type = 'success', durationMs) => {
      setQueue(q => {
        const stripped = q.filter(t => t.durationMs !== 0);
        return [...stripped, { message: msg, type, key: Date.now(), durationMs }];
      });
    };
  }, []);

  useEffect(() => {
    if (!visible) return;
    if (visible.durationMs === 0) return;
    const t = setTimeout(() => setQueue(q => q.slice(1)), visible.durationMs ?? 3000);
    return () => clearTimeout(t);
  }, [visible]);

  const dismiss = () => setQueue(q => q.slice(1));

  if (!visible) return null;

  const intent = visible.type === 'error' ? 'error' : visible.type === 'info' ? 'info' : 'success';
  const isPersistent = visible.durationMs === 0;

  return (
    <div
      role="status"
      aria-live="polite"
      aria-atomic="true"
      style={{
        position: 'fixed',
        top: 12,
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 999,
        minWidth: isPersistent ? 560 : 280,
        maxWidth: isPersistent ? 'min(95vw, 1200px)' : 'min(90vw, 600px)',
      }}
    >
      <MessageBar intent={intent}>
        <MessageBarBody>{visible.message}</MessageBarBody>
        {isPersistent && (
          <MessageBarActions
            containerAction={
              <Button
                aria-label="Dismiss"
                appearance="transparent"
                icon={<DismissRegular />}
                onClick={dismiss}
              />
            }
          />
        )}
      </MessageBar>
    </div>
  );
}
