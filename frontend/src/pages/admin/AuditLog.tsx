/**
 * AuditLog Page — Phase 9
 * Searchable, filterable immutable platform audit records.
 * Displays actor, role, action, resource, timestamp, and payload diffs.
 */
import React, { useEffect, useState } from 'react';
import { adminAPI } from '../../utils/api';
import type { AuditLogRecord } from '../../types';
import { Card, Button, Input, Select } from '../../components/ui/Primitives';
import { TableSkeleton, EmptyState } from '../../components/ui/States';
import {
  Search,
  RefreshCw,
  AlertCircle,
} from 'lucide-react';

export const AuditLogPage: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [actionFilter, setActionFilter] = useState<string>('ALL');
  const [entityFilter, setEntityFilter] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState('');

  const fetchLogs = async () => {
    try {
      setLoading(true);
      setError(null);
      const action = actionFilter === 'ALL' ? undefined : actionFilter;
      const entity = entityFilter === 'ALL' ? undefined : entityFilter;
      const res = await adminAPI.auditLogs(action, entity, 100);
      setLogs(res);
    } catch (err: any) {
      setError(err?.message || 'Failed to load audit trail');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [actionFilter, entityFilter]);

  const displayedLogs = logs.filter((log) => {
    if (!searchTerm.trim()) return true;
    const q = searchTerm.toLowerCase();
    const act = log.action_type.toLowerCase();
    const ent = log.entity_type.toLowerCase();
    const actor = (log.user_id || '').toLowerCase();
    const id = (log.entity_id || '').toLowerCase();
    return act.includes(q) || ent.includes(q) || actor.includes(q) || id.includes(q);
  });

  const getActionBadgeColor = (action: string) => {
    switch (action.toUpperCase()) {
      case 'VERIFY':
        return 'var(--severity-1)';
      case 'ROLE_CHANGE':
        return 'var(--severity-3)';
      case 'SPLIT_CLUSTER':
      case 'MERGE_CLUSTER':
        return 'var(--cat-thunderstorm)';
      case 'CONNECTOR_DISABLE':
        return 'var(--severity-4)';
      case 'CONNECTOR_ENABLE':
        return 'var(--brand-blue)';
      default:
        return 'var(--text-muted)';
    }
  };

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
            System Audit Trail & Governance
          </h1>
          <p style={{ margin: '0.25rem 0 0 0', fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
            Append-only chronological record of all administrative operations, overrides, and cluster modifications
          </p>
        </div>

        <Button variant="secondary" size="sm" icon={<RefreshCw size={14} />} onClick={fetchLogs} loading={loading}>
          Refresh Trail
        </Button>
      </div>

      {/* Filter Toolbar */}
      <Card>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'center' }}>
          <div style={{ flex: '1 1 240px' }}>
            <Input
              placeholder="Search action, entity, user ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              icon={<Search size={14} color="var(--text-muted)" />}
            />
          </div>

          <div style={{ width: '180px' }}>
            <Select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              options={[
                { value: 'ALL', label: 'All Actions' },
                { value: 'VERIFY', label: 'VERIFY (Override)' },
                { value: 'ROLE_CHANGE', label: 'ROLE_CHANGE' },
                { value: 'SPLIT_CLUSTER', label: 'SPLIT_CLUSTER' },
                { value: 'MERGE_CLUSTER', label: 'MERGE_CLUSTER' },
                { value: 'CONNECTOR_ENABLE', label: 'CONNECTOR_ENABLE' },
                { value: 'CONNECTOR_DISABLE', label: 'CONNECTOR_DISABLE' },
                { value: 'CREATE', label: 'CREATE' },
              ]}
            />
          </div>

          <div style={{ width: '180px' }}>
            <Select
              value={entityFilter}
              onChange={(e) => setEntityFilter(e.target.value)}
              options={[
                { value: 'ALL', label: 'All Entities' },
                { value: 'VerificationResult', label: 'VerificationResult' },
                { value: 'User', label: 'User' },
                { value: 'DuplicateCluster', label: 'DuplicateCluster' },
                { value: 'WeatherEvent', label: 'WeatherEvent' },
                { value: 'WeatherReport', label: 'WeatherReport' },
                { value: 'Source', label: 'Source' },
              ]}
            />
          </div>
        </div>
      </Card>

      {/* Audit Logs Table */}
      {loading ? (
        <TableSkeleton rows={8} />
      ) : error ? (
        <Card>
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--severity-4)' }}>
            <AlertCircle size={32} style={{ margin: '0 auto 0.5rem auto' }} />
            <h4 style={{ margin: 0 }}>Error Fetching Audit Logs</h4>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>{error}</p>
          </div>
        </Card>
      ) : displayedLogs.length === 0 ? (
        <EmptyState
          title="No Audit Entries Found"
          message="No recorded mutations matching your search and filter criteria."
          action={
            <Button
              size="sm"
              variant="secondary"
              onClick={() => {
                setActionFilter('ALL');
                setEntityFilter('ALL');
                setSearchTerm('');
              }}
            >
              Reset Filters
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
                fontSize: 'var(--text-xs)',
              }}
            >
              <thead>
                <tr style={{ borderBottom: '1px solid var(--bg-border)', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '0.625rem 0.5rem' }}>Timestamp</th>
                  <th style={{ padding: '0.625rem 0.5rem' }}>Actor</th>
                  <th style={{ padding: '0.625rem 0.5rem' }}>Action</th>
                  <th style={{ padding: '0.625rem 0.5rem' }}>Target Entity</th>
                  <th style={{ padding: '0.625rem 0.5rem' }}>Entity ID</th>
                  <th style={{ padding: '0.625rem 0.5rem' }}>Mutation Details / Justification</th>
                  <th style={{ padding: '0.625rem 0.5rem' }}>IP Origin</th>
                </tr>
              </thead>
              <tbody>
                {displayedLogs.map((log) => {
                  const actionColor = getActionBadgeColor(log.action_type);
                  const details = log.new_value
                    ? JSON.stringify(log.new_value)
                    : log.old_value
                    ? JSON.stringify(log.old_value)
                    : '—';

                  return (
                    <tr
                      key={log.id}
                      style={{
                        borderBottom: '1px solid var(--bg-border)',
                      }}
                    >
                      <td style={{ padding: '0.625rem 0.5rem', whiteSpace: 'nowrap', color: 'var(--text-secondary)' }}>
                        {new Date(log.created_at).toLocaleString('en-IN', {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit',
                        })}
                      </td>
                      <td style={{ padding: '0.625rem 0.5rem', fontFamily: 'monospace', color: 'var(--text-primary)' }}>
                        {log.user_id ? `${log.user_id.slice(0, 8)}…` : 'SYSTEM'}
                      </td>
                      <td style={{ padding: '0.625rem 0.5rem' }}>
                        <span
                          style={{
                            padding: '0.15rem 0.45rem',
                            borderRadius: 'var(--radius-sm)',
                            fontWeight: 700,
                            fontSize: '10px',
                            backgroundColor: 'var(--bg-elevated)',
                            color: actionColor,
                            border: `1px solid ${actionColor}`,
                          }}
                        >
                          {log.action_type}
                        </span>
                      </td>
                      <td style={{ padding: '0.625rem 0.5rem', color: 'var(--text-primary)', fontWeight: 500 }}>
                        {log.entity_type}
                      </td>
                      <td style={{ padding: '0.625rem 0.5rem', fontFamily: 'monospace', color: 'var(--text-secondary)' }}>
                        {log.entity_id ? `${log.entity_id.slice(0, 8)}…` : '—'}
                      </td>
                      <td
                        style={{
                          padding: '0.625rem 0.5rem',
                          maxWidth: '340px',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          color: 'var(--text-secondary)',
                          fontFamily: 'monospace',
                        }}
                        title={details}
                      >
                        {details}
                      </td>
                      <td style={{ padding: '0.625rem 0.5rem', color: 'var(--text-muted)' }}>
                        {log.ip_address || 'internal'}
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
