import React from 'react';
import {
  FluentProvider,
  webLightTheme,
  webDarkTheme,
  createLightTheme,
  createDarkTheme,
} from '@fluentui/react-components';
import type { BrandVariants } from '@fluentui/react-components';
import { useTheme } from './McpBridge';

interface Props {
  children: React.ReactNode;
  brand?: BrandVariants;
}

export function FluentWrapper({ children, brand }: Props) {
  const theme = useTheme();
  const light = brand ? createLightTheme(brand) : webLightTheme;
  const dark = brand ? createDarkTheme(brand) : webDarkTheme;
  return (
    <FluentProvider theme={theme === 'dark' ? dark : light} style={{ background: 'transparent' }}>
      {children}
    </FluentProvider>
  );
}

