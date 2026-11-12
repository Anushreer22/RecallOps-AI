import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { authApi, LoginParams, RegisterParams } from '../api/auth';
import { User, Membership, Project, UserRole, Organization } from '../types';

interface AuthContextType {
  user: User | null;
  token: string | null;
  activeOrg: Membership | null;
  activeProject: Project | null;
  organizations: Organization[];
  role: UserRole | null;
  isLoading: boolean;
  loading: boolean;
  isAuthenticated: boolean;
  isAdmin: boolean;
  isEngineer: boolean;
  isViewer: boolean;
  login: (params: LoginParams) => Promise<void>;
  register: (params: RegisterParams) => Promise<void>;
  logout: () => void;
  switchOrganization: (orgId: string) => void;
  switchProject: (project: Project | null) => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('recallops_token'));
  const [activeOrg, setActiveOrg] = useState<Membership | null>(null);
  const [activeProject, setActiveProject] = useState<Project | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const resolveActiveOrg = useCallback((currentUser?: User | null, preferredOrgId?: string | null) => {
    if (!currentUser || !currentUser.memberships || currentUser.memberships.length === 0) {
      setActiveOrg(null);
      return;
    }
    const targetId = preferredOrgId || localStorage.getItem('recallops_org_id');
    const matched = currentUser.memberships.find((m) => m.organization_id === targetId);
    const selected = matched || currentUser.memberships[0];

    setActiveOrg(selected);
    localStorage.setItem('recallops_org_id', selected.organization_id);
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const me = await authApi.getMe();
      if (me) {
        setUser(me);
        resolveActiveOrg(me);
      }
    } catch (err) {
      console.error('Failed to rehydrate session:', err);
      localStorage.removeItem('recallops_token');
      localStorage.removeItem('recallops_org_id');
      setToken(null);
      setUser(null);
      setActiveOrg(null);
    } finally {
      setIsLoading(false);
    }
  }, [resolveActiveOrg]);

  useEffect(() => {
    if (token) {
      refreshUser();
    } else {
      setIsLoading(false);
    }
  }, [token, refreshUser]);

  const login = async (params: LoginParams) => {
    setIsLoading(true);
    try {
      const resp = await authApi.login(params);
      localStorage.setItem('recallops_token', resp.access_token);
      setToken(resp.access_token);
      setUser(resp.user);
      resolveActiveOrg(resp.user);
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (params: RegisterParams) => {
    setIsLoading(true);
    try {
      const resp = await authApi.register(params);
      localStorage.setItem('recallops_token', resp.access_token);
      setToken(resp.access_token);
      setUser(resp.user);
      resolveActiveOrg(resp.user);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    localStorage.removeItem('recallops_token');
    localStorage.removeItem('recallops_org_id');
    setToken(null);
    setUser(null);
    setActiveOrg(null);
    setActiveProject(null);
  };

  const switchOrganization = (orgId: string) => {
    if (!user) return;
    const matched = user.memberships.find((m) => m.organization_id === orgId);
    if (matched) {
      setActiveOrg(matched);
      localStorage.setItem('recallops_org_id', matched.organization_id);
      setActiveProject(null); // Reset active project on org switch
    }
  };

  const switchProject = (project: Project | null) => {
    setActiveProject(project);
  };

  const role = activeOrg?.role || null;
  const isAdmin = role === 'ADMIN';
  const isEngineer = role === 'ADMIN' || role === 'ENGINEER';
  const isViewer = role === 'VIEWER';

  const organizations: Organization[] = useMemo(() => {
    if (!user?.memberships) return [];
    return user.memberships.map((m) => ({
      id: m.organization_id,
      name: m.organization_name,
      slug: m.organization_slug,
      created_at: m.created_at,
    }));
  }, [user]);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        activeOrg,
        activeProject,
        organizations,
        role,
        isLoading,
        loading: isLoading,
        isAuthenticated: Boolean(token && user),
        isAdmin,
        isEngineer,
        isViewer,
        login,
        register,
        logout,
        switchOrganization,
        switchProject,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
