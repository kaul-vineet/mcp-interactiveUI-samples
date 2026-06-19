export interface Company {
  id: string;
  name: string;
  domain?: string;
  type?: string;
  lifecyclestage?: string;
  phone?: string;
  city?: string;
  country?: string;
  industry?: string;
}

export interface Contact {
  id: string;
  firstname: string;
  lastname: string;
  email: string;
  phone?: string;
  lifecyclestage?: string;
}

export interface Deal {
  id: string;
  dealname: string;
  amount?: number | string;
  dealstage?: string;
  closedate?: string;
  pipeline?: string;
}

export interface Ticket {
  id: string;
  subject: string;
  status?: string;
  priority?: string;
  category?: string;
}

export type HubSpotViewType = 'companies' | 'form' | 'company_contacts' | 'company_deals' | 'company_tickets' | 'error';

export interface HubSpotData {
  type: HubSpotViewType;
  total?: number;
  items?: (Company | Contact | Deal | Ticket)[];
  entity?: string;
  mode?: 'create' | 'edit';
  recordId?: string;
  prefill?: Record<string, string>;
  _schema?: any;
  _cache?: { hit: boolean; cached_at: string };
  _updatedId?: string;
  error?: string;
  message?: string;
}

