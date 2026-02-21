import type { 
  Tenant, 
  TenantCreateRequest, 
  Unit, 
  Transaction, 
  PlaidAccount, 
  LeaseDocument,
  ReconciliationSummary
} from './types';

const API_BASE = '/api';

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.text();
    throw new Error(error || response.statusText);
  }
  return response.json();
}

export const api = {
  tenants: {
    list: () => fetch(`${API_BASE}/tenants`).then(r => handleResponse<Tenant[]>(r)),
    get: (id: string) => fetch(`${API_BASE}/tenants/${id}`).then(r => handleResponse<Tenant>(r)),
    create: (data: TenantCreateRequest) => fetch(`${API_BASE}/tenants`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).then(r => handleResponse<Tenant>(r)),
    update: (id: string, data: Partial<TenantCreateRequest>) => fetch(`${API_BASE}/tenants/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }).then(r => handleResponse<Tenant>(r)),
    delete: (id: string) => fetch(`${API_BASE}/tenants/${id}`, { method: 'DELETE' }),
  },
  units: {
    list: () => fetch(`${API_BASE}/units`).then(r => handleResponse<Unit[]>(r)),
    update: (unitName: string, rentAmount: number) => fetch(`${API_BASE}/units/${unitName}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rent_amount: rentAmount }),
    }).then(r => handleResponse<Unit>(r)),
  },
  payments: {
    transactions: (params?: { match_status?: string; is_zelle?: boolean; month?: string }) => {
      const searchParams = new URLSearchParams();
      if (params?.match_status) searchParams.append('match_status', params.match_status);
      if (params?.is_zelle !== undefined) searchParams.append('is_zelle', String(params.is_zelle));
      if (params?.month) searchParams.append('month', params.month);
      return fetch(`${API_BASE}/payments/transactions?${searchParams.toString()}`).then(r => handleResponse<Transaction[]>(r));
    },
    match: (id: string, tenantId: string) => fetch(`${API_BASE}/payments/transactions/${id}/match`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tenant_id: tenantId }),
    }).then(r => handleResponse<Transaction>(r)),
    ignore: (id: string) => fetch(`${API_BASE}/payments/transactions/${id}/ignore`, { method: 'POST' }).then(r => handleResponse<Transaction>(r)),
    summary: (month?: string) => {
      const searchParams = new URLSearchParams();
      if (month) searchParams.append('month', month);
      return fetch(`${API_BASE}/payments/summary?${searchParams.toString()}`).then(r => handleResponse<ReconciliationSummary>(r));
    },
    sync: () => fetch(`${API_BASE}/payments/sync`, { method: 'POST' }),
    autoMatch: () => fetch(`${API_BASE}/payments/auto-match`, { method: 'POST' }),
  },
  plaid: {
    accounts: () => fetch(`${API_BASE}/plaid/accounts`).then(r => handleResponse<PlaidAccount[]>(r)),
    linkToken: (userId: string) => fetch(`${API_BASE}/plaid/link-token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId }),
    }).then(r => handleResponse<{ link_token: string }>(r)),
    exchange: (publicToken: string, institutionName: string) => fetch(`${API_BASE}/plaid/exchange`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ public_token: publicToken, institution_name: institutionName }),
    }),
  },
  leases: {
    list: () => fetch(`${API_BASE}/leases`).then(r => handleResponse<LeaseDocument[]>(r)),
    byTenant: (tenantId: string) => fetch(`${API_BASE}/leases/${tenantId}`).then(r => handleResponse<LeaseDocument[]>(r)),
    upload: (tenantId: string, file: File) => {
      const formData = new FormData();
      formData.append('tenant_id', tenantId);
      formData.append('file', file);
      return fetch(`${API_BASE}/leases/upload`, {
        method: 'POST',
        body: formData,
      }).then(r => handleResponse<LeaseDocument>(r));
    },
    delete: (id: string) => fetch(`${API_BASE}/leases/${id}`, { method: 'DELETE' }),
    downloadUrl: (id: string) => `${API_BASE}/leases/${id}/download`,
  },
};
