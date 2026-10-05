/**
 * SkyPulse Premium Data Table
 * Implements Section 8:
 * "Tables are critical for SkyPulse. They must feel like professional research/data software.
 *  Minimal borders, strong column alignment, compact row height, sticky headers,
 *  hover row state, selected row state, sorting indicators, inline search, export."
 */

import React, { useState, useMemo } from 'react';
import {
  ArrowUpDown, ArrowUp, ArrowDown, Search,
  Download, Copy, Check, ChevronLeft, ChevronRight,
} from 'lucide-react';
import { Button } from './Primitives';

export interface ColumnDef<T> {
  key: string;
  header: string;
  width?: string | number;
  align?: 'left' | 'center' | 'right';
  sortable?: boolean;
  render?: (row: T, index: number) => React.ReactNode;
}

interface DataTableProps<T> {
  data: T[];
  columns: ColumnDef<T>[];
  keyExtractor: (row: T) => string;
  title?: string;
  subtitle?: string;
  pageSize?: number;
  onRowClick?: (row: T) => void;
  selectedRowId?: string | null;
  searchable?: boolean;
  searchPlaceholder?: string;
  exportFileName?: string;
  compact?: boolean;
  emptyMessage?: string;
  className?: string;
  style?: React.CSSProperties;
}

export function DataTable<T extends Record<string, any>>({
  data,
  columns,
  keyExtractor,
  title,
  subtitle,
  pageSize = 10,
  onRowClick,
  selectedRowId,
  searchable = true,
  searchPlaceholder = 'Filter records...',
  exportFileName = 'skypulse_data',
  compact = false,
  emptyMessage = 'No meteorological records matching criteria.',
  className = '',
  style,
}: DataTableProps<T>) {
  const [searchQuery, setSearchQuery] = useState('');
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [currentPage, setCurrentPage] = useState(1);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // Search filter
  const filteredData = useMemo(() => {
    if (!searchQuery.trim()) return data;
    const q = searchQuery.toLowerCase();
    return data.filter((row) =>
      Object.values(row).some((val) =>
        val !== null && val !== undefined && String(val).toLowerCase().includes(q)
      )
    );
  }, [data, searchQuery]);

  // Sort
  const sortedData = useMemo(() => {
    if (!sortKey) return filteredData;
    return [...filteredData].sort((a, b) => {
      const valA = a[sortKey];
      const valB = b[sortKey];
      if (valA === valB) return 0;
      if (valA === null || valA === undefined) return 1;
      if (valB === null || valB === undefined) return -1;
      if (typeof valA === 'number' && typeof valB === 'number') {
        return sortDir === 'asc' ? valA - valB : valB - valA;
      }
      return sortDir === 'asc'
        ? String(valA).localeCompare(String(valB))
        : String(valB).localeCompare(String(valA));
    });
  }, [filteredData, sortKey, sortDir]);

  // Pagination
  const totalPages = Math.ceil(sortedData.length / pageSize) || 1;
  const paginatedData = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return sortedData.slice(start, start + pageSize);
  }, [sortedData, currentPage, pageSize]);

  const handleSort = (key: string) => {
    if (sortKey === key) {
      if (sortDir === 'asc') setSortDir('desc');
      else {
        setSortKey(null);
        setSortDir('asc');
      }
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const handleExportCSV = () => {
    const headers = columns.map((c) => `"${c.header}"`).join(',');
    const rows = sortedData.map((row) =>
      columns.map((c) => `"${String(row[c.key] ?? '').replace(/"/g, '""')}"`).join(',')
    );
    const csvContent = 'data:text/csv;charset=utf-8,' + [headers, ...rows].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `${exportFileName}_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleCopyRow = (e: React.MouseEvent, row: T) => {
    e.stopPropagation();
    const id = keyExtractor(row);
    navigator.clipboard.writeText(JSON.stringify(row, null, 2));
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 1500);
  };

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--border-hairline)',
        borderRadius: 'var(--r-2)',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        ...style,
      }}
      className={`sp-data-table-container ${className}`}
    >
      {/* Table Top Toolbar */}
      {(title || searchable) && (
        <div
          style={{
            padding: '0.75rem 1rem',
            borderBottom: '1px solid var(--border-hairline)',
            backgroundColor: 'var(--bg-panel)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '1rem',
            flexWrap: 'wrap',
          }}
        >
          {title && (
            <div>
              <div
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: 700,
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  color: 'var(--text-primary)',
                }}
              >
                {title}
              </div>
              {subtitle && (
                <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>
                  {subtitle}
                </div>
              )}
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: 1, justifyContent: 'flex-end' }}>
            {searchable && (
              <div style={{ position: 'relative', width: '100%', maxWidth: '240px' }}>
                <Search size={12} color="var(--text-muted)" style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)' }} />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => { setSearchQuery(e.target.value); setCurrentPage(1); }}
                  placeholder={searchPlaceholder}
                  style={{
                    width: '100%',
                    backgroundColor: 'var(--bg-surface)',
                    border: '1px solid var(--border-hairline)',
                    borderRadius: 'var(--r-1)',
                    color: 'var(--text-primary)',
                    fontSize: 'var(--text-xs)',
                    padding: '0.3rem 0.6rem 0.3rem 1.6rem',
                    outline: 'none',
                    fontFamily: 'var(--font-sans)',
                  }}
                />
              </div>
            )}

            <Button
              variant="secondary"
              size="xs"
              onClick={handleExportCSV}
              icon={<Download size={11} />}
              style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-2xs)' }}
            >
              CSV
            </Button>
          </div>
        </div>
      )}

      {/* Table Wrapper */}
      <div style={{ overflowX: 'auto', flex: 1 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead>
            <tr style={{ backgroundColor: 'var(--bg-panel)', borderBottom: '1px solid var(--border-hairline)' }}>
              {columns.map((col) => {
                const isSorted = sortKey === col.key;
                return (
                  <th
                    key={col.key}
                    onClick={() => col.sortable !== false && handleSort(col.key)}
                    style={{
                      padding: compact ? '0.45rem 0.75rem' : '0.65rem 1rem',
                      fontFamily: 'var(--font-mono)',
                      fontSize: 'var(--text-2xs)',
                      fontWeight: 700,
                      letterSpacing: '0.08em',
                      textTransform: 'uppercase',
                      color: isSorted ? 'var(--teal)' : 'var(--text-secondary)',
                      width: col.width,
                      textAlign: col.align || 'left',
                      cursor: col.sortable !== false ? 'pointer' : 'default',
                      userSelect: 'none',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                      <span>{col.header}</span>
                      {col.sortable !== false && (
                        <span>
                          {isSorted ? (
                            sortDir === 'asc' ? <ArrowUp size={11} color="var(--teal)" /> : <ArrowDown size={11} color="var(--teal)" />
                          ) : (
                            <ArrowUpDown size={10} color="var(--text-ghost)" />
                          )}
                        </span>
                      )}
                    </div>
                  </th>
                );
              })}
              <th style={{ width: 40, padding: '0.5rem' }} />
            </tr>
          </thead>
          <tbody>
            {paginatedData.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length + 1}
                  style={{
                    padding: '2.5rem 1rem',
                    textAlign: 'center',
                    color: 'var(--text-muted)',
                    fontSize: 'var(--text-xs)',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              paginatedData.map((row, rIdx) => {
                const rowId = keyExtractor(row);
                const isSelected = selectedRowId === rowId;

                return (
                  <tr
                    key={rowId}
                    onClick={() => onRowClick?.(row)}
                    style={{
                      borderBottom: '1px solid var(--border-hairline)',
                      backgroundColor: isSelected ? 'var(--teal-100)' : 'transparent',
                      cursor: onRowClick ? 'pointer' : 'default',
                      transition: 'background-color 0.12s ease',
                    }}
                    className="sp-table-row"
                  >
                    {columns.map((col) => (
                      <td
                        key={col.key}
                        style={{
                          padding: compact ? '0.45rem 0.75rem' : '0.65rem 1rem',
                          fontSize: 'var(--text-xs)',
                          color: 'var(--text-body)',
                          textAlign: col.align || 'left',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {col.render ? col.render(row, rIdx) : String(row[col.key] ?? '—')}
                      </td>
                    ))}
                    <td style={{ padding: '0.4rem', textAlign: 'right' }}>
                      <button
                        onClick={(e) => handleCopyRow(e, row)}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: copiedId === rowId ? 'var(--status-verified)' : 'var(--text-ghost)',
                          cursor: 'pointer',
                          padding: '0.2rem',
                          display: 'inline-flex',
                          borderRadius: 'var(--r-1)',
                        }}
                        title="Copy JSON record"
                      >
                        {copiedId === rowId ? <Check size={12} /> : <Copy size={12} />}
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination Footer */}
      {totalPages > 1 && (
        <div
          style={{
            padding: '0.6rem 1rem',
            borderTop: '1px solid var(--border-hairline)',
            backgroundColor: 'var(--bg-panel)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: 'var(--text-2xs)',
            fontFamily: 'var(--font-mono)',
            color: 'var(--text-muted)',
          }}
        >
          <div>
            Showing {(currentPage - 1) * pageSize + 1}–
            {Math.min(currentPage * pageSize, sortedData.length)} of {sortedData.length}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <button
              disabled={currentPage <= 1}
              onClick={() => setCurrentPage((p) => Math.max(p - 1, 1))}
              style={{
                background: 'none',
                border: '1px solid var(--border-hairline)',
                borderRadius: 'var(--r-1)',
                padding: '0.2rem 0.4rem',
                color: currentPage <= 1 ? 'var(--text-ghost)' : 'var(--text-primary)',
                cursor: currentPage <= 1 ? 'not-allowed' : 'pointer',
              }}
            >
              <ChevronLeft size={12} />
            </button>
            <span style={{ color: 'var(--text-primary)', padding: '0 0.25rem' }}>
              {currentPage} / {totalPages}
            </span>
            <button
              disabled={currentPage >= totalPages}
              onClick={() => setCurrentPage((p) => Math.min(p + 1, totalPages))}
              style={{
                background: 'none',
                border: '1px solid var(--border-hairline)',
                borderRadius: 'var(--r-1)',
                padding: '0.2rem 0.4rem',
                color: currentPage >= totalPages ? 'var(--text-ghost)' : 'var(--text-primary)',
                cursor: currentPage >= totalPages ? 'not-allowed' : 'pointer',
              }}
            >
              <ChevronRight size={12} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
