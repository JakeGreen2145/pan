import React, { useEffect, useState } from 'react';
import { api } from '../api';
import type { Tenant, TenantCreateRequest } from '../types';
import { Table } from '../components/Table';
import { Badge } from '../components/Badge';
import { Modal } from '../components/Modal';

export const Tenants: React.FC = () => {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingTenant, setEditingTenant] = useState<Tenant | null>(null);
  const [formData, setFormData] = useState<Partial<TenantCreateRequest>>({});

  const fetchTenants = async () => {
    try {
      const data = await api.tenants.list();
      setTenants(data);
    } catch (error) {
      console.error('Failed to fetch tenants', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTenants();
  }, []);

  const handleSave = async () => {
    try {
      if (editingTenant) {
        await api.tenants.update(editingTenant.id, formData);
      } else {
        await api.tenants.create(formData as TenantCreateRequest);
      }
      setIsModalOpen(false);
      setEditingTenant(null);
      setFormData({});
      fetchTenants();
    } catch (error) {
      console.error('Failed to save tenant', error);
      alert('Failed to save tenant');
    }
  };

  const handleDelete = async (id: string) => {
    if (confirm('Are you sure you want to delete this tenant?')) {
      try {
        await api.tenants.delete(id);
        fetchTenants();
      } catch (error) {
        console.error('Failed to delete tenant', error);
      }
    }
  };

  const openModal = (tenant?: Tenant) => {
    if (tenant) {
      setEditingTenant(tenant);
      setFormData({
        name: tenant.name,
        unit: tenant.unit,
        rent_amount: tenant.rent_amount,
        lease_start: tenant.lease_start,
        lease_end: tenant.lease_end,
        late_fee_flat: tenant.late_fee_flat,
        late_fee_daily: tenant.late_fee_daily,
        grace_period_days: tenant.grace_period_days,
        discord_id: tenant.discord_id,
      });
    } else {
      setEditingTenant(null);
      setFormData({});
    }
    setIsModalOpen(true);
  };

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px' }}>
        <h2 style={{ margin: 0 }}>Tenants</h2>
        <button 
          onClick={() => openModal()}
          style={{
            background: 'var(--primary)',
            color: 'white',
            border: 'none',
            padding: '8px 16px',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Add Tenant
        </button>
      </div>

      <Table
        data={tenants}
        keyExtractor={(t) => t.id}
        columns={[
          { header: 'Name', accessor: 'name' },
          { header: 'Unit', accessor: 'unit' },
          { header: 'Rent', accessor: (t) => `$${t.rent_amount.toLocaleString()}` },
          { header: 'Lease Period', accessor: (t) => `${t.lease_start} - ${t.lease_end}` },
          { header: 'Status', accessor: (t) => (
            <Badge variant={t.is_active ? 'success' : 'neutral'}>
              {t.is_active ? 'Active' : 'Inactive'}
            </Badge>
          )},
        ]}
        actions={(t) => (
          <>
            <button onClick={() => openModal(t)} style={{ background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer' }}>Edit</button>
            <button onClick={() => handleDelete(t.id)} style={{ background: 'none', border: 'none', color: 'var(--error)', cursor: 'pointer' }}>Delete</button>
          </>
        )}
      />

      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title={editingTenant ? 'Edit Tenant' : 'Add Tenant'}
        footer={
          <>
            <button onClick={() => setIsModalOpen(false)} style={{ padding: '8px 16px', background: 'transparent', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px', cursor: 'pointer' }}>Cancel</button>
            <button onClick={handleSave} style={{ padding: '8px 16px', background: 'var(--primary)', border: 'none', color: 'white', borderRadius: '4px', cursor: 'pointer' }}>Save</button>
          </>
        }
      >
        <div style={{ display: 'grid', gap: '16px' }}>
          <input 
            placeholder="Name" 
            value={formData.name || ''} 
            onChange={e => setFormData({...formData, name: e.target.value})}
            style={{ padding: '8px', background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px' }}
          />
          <input 
            placeholder="Unit" 
            value={formData.unit || ''} 
            onChange={e => setFormData({...formData, unit: e.target.value})}
            style={{ padding: '8px', background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px' }}
          />
          <input 
            type="number"
            placeholder="Rent Amount" 
            value={formData.rent_amount || ''} 
            onChange={e => setFormData({...formData, rent_amount: Number(e.target.value)})}
            style={{ padding: '8px', background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px' }}
          />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
            <input 
              type="date"
              placeholder="Lease Start" 
              value={formData.lease_start || ''} 
              onChange={e => setFormData({...formData, lease_start: e.target.value})}
              style={{ padding: '8px', background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px' }}
            />
            <input 
              type="date"
              placeholder="Lease End" 
              value={formData.lease_end || ''} 
              onChange={e => setFormData({...formData, lease_end: e.target.value})}
              style={{ padding: '8px', background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px' }}
            />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px' }}>
            <input 
              type="number"
              placeholder="Late Fee (Flat)" 
              value={formData.late_fee_flat || ''} 
              onChange={e => setFormData({...formData, late_fee_flat: Number(e.target.value)})}
              style={{ padding: '8px', background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px' }}
            />
            <input 
              type="number"
              placeholder="Late Fee (Daily)" 
              value={formData.late_fee_daily || ''} 
              onChange={e => setFormData({...formData, late_fee_daily: Number(e.target.value)})}
              style={{ padding: '8px', background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px' }}
            />
            <input 
              type="number"
              placeholder="Grace Period (Days)" 
              value={formData.grace_period_days || ''} 
              onChange={e => setFormData({...formData, grace_period_days: Number(e.target.value)})}
              style={{ padding: '8px', background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px' }}
            />
          </div>
          <input 
            type="number"
            placeholder="Discord ID (Optional)" 
            value={formData.discord_id || ''} 
            onChange={e => setFormData({...formData, discord_id: e.target.value ? Number(e.target.value) : null})}
            style={{ padding: '8px', background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px' }}
          />
        </div>
      </Modal>
    </div>
  );
};
