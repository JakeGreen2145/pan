export interface Tenant {
  id: string;
  name: string;
  unit: string;
  rent_amount: number;
  lease_start: string;
  lease_end: string;
  late_fee_flat: number;
  late_fee_daily: number;
  grace_period_days: number;
  is_active: boolean;
  discord_id: number | null;
}

export interface TenantCreateRequest {
  name: string;
  unit: string;
  rent_amount: number;
  lease_start: string;
  lease_end: string;
  late_fee_flat?: number;
  late_fee_daily?: number;
  grace_period_days?: number;
  discord_id?: number | null;
}

export interface Unit {
  unit: string;
  rent_amount: number;
  tenant_count: number;
}

export interface Transaction {
  id: string;
  amount: number;
  date: string;
  name: string;
  original_description: string | null;
  is_zelle: boolean;
  parsed_sender_name: string | null;
  match_status: 'matched' | 'partial' | 'unmatched' | 'manual' | 'ignored';
  match_confidence: number;
  matched_tenant_id: string | null;
}

export interface PlaidAccount {
  id: string;
  institution_name: string;
  last_synced_at: string | null;
}

export interface LeaseDocument {
  id: string;
  tenant_id: string;
  filename: string;
  lease_start: string | null;
  lease_end: string | null;
  uploaded_at: string;
}

export interface ReconciliationSummary {
  total_expected: number;
  total_received: number;
  shortfall: number;
}
