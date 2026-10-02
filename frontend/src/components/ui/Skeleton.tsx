/**
 * Skeleton / Loading Components — Phase 7
 */
import React from 'react';

interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  borderRadius?: string;
  style?: React.CSSProperties;
}

export function Skeleton({ width = '100%', height = 16, borderRadius = 'var(--radius-sm)', style }: SkeletonProps) {
  return (
    <div
      style={{
        width,
        height,
        borderRadius,
        backgroundColor: 'var(--bg-elevated)',
        backgroundImage: 'linear-gradient(90deg, var(--bg-elevated) 0%, var(--bg-border) 50%, var(--bg-elevated) 100%)',
        backgroundSize: '200% 100%',
        animation: 'shimmer 1.5s infinite',
        ...style,
      }}
      aria-hidden="true"
    />
  );
}

export function SkeletonCard({ lines = 3 }: { lines?: number }) {
  return (
    <div
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--bg-border)',
        borderRadius: 'var(--radius-lg)',
        padding: '1.25rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem',
      }}
    >
      <Skeleton height={20} width="40%" />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} height={14} width={i === lines - 1 ? '60%' : '100%'} />
      ))}
    </div>
  );
}

export function SkeletonKPI() {
  return (
    <div
      style={{
        backgroundColor: 'var(--bg-surface)',
        border: '1px solid var(--bg-border)',
        borderRadius: 'var(--radius-lg)',
        padding: '1.25rem',
      }}
    >
      <Skeleton height={12} width="60%" />
      <div style={{ marginTop: '0.75rem' }}>
        <Skeleton height={36} width="50%" />
      </div>
      <div style={{ marginTop: '0.5rem' }}>
        <Skeleton height={10} width="40%" />
      </div>
    </div>
  );
}
