/**
 * UserManagement Page — Phase 9
 * Admin portal for managing user accounts and RBAC system roles:
 * PUBLIC, CITIZEN, ANALYST, ADMIN, GOVERNMENT.
 */
import React, { useEffect, useState } from 'react';
import { adminAPI } from '../../utils/api';
import type { AdminUser, UserRole } from '../../types';
import { Card, Button, Select, Input } from '../../components/ui/Primitives';
import { TableSkeleton, EmptyState } from '../../components/ui/States';
import {
  Users,
  RefreshCw,
  Search,
  CheckCircle,
  AlertCircle,
} from 'lucide-react';

const ROLE_COLORS: Record<string, string> = {
  PUBLIC: 'var(--text-muted)',
  CITIZEN: 'var(--severity-1)',
  ANALYST: 'var(--cat-thunderstorm)',
  GOVERNMENT: 'var(--severity-3)',
  ADMIN: 'var(--severity-4)',
};

export const UserManagement: React.FC = () => {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedRoleFilter, setSelectedRoleFilter] = useState<string>('ALL');
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [notification, setNotification] = useState<{ message: string; isError?: boolean } | null>(null);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const role = selectedRoleFilter === 'ALL' ? undefined : selectedRoleFilter;
      const res = await adminAPI.users(role, 100);
      setUsers(res);
    } catch (err: any) {
      setNotification({ message: err?.message || 'Failed to load user directory', isError: true });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, [selectedRoleFilter]);

  const handleRoleChange = async (userId: string, newRole: UserRole) => {
    try {
      setActionLoading(userId);
      setNotification(null);
      await adminAPI.updateUserRole(userId, newRole);
      setNotification({ message: `Successfully updated user role to ${newRole}.` });
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, role: newRole } : u))
      );
    } catch (err: any) {
      setNotification({
        message: err?.message || 'Failed to update user role',
        isError: true,
      });
    } finally {
      setActionLoading(null);
    }
  };

  const filteredUsers = users.filter((u) => {
    if (!searchTerm.trim()) return true;
    const q = searchTerm.toLowerCase();
    return (
      u.email.toLowerCase().includes(q) ||
      u.display_name.toLowerCase().includes(q) ||
      u.role.toLowerCase().includes(q)
    );
  });

  return (
    <div
      style={{
        padding: '1.5rem',
        maxWidth: '1400px',
        margin: '0 auto',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: '1.5rem',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: 'var(--text-2xl)', fontWeight: 700, color: 'var(--text-primary)' }}>
            User & Access Management
          </h1>
          <p style={{ margin: '0.25rem 0 0 0', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
            Manage registered operators, assign RBAC permissions, and monitor last activity
          </p>
        </div>

        <Button variant="secondary" size="sm" icon={<RefreshCw size={14} />} onClick={fetchUsers} loading={loading}>
          Refresh Directory
        </Button>
      </div>

      {/* Global Notification */}
      {notification && (
        <div
          style={{
            padding: '0.75rem 1rem',
            borderRadius: 'var(--radius-md)',
            fontSize: 'var(--text-sm)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            backgroundColor: notification.isError ? 'rgba(239, 68, 68, 0.15)' : 'rgba(34, 197, 94, 0.15)',
            border: `1px solid ${notification.isError ? 'rgba(239, 68, 68, 0.3)' : 'rgba(34, 197, 94, 0.3)'}`,
            color: notification.isError ? 'var(--severity-4)' : 'var(--severity-1)',
          }}
        >
          {notification.isError ? <AlertCircle size={16} /> : <CheckCircle size={16} />}
          <span>{notification.message}</span>
        </div>
      )}

      {/* Filters Toolbar */}
      <Card>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center' }}>
          <div style={{ flex: '1 1 260px' }}>
            <Input
              placeholder="Search by name, email, or role..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              icon={<Search size={14} color="var(--text-muted)" />}
            />
          </div>

          <div style={{ width: '180px' }}>
            <Select
              value={selectedRoleFilter}
              onChange={(e) => setSelectedRoleFilter(e.target.value)}
              options={[
                { value: 'ALL', label: 'All Roles' },
                { value: 'PUBLIC', label: 'PUBLIC' },
                { value: 'CITIZEN', label: 'CITIZEN' },
                { value: 'ANALYST', label: 'ANALYST' },
                { value: 'GOVERNMENT', label: 'GOVERNMENT' },
                { value: 'ADMIN', label: 'ADMIN' },
              ]}
            />
          </div>
        </div>
      </Card>

      {/* User Table */}
      {loading ? (
        <TableSkeleton rows={8} />
      ) : filteredUsers.length === 0 ? (
        <EmptyState
          title="No Users Found"
          message="No registered user profiles matched your current search or filter criteria."
          action={
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                setSelectedRoleFilter('ALL');
                setSearchTerm('');
              }}
            >
              Clear Filters
            </Button>
          }
        />
      ) : (
        <Card>
          <div style={{ overflowX: 'auto' }}>
            <table
              style={{
                width: '100%',
                borderCollapse: 'collapse',
                textAlign: 'left',
                fontSize: 'var(--text-sm)',
              }}
            >
              <thead>
                <tr style={{ borderBottom: '1px solid var(--bg-border)', color: 'var(--text-muted)', fontSize: 'var(--text-xs)' }}>
                  <th style={{ padding: '0.75rem 0.5rem' }}>User</th>
                  <th style={{ padding: '0.75rem 0.5rem' }}>Email</th>
                  <th style={{ padding: '0.75rem 0.5rem' }}>Current Role</th>
                  <th style={{ padding: '0.75rem 0.5rem' }}>Created</th>
                  <th style={{ padding: '0.75rem 0.5rem' }}>Last Login</th>
                  <th style={{ padding: '0.75rem 0.5rem', textAlign: 'right' }}>Role Assignment (RBAC)</th>
                </tr>
              </thead>
              <tbody>
                {filteredUsers.map((u) => {
                  const roleColor = ROLE_COLORS[u.role] || 'var(--text-muted)';
                  return (
                    <tr
                      key={u.id}
                      style={{
                        borderBottom: '1px solid var(--bg-border)',
                      }}
                    >
                      <td style={{ padding: '0.75rem 0.5rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <Users size={16} color="var(--brand-blue)" />
                          <span>{u.display_name}</span>
                        </div>
                      </td>
                      <td style={{ padding: '0.75rem 0.5rem', color: 'var(--text-secondary)' }}>
                        {u.email}
                      </td>
                      <td style={{ padding: '0.75rem 0.5rem' }}>
                        <span
                          style={{
                            padding: '0.2rem 0.5rem',
                            borderRadius: 'var(--radius-sm)',
                            fontSize: '11px',
                            fontWeight: 700,
                            backgroundColor: 'var(--bg-elevated)',
                            color: roleColor,
                            border: `1px solid ${roleColor}`,
                          }}
                        >
                          {u.role}
                        </span>
                      </td>
                      <td style={{ padding: '0.75rem 0.5rem', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                        {u.created_at ? new Date(u.created_at).toLocaleDateString('en-IN') : '—'}
                      </td>
                      <td style={{ padding: '0.75rem 0.5rem', fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                        {u.last_login_at ? new Date(u.last_login_at).toLocaleString('en-IN') : 'Never'}
                      </td>
                      <td style={{ padding: '0.75rem 0.5rem', textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
                          <Select
                            value={u.role}
                            disabled={actionLoading === u.id}
                            onChange={(e) => handleRoleChange(u.id, e.target.value as UserRole)}
                            options={[
                              { value: 'PUBLIC', label: 'PUBLIC' },
                              { value: 'CITIZEN', label: 'CITIZEN' },
                              { value: 'ANALYST', label: 'ANALYST' },
                              { value: 'GOVERNMENT', label: 'GOVERNMENT' },
                              { value: 'ADMIN', label: 'ADMIN' },
                            ]}
                            style={{ minWidth: '130px', fontSize: 'var(--text-xs)' }}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
};
