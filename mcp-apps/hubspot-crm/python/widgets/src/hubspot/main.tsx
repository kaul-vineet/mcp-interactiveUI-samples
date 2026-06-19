import React from 'react';
import { createRoot } from 'react-dom/client';
import type { BrandVariants } from '@fluentui/react-components';
import { ErrorBoundary } from '../shared/ErrorBoundary';
import { McpBridgeProvider } from '../shared/McpBridge';
import { FluentWrapper } from '../shared/FluentWrapper';
import HubSpotApp from './App';

// HubSpot brand: Coral (#FF7A59) palette as BrandVariants
const hubspotBrand: BrandVariants = {
  10: '#FFF5F2',
  20: '#FFE8E0',
  30: '#FFD4C7',
  40: '#FFBFAD',
  50: '#FFA78F',
  60: '#FF8F73',
  70: '#FF7A59',
  80: '#E8563D',
  90: '#CC4A34',
  100: '#B03E2C',
  110: '#943324',
  120: '#78281C',
  130: '#5C1E15',
  140: '#40140E',
  150: '#240A07',
  160: '#0D0302',
};

createRoot(document.getElementById('root')!).render(
  <ErrorBoundary>
    <McpBridgeProvider appName="gtc-hubspot-widget">
      <FluentWrapper brand={hubspotBrand}>
        <HubSpotApp />
      </FluentWrapper>
    </McpBridgeProvider>
  </ErrorBoundary>
);

