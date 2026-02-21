import React, { useEffect, useState } from 'react';
import { api } from '../api';
import type { Unit } from '../types';
import { Table } from '../components/Table';
import { Modal } from '../components/Modal';

export const Units: React.FC = () => {
  const [units, setUnits] = useState<Unit[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingUnit, setEditingUnit] = useState<Unit | null>(null);
  const [newRent, setNewRent] = useState<number>(0);

  const fetchUnits = async () => {
    try {
      const data = await api.units.list();
      setUnits(data);
    } catch (error) {
      console.error('Failed to fetch units', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUnits();
  }, []);

  const handleEdit = (unit: Unit) => {
    setEditingUnit(unit);
    setNewRent(unit.rent_amount);
  };

  const handleSave = async () => {
    if (!editingUnit) return;
    try {
      await api.units.update(editingUnit.unit, newRent);
      setEditingUnit(null);
      fetchUnits();
    } catch (error) {
      console.error('Failed to update unit', error);
      alert('Failed to update unit');
    }
  };

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      <h2 style={{ marginBottom: '20px' }}>Units</h2>
      <Table
        data={units}
        keyExtractor={(u) => u.unit}
        columns={[
          { header: 'Unit', accessor: 'unit' },
          { header: 'Rent Amount', accessor: (u) => `$${u.rent_amount.toLocaleString()}` },
          { header: 'Tenants', accessor: 'tenant_count' },
        ]}
        actions={(u) => (
          <button 
            onClick={() => handleEdit(u)}
            style={{ background: 'none', border: 'none', color: 'var(--primary)', cursor: 'pointer' }}
          >
            Edit Rent
          </button>
        )}
      />

      <Modal
        isOpen={!!editingUnit}
        onClose={() => setEditingUnit(null)}
        title={`Edit Rent for Unit ${editingUnit?.unit}`}
        footer={
          <>
            <button onClick={() => setEditingUnit(null)} style={{ padding: '8px 16px', background: 'transparent', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px', cursor: 'pointer' }}>Cancel</button>
            <button onClick={handleSave} style={{ padding: '8px 16px', background: 'var(--primary)', border: 'none', color: 'white', borderRadius: '4px', cursor: 'pointer' }}>Save</button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <label style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>New Rent Amount</label>
          <input 
            type="number" 
            value={newRent} 
            onChange={(e) => setNewRent(Number(e.target.value))}
            style={{ padding: '8px', background: 'var(--background)', border: '1px solid var(--border)', color: 'var(--text-primary)', borderRadius: '4px' }}
          />
        </div>
      </Modal>
    </div>
  );
};
