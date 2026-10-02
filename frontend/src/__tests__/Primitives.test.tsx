import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import {
  Button,
  Card,
  Input,
  Select,
  Modal,
  Tabs,
} from '../components/ui/Primitives';

describe('UI Primitives — Design System Components', () => {
  describe('Button', () => {
    it('renders with text and handles click events', () => {
      const handleClick = vi.fn();
      render(<Button onClick={handleClick}>Click Me</Button>);

      const btn = screen.getByRole('button', { name: 'Click Me' });
      expect(btn).toBeInTheDocument();
      fireEvent.click(btn);
      expect(handleClick).toHaveBeenCalledTimes(1);
    });

    it('disables button when disabled or loading prop is set', () => {
      const handleClick = vi.fn();
      const { rerender } = render(
        <Button disabled onClick={handleClick}>
          Disabled
        </Button>
      );
      const btn = screen.getByRole('button', { name: 'Disabled' });
      expect(btn).toBeDisabled();
      fireEvent.click(btn);
      expect(handleClick).not.toHaveBeenCalled();

      rerender(
        <Button loading onClick={handleClick}>
          Loading
        </Button>
      );
      expect(btn).toBeDisabled();
    });

    it('renders different visual variants correctly', () => {
      const { rerender } = render(<Button variant="danger">Delete</Button>);
      expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument();

      rerender(<Button variant="success">Confirm</Button>);
      expect(screen.getByRole('button', { name: 'Confirm' })).toBeInTheDocument();

      rerender(<Button variant="ghost">Dismiss</Button>);
      expect(screen.getByRole('button', { name: 'Dismiss' })).toBeInTheDocument();
    });
  });

  describe('Card', () => {
    it('renders children with elevated and bordered styling', () => {
      render(
        <Card elevated bordered padding="lg">
          <div>Card Content</div>
        </Card>
      );
      expect(screen.getByText('Card Content')).toBeInTheDocument();
    });
  });

  describe('Input', () => {
    it('renders with label and handles text change', () => {
      const handleChange = vi.fn();
      render(
        <Input
          label="Search Events"
          placeholder="Type here..."
          value=""
          onChange={handleChange}
        />
      );

      expect(screen.getByLabelText('Search Events')).toBeInTheDocument();
      const input = screen.getByPlaceholderText('Type here...');
      fireEvent.change(input, { target: { value: 'Cyclone' } });
      expect(handleChange).toHaveBeenCalled();
    });

    it('renders error message when error prop is provided', () => {
      render(<Input label="Username" error="Field is required" />);
      expect(screen.getByText('Field is required')).toBeInTheDocument();
    });
  });

  describe('Select', () => {
    it('renders label and options and triggers onChange', () => {
      const handleChange = vi.fn();
      const options = [
        { label: 'Option A', value: 'A' },
        { label: 'Option B', value: 'B' },
      ];
      render(
        <Select
          label="Category Select"
          options={options}
          value="A"
          onChange={handleChange}
        />
      );

      expect(screen.getByLabelText('Category Select')).toBeInTheDocument();
      const select = screen.getByRole('combobox');
      fireEvent.change(select, { target: { value: 'B' } });
      expect(handleChange).toHaveBeenCalled();
    });
  });

  describe('Modal', () => {
    it('renders modal when isOpen is true and handles close button click', () => {
      const handleClose = vi.fn();
      render(
        <Modal
          isOpen={true}
          onClose={handleClose}
          title="Inspection Modal"
          footer={<button>Confirm</button>}
        >
          <p>Modal Body Content</p>
        </Modal>
      );

      expect(screen.getByText('Inspection Modal')).toBeInTheDocument();
      expect(screen.getByText('Modal Body Content')).toBeInTheDocument();
      expect(screen.getByText('Confirm')).toBeInTheDocument();

      const closeBtn = screen.getByText('✕');
      fireEvent.click(closeBtn);
      expect(handleClose).toHaveBeenCalledTimes(1);
    });

    it('does not render modal when isOpen is false', () => {
      render(
        <Modal isOpen={false} onClose={() => {}} title="Hidden Modal">
          <p>Hidden Content</p>
        </Modal>
      );
      expect(screen.queryByText('Hidden Modal')).not.toBeInTheDocument();
    });
  });

  describe('Tabs', () => {
    it('renders tabs list with counts and switches active tab on click', () => {
      const handleChange = vi.fn();
      const tabs = [
        { id: 'tab-1', label: 'Overview', count: 12 },
        { id: 'tab-2', label: 'Signals', count: 4 },
      ];
      render(
        <Tabs tabs={tabs} activeTab="tab-1" onChange={handleChange} />
      );

      expect(screen.getByText('Overview')).toBeInTheDocument();
      expect(screen.getByText('12')).toBeInTheDocument();
      expect(screen.getByText('Signals')).toBeInTheDocument();
      expect(screen.getByText('4')).toBeInTheDocument();

      const secondTab = screen.getByText('Signals');
      fireEvent.click(secondTab);
      expect(handleChange).toHaveBeenCalledWith('tab-2');
    });
  });
});
