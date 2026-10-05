/**
 * SkyPulse Design System — Core Primitives
 * "An instrument for understanding India's atmosphere."
 *
 * Implements:
 * - Premium Button System (Section 4: Ink/Ivory, Electric Teal, arrow shift 2-4px, microinteractions)
 * - Card (Section 6: Fine hairline border, small radius, zero floating glass)
 * - Input & Select (Section 24: Labels above, validation states, subtle focus glow)
 * - Modal (Section 14: Focused attention, backdrop blur, ESC & click-outside support)
 * - Tabs (Section 5: Instrument panel feel, active teal signal)
 */

import React, { useEffect, useRef } from 'react';
import { ArrowRight, Loader2 } from 'lucide-react';

// ==========================================
// 1. BUTTON SYSTEM (Section 4)
// ==========================================
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'teal' | 'secondary' | 'outline' | 'danger' | 'ghost';
  size?: 'xs' | 'sm' | 'md' | 'lg';
  icon?: React.ReactNode;
  iconPosition?: 'left' | 'right';
  loading?: boolean;
  withArrow?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  icon,
  iconPosition = 'left',
  loading = false,
  withArrow = false,
  disabled,
  style,
  className = '',
  ...props
}) => {
  const getVariantStyles = (): React.CSSProperties => {
    switch (variant) {
      case 'primary':
        // Ink background with warm ivory text and subtle border
        return {
          backgroundColor: 'var(--ink)',
          color: 'var(--ivory)',
          border: '1px solid var(--border-subtle)',
          boxShadow: '0 1px 2px rgba(0, 0, 0, 0.4)',
        };
      case 'teal':
        // Electric teal signal background with deep ink text
        return {
          backgroundColor: 'var(--teal)',
          color: 'var(--ink)',
          border: '1px solid var(--teal)',
          fontWeight: 700,
        };
      case 'secondary':
        // Subtle text with underline on hover / minimal border
        return {
          backgroundColor: 'transparent',
          color: 'var(--text-primary)',
          border: '1px solid var(--border-hairline)',
        };
      case 'outline':
        return {
          backgroundColor: 'transparent',
          color: 'var(--text-primary)',
          border: '1px solid var(--border-default)',
        };
      case 'danger':
        return {
          backgroundColor: 'var(--sev-4-dim)',
          color: 'var(--sev-4)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
        };
      case 'ghost':
        return {
          backgroundColor: 'transparent',
          color: 'var(--text-secondary)',
          border: '1px solid transparent',
        };
    }
  };

  const getSizeStyles = (): React.CSSProperties => {
    switch (size) {
      case 'xs':
        return { padding: '0.2rem 0.5rem', fontSize: 'var(--text-2xs)', gap: '0.3rem', height: 24 };
      case 'sm':
        return { padding: '0.35rem 0.75rem', fontSize: 'var(--text-xs)', gap: '0.4rem', height: 30 };
      case 'lg':
        return { padding: '0.65rem 1.4rem', fontSize: 'var(--text-base)', gap: '0.6rem', height: 44 };
      case 'md':
      default:
        return { padding: '0.5rem 1rem', fontSize: 'var(--text-sm)', gap: '0.5rem', height: 36 };
    }
  };

  return (
    <button
      disabled={disabled || loading}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: 'var(--r-2)',
        fontFamily: 'var(--font-sans)',
        fontWeight: 600,
        letterSpacing: '0.01em',
        cursor: disabled || loading ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.45 : 1,
        transition: 'all 0.18s cubic-bezier(0.16, 1, 0.3, 1)',
        whiteSpace: 'nowrap',
        userSelect: 'none',
        ...getVariantStyles(),
        ...getSizeStyles(),
        ...style,
      }}
      className={`sp-btn sp-btn-${variant} ${className}`}
      {...props}
    >
      {loading ? (
        <Loader2 size={size === 'sm' || size === 'xs' ? 12 : 14} className="sp-spin" />
      ) : (
        icon && iconPosition === 'left' && <span className="sp-btn-icon">{icon}</span>
      )}
      {children && <span>{children}</span>}
      {!loading && icon && iconPosition === 'right' && (
        <span className="sp-btn-icon">{icon}</span>
      )}
      {!loading && withArrow && (
        <ArrowRight size={size === 'sm' || size === 'xs' ? 12 : 14} className="sp-btn-arrow" />
      )}
    </button>
  );
};

