import React, { useEffect, useState } from 'react';
import { api } from '../api';
import type { LeaseDocument, Tenant } from '../types';
import { Table } from '../components/Table';
import { Modal } from '../components/Modal';

export const Leases: React.FC = () => {
  const [leases, setLeases] = useState<LeaseDocument[]>([]);
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [selectedTenantId, setSelectedTenantId] = useState<string>('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const fetchData = async () => {
    try {
      const [leaseData, tenantData] = await Promise.all([
        api.leases.list(),
        api.tenants.list()
      ]);
      setLeases(leaseData);
      setTenants(tenantData);
    } catch (error) {
      console.error('Failed to fetch lease data', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleUpload = async () => {
    if (!selectedTenantId || !selectedFile) return;
    try {
      await api.leases.upload(selectedTenantId, selectedFile);
      setIsUploadModalOpen(false);
      setSelectedTenantId('');
      setSelectedFile(null);
      fetchData();
    } catch (error) {
      console.error('Failed to upload lease', error);
      alert('Failed to upload lease');
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm('Are you sure you want to delete this lease?')) {
      try {
        await api.leases.delete(id);
        fetchData();
      } catch (error) {
        console.error('Failed to delete lease', error);
      }
    }
  };

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px' }}>
        <h2 style={{ margin: 0 }}>Leases</h2>
        <button 
          onClick={() => setIsUploadModalOpen(true)}
          style={{
            background: 'var(--primary)',
            color: 'white',
            border: 'none',
            padding: '8px 16px',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Upload Lease
        </button>
      </div>

      <Table
        data={leases}
        keyExtractor={(l) => l.id}
        columns={[
          { header: 'Tenant', accessor: (l) => tenants.find(t => t.id === l.tenant_id)?.name || 'Unknown' },
          { header: 'Filename', accessor: 'filename' },
          { header: 'Uploaded At', accessor: (l) => new Date(l.uploaded_at).toLocaleDateString() },
          { header: 'Lease Period', accessor: (l) => l.lease_start && l.lease_end ? `${l.lease_start} - ${l.lease_end}` : '-' },
        ]}
        actions={(l) => (
          <div style={{ display: 'flex', gap: '8px' }}>
            <a 
              href={api.leases.downloadUrl(l.id)} 
              target="_blank" 
              rel="noopener noreferrer"
              style={{ color: 'var(--primary)', textDecoration: 'none', fontSize: '14px' }}
            >
              Download
            </a>
            <button 
              onClick={() => handleDelete(l.id)}
              style={{ background: 'none', border: 'none', color: 'var(--error)', cursor: 'pointer' }}
            >
              Delete
            </button>
          </div>
        )}
      />

      <Modal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        title="Upload Lease Document"
        footer={
          <>
            <button onClick={() => setIsUploadModalOpen(false)} style={{ padding: '8px 16px', background: 'transparent', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px', cursor: 'pointer' }}>Cancel</button>
            <button onClick={handleUpload} disabled={!selectedTenantId || !selectedFile} style={{ padding: '8px 16px', background: 'var(--primary)', border: 'none', color: 'white', borderRadius: '4px', cursor: 'pointer', opacity: (!selectedTenantId || !selectedFile) ? 0.5 : 1 }}>Upload</button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
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
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>Select File</label>
            <input 
              type="file" 
              onChange={(e) => setSelectedFile(e.target.files ? e.target.files[0] : null)}
              style={{ padding: '8px', background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px' }}
            />
          </div>
        </div>
      </Modal>
    </div>
  );
};
