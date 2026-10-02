import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { TimeRangeSelector } from '../components/ui/Filters';

describe('TimeRangeSelector Component', () => {
  it('renders all preset time range buttons', () => {
    const handleChange = vi.fn();
    render(<TimeRangeSelector value="24h" onChange={handleChange} />);

    expect(screen.getByText('Last 1h')).toBeInTheDocument();
    expect(screen.getByText('Last 6h')).toBeInTheDocument();
    expect(screen.getByText('Last 24h')).toBeInTheDocument();
    expect(screen.getByText('Last 7d')).toBeInTheDocument();
  });

  it('triggers onChange callback with clicked preset', () => {
    const handleChange = vi.fn();
    render(<TimeRangeSelector value="24h" onChange={handleChange} />);

    const oneHourBtn = screen.getByText('Last 1h');
    fireEvent.click(oneHourBtn);

    expect(handleChange).toHaveBeenCalledWith('1h');
  });
});
