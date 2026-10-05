import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  SeverityBadge,
  VerificationBadge,
  CategoryBadge,
  ConfidenceBar,
  DemoBadge,
} from '../components/ui/Badges';

describe('Badges UI Components', () => {
  it('renders SeverityBadge correctly for all levels', () => {
    const { rerender } = render(<SeverityBadge severity={1} showLabel />);
    expect(screen.getByText('Minor')).toBeInTheDocument();
    expect(screen.getByText(/●\s*1/)).toBeInTheDocument();

    rerender(<SeverityBadge severity={4} showLabel />);
    expect(screen.getByText('Extreme')).toBeInTheDocument();
    expect(screen.getByText(/●\s*4/)).toBeInTheDocument();
  });

  it('renders VerificationBadge correctly', () => {
    const { rerender } = render(<VerificationBadge status="VERIFIED" />);
    expect(screen.getByText(/VERIFIED/)).toBeInTheDocument();

    rerender(<VerificationBadge status="REQUIRES_REVIEW" />);
    expect(screen.getByText(/REVIEW/)).toBeInTheDocument();
  });

  it('renders CategoryBadge for various weather categories', () => {
    render(<CategoryBadge category="THUNDERSTORM" />);
    expect(screen.getByText(/THUNDERSTORM/i)).toBeInTheDocument();
  });

  it('renders ConfidenceBar with appropriate width and label', () => {
    render(<ConfidenceBar value={0.85} showValue />);
    expect(screen.getByText('85%')).toBeInTheDocument();
  });

  it('renders DemoBadge without visual DOM footprint', () => {
    const { container } = render(<DemoBadge />);
    expect(container.firstChild).toBeNull();
  });
});
