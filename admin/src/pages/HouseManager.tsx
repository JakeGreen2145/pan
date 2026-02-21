import React, { useState } from 'react';
import { Tenants } from './Tenants';
import { Units } from './Units';
import { Payments } from './Payments';
import { Leases } from './Leases';
import { BankConnection } from './BankConnection';

export const HouseManager: React.FC = () => {
  const [activeTab, setActiveTab] = useState('tenants');

  const tabs = [
    { id: 'tenants', label: 'Tenants' },
    { id: 'units', label: 'Units' },
    { id: 'payments', label: 'Payments' },
    { id: 'leases', label: 'Leases' },
    { id: 'bank', label: 'Bank Connection' },
  ];

  return (
    <div>
      <div style={{ display: 'flex', gap: '8px', marginBottom: '24px', borderBottom: '1px solid var(--border)', paddingBottom: '12px' }}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: '8px 16px',
              background: activeTab === tab.id ? 'var(--surface)' : 'transparent',
              border: 'none',
              borderRadius: '4px',
              color: activeTab === tab.id ? 'var(--primary)' : 'var(--text-secondary)',
              cursor: 'pointer',
              fontWeight: 500,
              fontSize: '14px'
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'tenants' && <Tenants />}
      {activeTab === 'units' && <Units />}
      {activeTab === 'payments' && <Payments />}
      {activeTab === 'leases' && <Leases />}
      {activeTab === 'bank' && <BankConnection />}
    </div>
  );
};