// ==========================================
// 2. CARD (Section 6)
// ==========================================
interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  elevated?: boolean;
  bordered?: boolean;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  accentBorder?: 'teal' | 'sev-1' | 'sev-2' | 'sev-3' | 'sev-4';
}

export const Card: React.FC<CardProps> = ({
  children,
  elevated = false,
  bordered = true,
  padding = 'md',
  accentBorder,
  style,
  className = '',
  ...props
}) => {
  const getPadding = () => {
    switch (padding) {
      case 'none': return 0;
      case 'sm': return '0.75rem';
      case 'lg': return '1.5rem';
      case 'md':
      default: return '1rem';
    }
  };

  const getBorderColor = () => {
    if (!bordered) return 'none';
    if (accentBorder === 'teal') return '1px solid var(--border-teal)';
    if (accentBorder === 'sev-1') return '1px solid var(--sev-1)';
    if (accentBorder === 'sev-2') return '1px solid var(--sev-2)';
    if (accentBorder === 'sev-3') return '1px solid var(--sev-3)';
    if (accentBorder === 'sev-4') return '1px solid var(--sev-4)';
    return '1px solid var(--border-hairline)';
  };

  return (
    <div
      style={{
        backgroundColor: elevated ? 'var(--bg-elevated)' : 'var(--bg-surface)',
        border: getBorderColor(),
        borderRadius: 'var(--r-2)',
        padding: getPadding(),
        position: 'relative',
        transition: 'border-color 0.15s ease',
        ...style,
      }}
      className={`sp-card ${className}`}
      {...props}
    >
      {children}
    </div>
  );
};

// ==========================================
// 3. INPUT & TEXTAREA (Section 24)
// ==========================================
interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  icon?: React.ReactNode;
}

export const Input: React.FC<InputProps> = ({
  label,
  error,
  hint,
  icon,
  style,
  id,
  ...props
}) => {
  const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', width: '100%' }}>
      {label && (
        <label
          htmlFor={inputId}
          style={{
            fontSize: 'var(--text-xs)',
            fontWeight: 600,
            color: 'var(--text-secondary)',
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
            fontFamily: 'var(--font-mono)',
          }}
        >
          {label}
        </label>
      )}
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
        {icon && (
          <span
            style={{
              position: 'absolute',
              left: '0.75rem',
              color: 'var(--text-muted)',
              display: 'flex',
              pointerEvents: 'none',
            }}
          >
            {icon}
          </span>
        )}
        <input
          id={inputId}
          style={{
            width: '100%',
            backgroundColor: 'var(--bg-panel)',
            border: `1px solid ${error ? 'var(--sev-4)' : 'var(--border-hairline)'}`,
            borderRadius: 'var(--r-2)',
            color: 'var(--text-primary)',
            padding: icon ? '0.45rem 0.75rem 0.45rem 2.25rem' : '0.45rem 0.75rem',
            fontSize: 'var(--text-sm)',
            outline: 'none',
            fontFamily: 'var(--font-sans)',
            transition: 'border-color 0.18s ease, box-shadow 0.18s ease',
            ...style,
          }}
          className="sp-input"
          {...props}
        />
      </div>
      {hint && !error && (
        <span style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)' }}>{hint}</span>
      )}
      {error && (
        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--sev-4)', fontFamily: 'var(--font-mono)' }}>
          {error}
        </span>
      )}
    </div>
  );
};

// ==========================================
// 4. SELECT
// ==========================================
interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  options: { label: string; value: string | number }[];
}

