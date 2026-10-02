import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ErrorState, EmptyState, OfflineBanner } from '../components/ui/States';
import { Skeleton, SkeletonCard } from '../components/ui/Skeleton';

describe('States UI Components', () => {
  describe('ErrorState', () => {
    it('renders title, error message, and triggers retry callback', () => {
      const handleRetry = vi.fn();
      render(
        <ErrorState
          title="Connection Timed Out"
          message="Failed to connect to backend API server."
          onRetry={handleRetry}
        />
      );

      expect(screen.getByText('Connection Timed Out')).toBeInTheDocument();
      expect(screen.getByText('Failed to connect to backend API server.')).toBeInTheDocument();

      const retryBtn = screen.getByRole('button', { name: /retry/i });
      expect(retryBtn).toBeInTheDocument();
      fireEvent.click(retryBtn);
      expect(handleRetry).toHaveBeenCalledTimes(1);
    });
  });

  describe('EmptyState', () => {
    it('renders title and message or description', () => {
      render(
        <EmptyState
          title="No Active Alerts"
          description="There are currently no active weather alerts in this zone."
          action={<button>Reset Filters</button>}
        />
      );

      expect(screen.getByText('No Active Alerts')).toBeInTheDocument();
      expect(
        screen.getByText('There are currently no active weather alerts in this zone.')
      ).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Reset Filters' })).toBeInTheDocument();
    });
  });

  describe('OfflineBanner', () => {
    it('renders offline warning banner with alert text', () => {
      render(<OfflineBanner />);
      expect(screen.getByText(/LIVE CONNECTION LOST/i)).toBeInTheDocument();
    });
  });

  describe('Skeleton components', () => {
    it('renders Skeleton box and SkeletonCard shimmer container', () => {
      const { container } = render(
        <div>
          <Skeleton width="100px" height="20px" />
          <SkeletonCard />
        </div>
      );
      expect(container.firstChild).toBeInTheDocument();
    });
  });
});
