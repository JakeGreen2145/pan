import React from 'react';
import { TabNav } from './TabNav';

interface LayoutProps {
  children: React.ReactNode;
  activeTab: string;
  onTabChange: (id: string) => void;
}

export const Layout: React.FC<LayoutProps> = ({ children, activeTab, onTabChange }) => {
  const tabs = [
    { id: 'house-manager', label: 'House Manager' },
    { id: 'tech-chair', label: 'Tech Chair', disabled: true },
    { id: 'settings', label: 'Settings', disabled: true },
  ];

  return (
    <div style={{ 
      minHeight: '100vh', 
      background: 'var(--background)', 
      color: 'var(--text-primary)',
      fontFamily: 'system-ui, -apple-system, sans-serif'
    }}>
      <nav style={{ 
        height: '60px', 
        background: '#0f1117', 
        borderBottom: '1px solid var(--border)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 24px'
      }}>
        <h1 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--text-primary)' }}>Pan Admin</h1>
      </nav>
      
      <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
        <TabNav tabs={tabs} activeTab={activeTab} onTabChange={onTabChange} />
        <main>
          {children}
        </main>
      </div>
    </div>
  );
};
