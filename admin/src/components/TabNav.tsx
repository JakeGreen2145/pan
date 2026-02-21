import React from 'react';

interface Tab {
  id: string;
  label: string;
  disabled?: boolean;
}

interface TabNavProps {
  tabs: Tab[];
  activeTab: string;
  onTabChange: (id: string) => void;
}

export const TabNav: React.FC<TabNavProps> = ({ tabs, activeTab, onTabChange }) => {
  return (
    <div style={{ 
      display: 'flex', 
      borderBottom: '1px solid var(--border)',
      marginBottom: '20px'
    }}>
      {tabs.map(tab => (
        <button
          key={tab.id}
          onClick={() => !tab.disabled && onTabChange(tab.id)}
          disabled={tab.disabled}
          style={{
            padding: '12px 24px',
            background: 'transparent',
            border: 'none',
            borderBottom: tab.id === activeTab ? '2px solid var(--primary)' : '2px solid transparent',
            color: tab.disabled ? 'var(--text-secondary)' : (tab.id === activeTab ? 'var(--primary)' : 'var(--text-primary)'),
            cursor: tab.disabled ? 'not-allowed' : 'pointer',
            fontSize: '14px',
            fontWeight: 500,
            opacity: tab.disabled ? 0.5 : 1,
            transition: 'all 0.2s'
          }}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
};
