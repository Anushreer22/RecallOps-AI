import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AuthProvider, useAuth } from '../context/AuthContext';
import { authApi } from '../api/auth';
import { LoginPage } from '../pages/auth/LoginPage';
import { UserRole } from '../types';

vi.mock('../api/auth', () => ({
  authApi: {
    login: vi.fn(),
    register: vi.fn(),
    getMe: vi.fn(),
  },
}));

const renderWithProviders = (ui: React.ReactElement) => {
  return render(
    <BrowserRouter>
      <AuthProvider>{ui}</AuthProvider>
    </BrowserRouter>
  );
};

describe('Authentication & Session Management', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('renders login form with email, password inputs and submit button', () => {
    renderWithProviders(<LoginPage />);

    expect(screen.getByText(/Sign In to/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText('sre@company.com')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('••••••••••••')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('handles successful login and saves JWT token to localStorage', async () => {
    const mockUser = {
      id: 'usr-123',
      email: 'sre@recallops.io',
      full_name: 'Lead SRE',
      is_active: true,
      is_superuser: false,
      created_at: new Date().toISOString(),
      memberships: [
        {
          id: 'mem-1',
          organization_id: 'org-1',
          organization_name: 'Acme Corp',
          organization_slug: 'acme-corp',
          role: UserRole.ENGINEER,
          created_at: new Date().toISOString(),
        },
      ],
    };

    (authApi.login as any).mockResolvedValueOnce({
      access_token: 'test-jwt-token-xyz',
      token_type: 'bearer',
      expires_in: 3600,
      user: mockUser,
    });

    renderWithProviders(<LoginPage />);

    fireEvent.change(screen.getByPlaceholderText('sre@company.com'), {
      target: { value: 'sre@recallops.io' },
    });
    fireEvent.change(screen.getByPlaceholderText('••••••••••••'), {
      target: { value: 'CorrectHorseBatteryStaple!' },
    });

    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(authApi.login).toHaveBeenCalledWith({
        email: 'sre@recallops.io',
        password: 'CorrectHorseBatteryStaple!',
      });
      expect(localStorage.getItem('recallops_token')).toBe('test-jwt-token-xyz');
      expect(localStorage.getItem('recallops_org_id')).toBe('org-1');
    });
  });

  it('displays error message when login credentials are invalid', async () => {
    (authApi.login as any).mockRejectedValueOnce({
      response: {
        data: { detail: 'Invalid authentication credentials' },
      },
    });

    renderWithProviders(<LoginPage />);

    fireEvent.change(screen.getByPlaceholderText('sre@company.com'), {
      target: { value: 'wrong@company.com' },
    });
    fireEvent.change(screen.getByPlaceholderText('••••••••••••'), {
      target: { value: 'WrongPassword' },
    });

    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText('Invalid authentication credentials')).toBeInTheDocument();
    });
  });

  it('clears token and session state on logout', async () => {
    (authApi.getMe as any).mockResolvedValueOnce({
      id: 'usr-123',
      email: 'sre@recallops.io',
      full_name: 'Lead SRE',
      memberships: [],
    });

    localStorage.setItem('recallops_token', 'active-token');
    localStorage.setItem('recallops_org_id', 'org-1');

    const TestComponent = () => {
      const { isAuthenticated, logout } = useAuth();
      return (
        <div>
          <span data-testid="auth-status">{isAuthenticated ? 'LOGGED_IN' : 'LOGGED_OUT'}</span>
          <button onClick={logout}>Logout</button>
        </div>
      );
    };

    renderWithProviders(<TestComponent />);

    fireEvent.click(screen.getByText('Logout'));

    expect(localStorage.getItem('recallops_token')).toBeNull();
    expect(localStorage.getItem('recallops_org_id')).toBeNull();
    expect(screen.getByTestId('auth-status').textContent).toBe('LOGGED_OUT');
  });
});
