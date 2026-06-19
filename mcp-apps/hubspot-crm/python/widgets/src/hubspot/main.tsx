import React from 'react';
import { createRoot } from 'react-dom/client';
import type { BrandVariants } from '@fluentui/react-components';
import { ErrorBoundary } from '../shared/ErrorBoundary';
import { McpBridgeProvider } from '../shared/McpBridge';
import { FluentWrapper } from '../shared/FluentWrapper';
import { ToastContainer } from '../shared/Toast';
import HubSpotApp from './App';

const hubspotBrand: BrandVariants = {
  10: '#FFF5F0',
  20: '#FFE8DB',
  30: '#FFD4BD',
  40: '#FFBD9A',
  50: '#FFA477',
  60: '#FF8C59',
  70: '#FF7A45',
  80: '#FF5C35',
  90: '#E8492B',
  100: '#CC3D24',
  110: '#B3321E',
  120: '#992818',
  130: '#801F13',
  140: '#66170E',
  150: '#4D100A',
  160: '#330A06',
};

createRoot(document.getElementById('root')!).render(
  <ErrorBoundary>
    <McpBridgeProvider appName="gtc-hubspot-widget">
      <FluentWrapper brand={hubspotBrand}>
        <HubSpotApp />
        <ToastContainer />
      </FluentWrapper>
    </McpBridgeProvider>
  </ErrorBoundary>
);

