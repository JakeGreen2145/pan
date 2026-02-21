import React from 'react';

interface BadgeProps {
  children: React.ReactNode;
  variant: 'success' | 'warning' | 'error' | 'neutral';
}

export const Badge: React.FC<BadgeProps> = ({ children, variant }) => {
  const colors = {
    success: { bg: 'rgba(34, 197, 94, 0.1)', color: '#22c55e' },
    warning: { bg: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b' },
    error: { bg: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' },
    neutral: { bg: 'rgba(148, 163, 184, 0.1)', color: '#94a3b8' },
  };

  const style = colors[variant];

  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      padding: '2px 8px',
      borderRadius: '4px',
      fontSize: '12px',
      fontWeight: 500,
      backgroundColor: style.bg,
      color: style.color,
    }}>
      {children}
    </span>
  );
};