export const Select: React.FC<SelectProps> = ({
  label,
  options,
  style,
  id,
  ...props
}) => {
  const selectId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
      {label && (
        <label
          htmlFor={selectId}
          style={{
            fontSize: 'var(--text-xs)',
            fontWeight: 600,
            color: 'var(--text-secondary)',
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
            fontFamily: 'var(--font-mono)',
          }}
        >
          {label}
        </label>
      )}
      <select
        id={selectId}
        style={{
          backgroundColor: 'var(--bg-panel)',
          border: '1px solid var(--border-hairline)',
          borderRadius: 'var(--r-2)',
          color: 'var(--text-primary)',
          padding: '0.45rem 0.75rem',
          fontSize: 'var(--text-sm)',
          outline: 'none',
          cursor: 'pointer',
          fontFamily: 'var(--font-sans)',
          transition: 'border-color 0.18s ease',
          ...style,
        }}
        className="sp-select"
        {...props}
      >
        {options.map((opt) => (
          <option
            key={opt.value}
            value={opt.value}
            style={{ backgroundColor: 'var(--bg-surface)', color: 'var(--text-primary)' }}
          >
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
};

// ==========================================
// 5. MODAL / DIALOG (Section 14)
// ==========================================
interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  maxWidth?: string;
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  subtitle,
  children,
  footer,
  maxWidth = '560px',
}) => {
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        backgroundColor: 'rgba(11, 13, 13, 0.82)',
        backdropFilter: 'blur(6px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1.25rem',
        animation: 'fade-in 0.2s ease-out',
      }}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        ref={modalRef}
        style={{
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--r-3)',
          width: '100%',
          maxWidth,
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 20px 40px rgba(0,0,0,0.6)',
          overflow: 'hidden',
          animation: 'scale-up 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '1.25rem 1.5rem',
            borderBottom: '1px solid var(--border-hairline)',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
          }}
        >
          <div>
            <h3
              style={{
                fontSize: 'var(--text-lg)',
                fontWeight: 700,
                color: 'var(--text-primary)',
                fontFamily: 'var(--font-sans)',
                margin: 0,
                letterSpacing: '-0.01em',
              }}
            >
              {title}
            </h3>
            {subtitle && (
              <div
                style={{
                  fontSize: 'var(--text-xs)',
                  color: 'var(--text-muted)',
                  marginTop: '0.25rem',
                  fontFamily: 'var(--font-mono)',
                }}
              >
                {subtitle}
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              fontSize: '1.1rem',
              display: 'flex',
              padding: '0.25rem',
              lineHeight: 1,
              borderRadius: 'var(--r-1)',
              transition: 'color 0.15s ease',
            }}
            aria-label="Close dialog"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '1.5rem', overflowY: 'auto', flex: 1 }}>{children}</div>

        {/* Footer */}
        {footer && (
          <div
            style={{
              padding: '1rem 1.5rem',
              borderTop: '1px solid var(--border-hairline)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-end',
              gap: '0.75rem',
              backgroundColor: 'var(--bg-panel)',
            }}
          >
            {footer}
          </div>
        )}
      </div>
    </div>
  );
};

// ==========================================
// 6. TABS (Section 5)
// ==========================================
interface TabsProps {
  tabs: { id: string; label: string; count?: number; icon?: React.ReactNode }[];
  activeTab: string;
  onChange: (tabId: string) => void;
}

export const Tabs: React.FC<TabsProps> = ({ tabs, activeTab, onChange }) => {
  return (
    <div
      style={{
        display: 'flex',
        borderBottom: '1px solid var(--border-hairline)',
        gap: '0.25rem',
        overflowX: 'auto',
      }}
      role="tablist"
    >
      {tabs.map((tab) => {
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(tab.id)}
            style={{
              background: 'none',
              border: 'none',
              borderBottom: `2px solid ${isActive ? 'var(--teal)' : 'transparent'}`,
              color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
              fontWeight: isActive ? 700 : 500,
              padding: '0.6rem 0.9rem',
              fontSize: 'var(--text-xs)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.45rem',
              whiteSpace: 'nowrap',
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
              transition: 'all 0.15s ease',
            }}
          >
            {tab.icon}
            {tab.label}
            {tab.count !== undefined && (
              <span
                style={{
                  fontSize: 'var(--text-2xs)',
                  padding: '0.1rem 0.45rem',
                  borderRadius: 'var(--r-full)',
                  backgroundColor: isActive ? 'var(--teal-100)' : 'var(--bg-elevated)',
                  color: isActive ? 'var(--teal)' : 'var(--text-muted)',
                  fontWeight: 600,
                }}
              >
                {tab.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
};
