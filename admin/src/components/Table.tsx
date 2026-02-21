import React from 'react';

interface Column<T> {
  header: string;
  accessor: keyof T | ((item: T) => React.ReactNode);
  width?: string;
}

interface TableProps<T> {
  data: T[];
  columns: Column<T>[];
  keyExtractor: (item: T) => string;
  actions?: (item: T) => React.ReactNode;
}

export function Table<T>({ data, columns, keyExtractor, actions }: TableProps<T>) {
  return (
    <div style={{ overflowX: 'auto', border: '1px solid var(--border)', borderRadius: '8px' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
        <thead>
          <tr style={{ background: 'var(--surface)', borderBottom: '1px solid var(--border)' }}>
            {columns.map((col, i) => (
              <th key={i} style={{ padding: '12px 16px', fontWeight: 600, fontSize: '14px', color: 'var(--text-secondary)', width: col.width }}>
                {col.header}
              </th>
            ))}
            {actions && <th style={{ padding: '12px 16px', width: '100px' }}>Actions</th>}
          </tr>
        </thead>
        <tbody>
          {data.length === 0 ? (
            <tr>
              <td colSpan={columns.length + (actions ? 1 : 0)} style={{ padding: '24px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                No data found
              </td>
            </tr>
          ) : (
            data.map((item) => (
              <tr key={keyExtractor(item)} style={{ borderBottom: '1px solid var(--border)' }}>
                {columns.map((col, i) => (
                  <td key={i} style={{ padding: '12px 16px', fontSize: '14px', color: 'var(--text-primary)' }}>
                    {typeof col.accessor === 'function' ? col.accessor(item) : (item[col.accessor] as React.ReactNode)}
                  </td>
                ))}
                {actions && (
                  <td style={{ padding: '12px 16px' }}>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      {actions(item)}
                    </div>
                  </td>
                )}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
