import React, { useEffect, useState } from 'react';
import { api } from '../api';
import type { PlaidAccount } from '../types';
import { Table } from '../components/Table';

export const BankConnection: React.FC = () => {
  const [accounts, setAccounts] = useState<PlaidAccount[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAccounts = async () => {
    try {
      const data = await api.plaid.accounts();
      setAccounts(data);
    } catch (error) {
      console.error('Failed to fetch plaid accounts', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAccounts();
  }, []);

  const handleConnect = () => {
    alert('Plaid Link integration would open here. This requires the Plaid Link SDK.');
  };

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px' }}>
        <h2 style={{ margin: 0 }}>Bank Connections</h2>
        <button 
          onClick={handleConnect}
          style={{
            background: 'var(--primary)',
            color: 'white',
            border: 'none',
            padding: '8px 16px',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Connect Bank
        </button>
      </div>

      <Table
        data={accounts}
        keyExtractor={(a) => a.id}
        columns={[
          { header: 'Institution', accessor: 'institution_name' },
          { header: 'Last Synced', accessor: (a) => a.last_synced_at ? new Date(a.last_synced_at).toLocaleString() : 'Never' },
          { header: 'Status', accessor: () => <span style={{ color: 'var(--success)' }}>Active</span> },
        ]}
      />
    </div>
  );
};
