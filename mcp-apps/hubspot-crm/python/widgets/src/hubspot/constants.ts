import { tokens } from '@fluentui/react-components';

// ── HubSpot Picklist Constants ─────────────────────────────────────────────
export const HS_TYPES = ['PROSPECT', 'PARTNER', 'RESELLER', 'VENDOR', 'OTHER'];
export const HS_LIFECYCLESTAGES = ['subscriber', 'lead', 'marketingqualifiedlead', 'salesqualifiedlead', 'opportunity', 'customer', 'evangelist', 'other'];
export const HS_INDUSTRIES = ['Agriculture', 'Apparel', 'Banking', 'Biotechnology', 'Construction', 'Consulting', 'Education', 'Electronics', 'Energy', 'Engineering', 'Entertainment', 'Finance', 'Food & Beverage', 'Government', 'Healthcare', 'Hospitality', 'Insurance', 'Manufacturing', 'Media', 'Real Estate', 'Retail', 'Technology', 'Telecommunications', 'Transportation', 'Utilities', 'Other'];

// ── Status pill styles ─────────────────────────────────────────────────────
export type PillStyle = { background: string; color: string; border: string };
export const STATUS_STYLES: Record<string, PillStyle> = {
  prospect:  { background: tokens.colorPaletteDarkOrangeBackground1, color: tokens.colorPaletteDarkOrangeForeground2, border: tokens.colorPaletteDarkOrangeBorder1 },
  customer:  { background: tokens.colorPaletteGreenBackground1,      color: tokens.colorPaletteGreenForeground2,      border: tokens.colorPaletteGreenBorder1 },
  lead:      { background: tokens.colorPaletteYellowBackground1,     color: tokens.colorPaletteYellowForeground2,     border: tokens.colorPaletteYellowBorder1 },
  partner:   { background: tokens.colorPaletteLavenderBackground1,   color: tokens.colorPaletteLavenderForeground2,   border: tokens.colorPaletteLavenderBorder1 },
  other:     { background: tokens.colorPaletteRedBackground1,        color: tokens.colorPaletteRedForeground2,        border: tokens.colorPaletteRedBorder1 },
};

export function getStatusKey(type: string): string {
  const v = (type || '').toLowerCase();
  if (v.includes('customer') || v.includes('evangelist')) return 'customer';
  if (v.includes('lead') || v.includes('subscriber') || v.includes('qualified')) return 'lead';
  if (v.includes('partner') || v.includes('reseller')) return 'partner';
  if (v.includes('prospect') || v.includes('opportunity')) return 'prospect';
  return 'other';
}

// ── Form field definitions ─────────────────────────────────────────────────
export const COMPANY_FORM_FIELDS = [
  { label: 'Company Name *', key: 'name' },
  { label: 'Domain', key: 'domain' },
  { label: 'Phone', key: 'phone' },
  { label: 'City', key: 'city' },
  { label: 'Industry', key: 'industry', type: 'select' as const, options: HS_INDUSTRIES },
];
