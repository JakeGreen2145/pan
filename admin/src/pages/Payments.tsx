import React, { useEffect, useState } from 'react';
import { api } from '../api';
import type { Transaction, ReconciliationSummary, Tenant } from '../types';
import { Table } from '../components/Table';
import { Badge } from '../components/Badge';
import { Modal } from '../components/Modal';

export const Payments: React.FC = () => {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [summary, setSummary] = useState<ReconciliationSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [matchingTransaction, setMatchingTransaction] = useState<Transaction | null>(null);
  const [selectedTenantId, setSelectedTenantId] = useState<string>('');
  const [month, setMonth] = useState<string>(new Date().toISOString().slice(0, 7));
  const [statusFilter, setStatusFilter] = useState<string>('');

  const fetchData = async () => {
    setLoading(true);
    try {
      const [txData, summaryData, tenantData] = await Promise.all([
        api.payments.transactions({ month, match_status: statusFilter || undefined }),
        api.payments.summary(month),
        api.tenants.list()
      ]);
      setTransactions(txData);
      setSummary(summaryData);
      setTenants(tenantData);
    } catch (error) {
      console.error('Failed to fetch payment data', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [month, statusFilter]);

  const handleMatch = async () => {
    if (!matchingTransaction || !selectedTenantId) return;
    try {
      await api.payments.match(matchingTransaction.id, selectedTenantId);
      setMatchingTransaction(null);
      setSelectedTenantId('');
      fetchData();
    } catch (error) {
      console.error('Failed to match transaction', error);
      alert('Failed to match transaction');
    }
  };

  const handleIgnore = async (id: string) => {
    try {
      await api.payments.ignore(id);
      fetchData();
    } catch (error) {
      console.error('Failed to ignore transaction', error);
    }
  };

  const handleSync = async () => {
    try {
      await api.payments.sync();
      fetchData();
    } catch (error) {
      console.error('Failed to sync transactions', error);
      alert('Failed to sync transactions');
    }
  };

  const handleAutoMatch = async () => {
    try {
      await api.payments.autoMatch();
      fetchData();
    } catch (error) {
      console.error('Failed to auto-match transactions', error);
      alert('Failed to auto-match transactions');
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'matched': return <Badge variant="success">Matched</Badge>;
      case 'partial': return <Badge variant="warning">Partial</Badge>;
      case 'unmatched': return <Badge variant="error">Unmatched</Badge>;
      case 'manual': return <Badge variant="success">Manual</Badge>;
      case 'ignored': return <Badge variant="neutral">Ignored</Badge>;
      default: return <Badge variant="neutral">{status}</Badge>;
    }
  };

  if (loading && !transactions.length) return <div>Loading...</div>;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h2 style={{ margin: 0 }}>Payments</h2>
        <div style={{ display: 'flex', gap: '12px' }}>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ padding: '8px', background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px' }}
          >
            <option value="">All Statuses</option>
            <option value="matched">Matched</option>
            <option value="partial">Partial</option>
            <option value="unmatched">Unmatched</option>
            <option value="manual">Manual</option>
            <option value="ignored">Ignored</option>
          </select>
          <input 
            type="month" 
            value={month} 
            onChange={(e) => setMonth(e.target.value)}
            style={{ padding: '8px', background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px' }}
          />
          <button onClick={handleSync} style={{ padding: '8px 16px', background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px', cursor: 'pointer' }}>Sync Plaid</button>
          <button onClick={handleAutoMatch} style={{ padding: '8px 16px', background: 'var(--primary)', border: 'none', color: 'white', borderRadius: '4px', cursor: 'pointer' }}>Auto-Match</button>
        </div>
      </div>

      {summary && (
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(3, 1fr)', 
          gap: '24px', 
          marginBottom: '32px',
          background: 'var(--surface)',
          padding: '24px',
          borderRadius: '8px',
          border: '1px solid var(--border)'
        }}>
          <div>
            <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '8px' }}>Expected Rent</div>
            <div style={{ fontSize: '24px', fontWeight: 600 }}>${summary.total_expected.toLocaleString()}</div>
          </div>
          <div>
            <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '8px' }}>Received</div>
            <div style={{ fontSize: '24px', fontWeight: 600, color: 'var(--success)' }}>${summary.total_received.toLocaleString()}</div>
          </div>
          <div>
            <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginBottom: '8px' }}>Shortfall</div>
            <div style={{ fontSize: '24px', fontWeight: 600, color: summary.shortfall > 0 ? 'var(--error)' : 'var(--text-primary)' }}>
              ${summary.shortfall.toLocaleString()}
            </div>
          </div>
        </div>
      )}

      <Table
        data={transactions}
        keyExtractor={(t) => t.id}
        columns={[
          { header: 'Date', accessor: (t) => new Date(t.date).toLocaleDateString() },
          { header: 'Amount', accessor: (t) => `$${t.amount.toLocaleString()}` },
          { header: 'Sender', accessor: (t) => t.parsed_sender_name || t.name },
          { header: 'Status', accessor: (t) => getStatusBadge(t.match_status) },
          { header: 'Matched Tenant', accessor: (t) => tenants.find(tenant => tenant.id === t.matched_tenant_id)?.name || '-' },
        ]}
        actions={(t) => (
          <div style={{ display: 'flex', gap: '8px' }}>
            {t.match_status === 'unmatched' && (
              <button 
                onClick={() => setMatchingTransaction(t)}
                style={{ background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer' }}
              >
                Match
              </button>
            )}
            {t.match_status !== 'ignored' && (
              <button 
                onClick={() => handleIgnore(t.id)}
                style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
              >
                Ignore
              </button>
            )}
          </div>
        )}
      />

      <Modal
        isOpen={!!matchingTransaction}
        onClose={() => {
          setMatchingTransaction(null);
          setSelectedTenantId('');
        }}
        title="Match Transaction"
        footer={
          <>
            <button onClick={() => setMatchingTransaction(null)} style={{ padding: '8px 16px', background: 'transparent', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px', cursor: 'pointer' }}>Cancel</button>
            <button onClick={handleMatch} disabled={!selectedTenantId} style={{ padding: '8px 16px', background: 'var(--primary)', border: 'none', color: 'white', borderRadius: '4px', cursor: 'pointer', opacity: !selectedTenantId ? 0.5 : 1 }}>Confirm Match</button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ padding: '12px', background: 'var(--background)', borderRadius: '4px' }}>
            <div style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>Transaction</div>
            <div style={{ fontWeight: 500, marginTop: '4px' }}>
              {matchingTransaction?.parsed_sender_name || matchingTransaction?.name} — ${matchingTransaction?.amount.toLocaleString()}
            </div>
          </div>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>Select Tenant</label>
            <select 
              value={selectedTenantId} 
              onChange={(e) => setSelectedTenantId(e.target.value)}
              style={{ padding: '8px', background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px' }}
            >
              <option value="">Select a tenant...</option>
              {tenants.map(t => (
                <option key={t.id} value={t.id}>{t.name} (Unit {t.unit})</option>
              ))}
            </select>
          </div>
        </div>
      </Modal>
    </div>
  );
};
