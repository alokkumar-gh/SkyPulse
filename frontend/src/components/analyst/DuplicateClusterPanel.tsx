/**
 * DuplicateClusterPanel — Phase 9
 * Interactive analyst component for inspecting duplicate clusters,
 * selecting mismatched reports to SPLIT into separate events,
 * or selecting another canonical event to MERGE into.
 */
import React, { useState } from 'react';
import type { DuplicateCluster } from '../../types';
import { verificationAPI } from '../../utils/api';
import { Card, Button, Input } from '../ui/Primitives';
import { SeverityBadge, CategoryBadge } from '../ui/Badges';
import { GitBranch, GitMerge, Check, AlertTriangle, Layers } from 'lucide-react';

interface DuplicateClusterPanelProps {
  cluster?: DuplicateCluster | null;
  eventId?: string;
  onClusterUpdated?: () => void;
}

export const DuplicateClusterPanel: React.FC<DuplicateClusterPanelProps> = ({
  cluster,
  eventId,
  onClusterUpdated,
}) => {
  const [selectedReportIds, setSelectedReportIds] = useState<string[]>([]);
  const [splitReason, setSplitReason] = useState('');
  const [showSplitConfirm, setShowSplitConfirm] = useState(false);
  const [isSplitting, setIsSplitting] = useState(false);

  // Merge state
  const [showMergeModal, setShowMergeModal] = useState(false);
  const [secondaryEventId, setSecondaryEventId] = useState('');
  const [mergeReason, setMergeReason] = useState('');
  const [isMerging, setIsMerging] = useState(false);

  // Feedback message
  const [feedback, setFeedback] = useState<{ message: string; isError?: boolean } | null>(null);

  const reports = cluster?.reports || [];

  const handleToggleSelect = (reportId: string) => {
    setSelectedReportIds((prev) =>
      prev.includes(reportId) ? prev.filter((id) => id !== reportId) : [...prev, reportId]
    );
  };

  const handleSelectAll = () => {
    if (selectedReportIds.length === reports.length) {
      setSelectedReportIds([]);
    } else {
      setSelectedReportIds(reports.map((r) => r.id));
    }
  };

  const executeSplit = async () => {
    if (selectedReportIds.length === 0 || !splitReason.trim()) return;
    try {
      setIsSplitting(true);
      setFeedback(null);
      const res = await verificationAPI.splitCluster(selectedReportIds, splitReason);
      setFeedback({ message: `Successfully split ${res.removed_count} report(s) from cluster.` });
      setSelectedReportIds([]);
      setSplitReason('');
      setShowSplitConfirm(false);
      if (onClusterUpdated) onClusterUpdated();
    } catch (err: any) {
      setFeedback({
        message: err?.message || 'Failed to split duplicate cluster',
        isError: true,
      });
    } finally {
      setIsSplitting(false);
    }
  };

  const executeMerge = async () => {
    const primaryId = eventId || cluster?.canonical_event_id;
    if (!primaryId || !secondaryEventId.trim() || !mergeReason.trim()) return;
    try {
      setIsMerging(true);
      setFeedback(null);
      await verificationAPI.mergeClusters(primaryId, secondaryEventId.trim(), mergeReason);
      setFeedback({ message: `Successfully merged cluster with canonical event ${secondaryEventId.trim()}` });
      setSecondaryEventId('');
      setMergeReason('');
      setShowMergeModal(false);
      if (onClusterUpdated) onClusterUpdated();
    } catch (err: any) {
      setFeedback({
        message: err?.message || 'Failed to merge events',
        isError: true,
      });
    } finally {
      setIsMerging(false);
    }
  };

  return (
    <Card>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Layers size={18} color="var(--brand-blue)" />
          <h3 style={{ margin: 0, fontSize: 'var(--text-base)', fontWeight: 600, color: 'var(--text-primary)' }}>
            Duplicate Event Cluster
          </h3>
          <span
            style={{
              padding: '0.15rem 0.5rem',
              borderRadius: 'var(--radius-full)',
              backgroundColor: 'var(--bg-elevated)',
              fontSize: '11px',
              fontWeight: 600,
              color: 'var(--text-secondary)',
            }}
          >
            {reports.length} Reports
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Button
            size="sm"
            variant="secondary"
            icon={<GitMerge size={14} />}
            onClick={() => setShowMergeModal(true)}
          >
            Merge Clusters
          </Button>
          <Button
            size="sm"
            variant="danger"
            icon={<GitBranch size={14} />}
            disabled={selectedReportIds.length === 0}
            onClick={() => setShowSplitConfirm(true)}
          >
            Split Selected ({selectedReportIds.length})
          </Button>
        </div>
      </div>

      {/* Feedback banner */}
      {feedback && (
        <div
          style={{
            padding: '0.625rem 0.875rem',
            borderRadius: 'var(--radius-md)',
            marginBottom: '1rem',
            fontSize: 'var(--text-xs)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            backgroundColor: feedback.isError ? 'rgba(239, 68, 68, 0.15)' : 'rgba(34, 197, 94, 0.15)',
            border: `1px solid ${feedback.isError ? 'rgba(239, 68, 68, 0.3)' : 'rgba(34, 197, 94, 0.3)'}`,
            color: feedback.isError ? 'var(--severity-4)' : 'var(--severity-1)',
          }}
        >
          {feedback.isError ? <AlertTriangle size={14} /> : <Check size={14} />}
          <span>{feedback.message}</span>
        </div>
      )}

      {/* Reports Table / List */}
      {reports.length === 0 ? (
        <div
          style={{
            padding: '2rem 1rem',
            textAlign: 'center',
            color: 'var(--text-muted)',
            fontSize: 'var(--text-sm)',
          }}
        >
          No correlated duplicate reports linked to this canonical event.
        </div>
      ) : (
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
                <th style={{ padding: '0.5rem', width: '36px' }}>
                  <input
                    type="checkbox"
                    checked={reports.length > 0 && selectedReportIds.length === reports.length}
                    onChange={handleSelectAll}
                    aria-label="Select all duplicate reports"
                  />
                </th>
                <th style={{ padding: '0.5rem' }}>Report ID</th>
                <th style={{ padding: '0.5rem' }}>Category</th>
                <th style={{ padding: '0.5rem' }}>Severity</th>
                <th style={{ padding: '0.5rem' }}>Location</th>
                <th style={{ padding: '0.5rem' }}>Content Snippet</th>
                <th style={{ padding: '0.5rem' }}>Duplicate Flag</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((rep) => {
                const isSelected = selectedReportIds.includes(rep.id);
                return (
                  <tr
                    key={rep.id}
                    style={{
                      borderBottom: '1px solid var(--bg-border)',
                      backgroundColor: isSelected ? 'var(--brand-blue-dim)' : 'transparent',
                      transition: 'background-color var(--transition-fast)',
                    }}
                  >
                    <td style={{ padding: '0.5rem' }}>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => handleToggleSelect(rep.id)}
                        aria-label={`Select report ${rep.id}`}
                      />
                    </td>
                    <td style={{ padding: '0.5rem', fontFamily: 'monospace', color: 'var(--text-primary)' }}>
                      {rep.id.slice(0, 8)}…
                    </td>
                    <td style={{ padding: '0.5rem' }}>
                      {rep.category ? <CategoryBadge category={rep.category as any} /> : '—'}
                    </td>
                    <td style={{ padding: '0.5rem' }}>
                      {rep.severity ? <SeverityBadge severity={rep.severity} /> : '—'}
                    </td>
                    <td style={{ padding: '0.5rem', color: 'var(--text-secondary)' }}>
                      {[rep.location_district, rep.location_state].filter(Boolean).join(', ') || 'India'}
                    </td>
                    <td
                      style={{
                        padding: '0.5rem',
                        maxWidth: '280px',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        color: 'var(--text-secondary)',
                      }}
                      title={rep.normalized_text || rep.description || rep.text || ''}
                    >
                      {rep.normalized_text || rep.description || rep.text || '—'}
                    </td>
                    <td style={{ padding: '0.5rem' }}>
                      <span
                        style={{
                          padding: '0.15rem 0.45rem',
                          borderRadius: 'var(--radius-sm)',
                          fontSize: '10px',
                          fontWeight: 600,
                          backgroundColor: rep.is_duplicate ? 'rgba(234, 179, 8, 0.15)' : 'rgba(34, 197, 94, 0.15)',
                          color: rep.is_duplicate ? 'var(--severity-2)' : 'var(--severity-1)',
                        }}
                      >
                        {rep.is_duplicate ? 'DUPLICATE' : 'CANONICAL'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Split Confirmation Dialog */}
      {showSplitConfirm && (
        <div
          style={{
            marginTop: '1rem',
            padding: '1rem',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--severity-4)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--severity-4)', marginBottom: '0.5rem', fontWeight: 600, fontSize: 'var(--text-sm)' }}>
            <AlertTriangle size={16} />
            <span>Confirm Decouple & Split Cluster</span>
          </div>
          <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', margin: '0 0 0.75rem 0' }}>
            Decoupling <strong>{selectedReportIds.length}</strong> reports will clear their canonical event linkage
            and create an audit trail. An operational justification is required:
          </p>
          <Input
            placeholder="Operational reason for splitting cluster (min 5 characters)..."
            value={splitReason}
            onChange={(e) => setSplitReason(e.target.value)}
            style={{ marginBottom: '0.75rem' }}
          />
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
            <Button size="sm" variant="secondary" onClick={() => setShowSplitConfirm(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              variant="danger"
              disabled={selectedReportIds.length === 0 || splitReason.trim().length < 5}
              loading={isSplitting}
              onClick={executeSplit}
            >
              Confirm Split
            </Button>
          </div>
        </div>
      )}

      {/* Merge Modal / Dialog */}
      {showMergeModal && (
        <div
          style={{
            marginTop: '1rem',
            padding: '1rem',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--bg-elevated)',
            border: '1px solid var(--brand-blue)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--brand-blue)', marginBottom: '0.5rem', fontWeight: 600, fontSize: 'var(--text-sm)' }}>
            <GitMerge size={16} />
            <span>Merge Cluster Into Secondary Canonical Event</span>
          </div>
          <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)', margin: '0 0 0.75rem 0' }}>
            Target canonical event UUID to merge into current event (<strong>{eventId || cluster?.canonical_event_id}</strong>).
            Constituent reports will be re-pointed to this primary event.
          </p>
          <Input
            placeholder="Secondary event UUID (e.g. 550e8400-e29b-41d4-a716-446655440000)..."
            value={secondaryEventId}
            onChange={(e) => setSecondaryEventId(e.target.value)}
            style={{ marginBottom: '0.5rem' }}
          />
          <Input
            placeholder="Justification for merging events (min 5 characters)..."
            value={mergeReason}
            onChange={(e) => setMergeReason(e.target.value)}
            style={{ marginBottom: '0.75rem' }}
          />
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
            <Button size="sm" variant="secondary" onClick={() => setShowMergeModal(false)}>
              Cancel
            </Button>
            <Button
              size="sm"
              variant="primary"
              disabled={!secondaryEventId.trim() || mergeReason.trim().length < 5}
              loading={isMerging}
              onClick={executeMerge}
            >
              Confirm Merge
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
};
