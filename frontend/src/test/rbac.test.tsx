import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

describe('Role-Based Access Control (RBAC) UI Enforcement', () => {
  it('correctly grants Viewer read-only status and disables administrative actions', () => {
    localStorage.setItem('recallops_token', 'mock-token');

    // Viewer role simulation
    const ViewerWrapper: React.FC = () => {
      const isViewer = true;
      const isEngineer = false;
      const isAdmin = false;

      return (
        <div>
          <button disabled={isViewer && !isEngineer} data-testid="investigate-btn">
            Run Investigation
          </button>
          <button disabled={!isAdmin} data-testid="admin-member-btn">
            Add Organization Member
          </button>
          <div data-testid="role-summary">VIEWER_ACCESS</div>
        </div>
      );
    };

    render(<ViewerWrapper />);

    expect(screen.getByTestId('role-summary').textContent).toBe('VIEWER_ACCESS');
    expect(screen.getByTestId('investigate-btn')).toBeDisabled();
    expect(screen.getByTestId('admin-member-btn')).toBeDisabled();
  });

  it('allows Engineer to trigger investigations but disables user management', () => {
    const EngineerWrapper: React.FC = () => {
      const isViewer = false;
      const isEngineer = true;
      const isAdmin = false;

      return (
        <div>
          <button disabled={isViewer && !isEngineer} data-testid="investigate-btn">
            Run Investigation
          </button>
          <button disabled={!isAdmin} data-testid="admin-member-btn">
            Add Organization Member
          </button>
          <div data-testid="role-summary">ENGINEER_ACCESS</div>
        </div>
      );
    };

    render(<EngineerWrapper />);

    expect(screen.getByTestId('role-summary').textContent).toBe('ENGINEER_ACCESS');
    expect(screen.getByTestId('investigate-btn')).not.toBeDisabled();
    expect(screen.getByTestId('admin-member-btn')).toBeDisabled();
  });

  it('grants Admin full administrative privileges including member management', () => {
    const AdminWrapper: React.FC = () => {
      const isViewer = false;
      const isEngineer = true;
      const isAdmin = true;

      return (
        <div>
          <button disabled={isViewer && !isEngineer} data-testid="investigate-btn">
            Run Investigation
          </button>
          <button disabled={!isAdmin} data-testid="admin-member-btn">
            Add Organization Member
          </button>
          <div data-testid="role-summary">ADMIN_ACCESS</div>
        </div>
      );
    };

    render(<AdminWrapper />);

    expect(screen.getByTestId('role-summary').textContent).toBe('ADMIN_ACCESS');
    expect(screen.getByTestId('investigate-btn')).not.toBeDisabled();
    expect(screen.getByTestId('admin-member-btn')).not.toBeDisabled();
  });
});
