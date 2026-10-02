/**
 * SkyPulse Design System — Core Primitives
 * Button, Input, Select, Card, Modal, Tabs
 */
import React from 'react';

// ==========================================
// BUTTON
// ==========================================
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'danger' | 'ghost' | 'success';
  size?: 'sm' | 'md' | 'lg';
  icon?: React.ReactNode;
  loading?: boolean;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  icon,
  loading = false,
  disabled,
  style,
  className = '',
  ...props
}) => {
  const getVariantStyles = (): React.CSSProperties => {
    switch (variant) {
      case 'primary':
        return {
          backgroundColor: 'var(--brand-blue)',
          color: '#ffffff',
          border: '1px solid var(--brand-blue)',
        };
      case 'secondary':
        return {
          backgroundColor: 'var(--bg-elevated)',
          color: 'var(--text-primary)',
          border: '1px solid var(--bg-border)',
        };
      case 'outline':
        return {
          backgroundColor: 'transparent',
          color: 'var(--text-primary)',
          border: '1px solid var(--bg-border)',
        };
      case 'danger':
        return {
          backgroundColor: 'rgba(239, 68, 68, 0.15)',
          color: 'var(--severity-4)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
        };
      case 'success':
        return {
          backgroundColor: 'rgba(34, 197, 94, 0.15)',
          color: 'var(--severity-1)',
          border: '1px solid rgba(34, 197, 94, 0.3)',
        };
      case 'ghost':
        return {
          backgroundColor: 'transparent',
          color: 'var(--text-secondary)',
          border: 'none',
        };
    }
  };

  const getSizeStyles = (): React.CSSProperties => {
    switch (size) {
      case 'sm':
        return { padding: '0.25rem 0.6rem', fontSize: 'var(--text-xs)', gap: '0.35rem' };
      case 'lg':
        return { padding: '0.75rem 1.5rem', fontSize: 'var(--text-base)', gap: '0.6rem' };
      case 'md':
      default:
        return { padding: '0.45rem 1rem', fontSize: 'var(--text-sm)', gap: '0.5rem' };
    }
  };

  return (
    <button
      disabled={disabled || loading}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: 'var(--radius-md)',
        fontWeight: 500,
        fontFamily: 'inherit',
        cursor: disabled || loading ? 'not-allowed' : 'pointer',
        opacity: disabled || loading ? 0.6 : 1,
        transition: 'all 0.15s ease',
        ...getVariantStyles(),
        ...getSizeStyles(),
        ...style,
      }}
      className={`sp-button ${className}`}
      {...props}
    >
      {loading ? (
        <span
          style={{
            width: 14,
            height: 14,
            border: '2px solid currentColor',
            borderRightColor: 'transparent',
            borderRadius: '50%',
            animation: 'spin 0.75s linear infinite',
            display: 'inline-block',
          }}
        />
      ) : (
        icon
      )}
      {children}
    </button>
  );
};

// ==========================================
// CARD
// ==========================================
interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  elevated?: boolean;
  bordered?: boolean;
  padding?: 'none' | 'sm' | 'md' | 'lg';
}

export const Card: React.FC<CardProps> = ({
  children,
  elevated = false,
  bordered = true,
  padding = 'md',
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

  return (
    <div
      style={{
        backgroundColor: elevated ? 'var(--bg-elevated)' : 'var(--bg-surface)',
        border: bordered ? '1px solid var(--bg-border)' : 'none',
        borderRadius: 'var(--radius-lg)',
        padding: getPadding(),
        boxShadow: elevated ? 'var(--shadow-md)' : 'none',
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
// INPUT & TEXTAREA
// ==========================================
interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  icon?: React.ReactNode;
}

export const Input: React.FC<InputProps> = ({
  label,
  error,
  icon,
  style,
  id,
  ...props
}) => {
  const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', width: '100%' }}>
      {label && (
        <label htmlFor={inputId} style={{ fontSize: 'var(--text-xs)', fontWeight: 500, color: 'var(--text-secondary)' }}>
          {label}
        </label>
      )}
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
        {icon && (
          <span style={{ position: 'absolute', left: '0.75rem', color: 'var(--text-muted)', display: 'flex' }}>
            {icon}
          </span>
        )}
        <input
          id={inputId}
          style={{
            width: '100%',
            backgroundColor: 'var(--bg-primary)',
            border: `1px solid ${error ? 'var(--severity-4)' : 'var(--bg-border)'}`,
            borderRadius: 'var(--radius-md)',
            color: 'var(--text-primary)',
            padding: icon ? '0.45rem 0.75rem 0.45rem 2.25rem' : '0.45rem 0.75rem',
            fontSize: 'var(--text-sm)',
            outline: 'none',
            fontFamily: 'inherit',
            transition: 'border-color 0.15s ease',
            ...style,
          }}
          {...props}
        />
      </div>
      {error && (
        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--severity-4)' }}>{error}</span>
      )}
    </div>
  );
};

// ==========================================
// SELECT
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
        <label htmlFor={selectId} style={{ fontSize: 'var(--text-xs)', fontWeight: 500, color: 'var(--text-secondary)' }}>
          {label}
        </label>
      )}
      <select
        id={selectId}
        style={{
          backgroundColor: 'var(--bg-primary)',
          border: '1px solid var(--bg-border)',
          borderRadius: 'var(--radius-md)',
          color: 'var(--text-primary)',
          padding: '0.45rem 0.75rem',
          fontSize: 'var(--text-sm)',
          outline: 'none',
          cursor: 'pointer',
          fontFamily: 'inherit',
          ...style,
        }}
        {...props}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value} style={{ backgroundColor: 'var(--bg-elevated)', color: 'var(--text-primary)' }}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
};

// ==========================================
// MODAL / DIALOG
// ==========================================
interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  maxWidth?: string;
}

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  title,
  children,
  footer,
  maxWidth = '550px',
}) => {
  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1rem',
      }}
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--bg-border)',
          borderRadius: 'var(--radius-lg)',
          width: '100%',
          maxWidth,
          maxHeight: '90vh',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: 'var(--shadow-lg)',
          overflow: 'hidden',
          animation: 'fadeSlideIn 0.2s ease-out',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '1rem 1.25rem',
            borderBottom: '1px solid var(--bg-border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--text-primary)', margin: 0 }}>
            {title}
          </h3>
          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              fontSize: '1.25rem',
              display: 'flex',
              padding: '0.2rem',
            }}
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '1.25rem', overflowY: 'auto', flex: 1 }}>{children}</div>

        {/* Footer */}
        {footer && (
          <div
            style={{
              padding: '0.75rem 1.25rem',
              borderTop: '1px solid var(--bg-border)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-end',
              gap: '0.75rem',
              backgroundColor: 'var(--bg-elevated)',
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
// TABS
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
        borderBottom: '1px solid var(--bg-border)',
        gap: '0.25rem',
        overflowX: 'auto',
      }}
    >
      {tabs.map((tab) => {
        const isActive = activeTab === tab.id;
        return (
          <button
            key={tab.id}
            onClick={() => onChange(tab.id)}
            style={{
              background: 'none',
              border: 'none',
              borderBottom: `2px solid ${isActive ? 'var(--brand-blue)' : 'transparent'}`,
              color: isActive ? 'var(--brand-blue)' : 'var(--text-secondary)',
              fontWeight: isActive ? 600 : 400,
              padding: '0.6rem 1rem',
              fontSize: 'var(--text-sm)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              whiteSpace: 'nowrap',
              transition: 'all 0.15s ease',
            }}
          >
            {tab.icon}
            {tab.label}
            {tab.count !== undefined && (
              <span
                style={{
                  fontSize: 'var(--text-xs)',
                  padding: '0.1rem 0.4rem',
                  borderRadius: 'var(--radius-full)',
                  backgroundColor: isActive ? 'rgba(59, 130, 246, 0.2)' : 'var(--bg-elevated)',
                  color: isActive ? 'var(--brand-blue)' : 'var(--text-muted)',
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
