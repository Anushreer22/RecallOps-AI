import React, { useState, useEffect } from 'react';
import {
  Building2,
  Users,
  Shield,
  Plus,
  RefreshCw,
  UserCheck,
  CheckCircle2,
  Database,
  Lock,
} from 'lucide-react';
import { organizationsApi } from '../../api/organizations';
import { MemberDetail, UserRole } from '../../types';
import { Card, CardHeader, CardBody } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Modal } from '../../components/ui/Modal';
import { Input, Select } from '../../components/ui/Input';
import { Badge, RoleBadge } from '../../components/ui/Badge';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { useAuth } from '../../context/AuthContext';

export const SettingsPage: React.FC = () => {
  const { user: _user, activeOrg, organizations, switchOrganization, isAdmin, role } = useAuth();

  const [members, setMembers] = useState<MemberDetail[]>([]);
  const [loadingMembers, setLoadingMembers] = useState(false);

  // Add Member Modal
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [newRole, setNewRole] = useState<UserRole>(UserRole.ENGINEER);
  const [submittingMember, setSubmittingMember] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Create Org Modal
  const [createOrgOpen, setCreateOrgOpen] = useState(false);
  const [newOrgName, setNewOrgName] = useState('');
  const [creatingOrg, setCreatingOrg] = useState(false);

  const fetchMembers = async () => {
    if (!activeOrg?.id) return;
    setLoadingMembers(true);
    try {
      const data = await organizationsApi.listMembers(activeOrg.id);
      setMembers(data);
    } catch (err: any) {
      console.error('Failed to load members', err);
    } finally {
      setLoadingMembers(false);
    }
  };

  useEffect(() => {
    fetchMembers();
  }, [activeOrg?.id]);

  const handleAddMember = async () => {
    if (!activeOrg?.id || !newEmail.trim()) {
      alert('Email is required.');
      return;
    }
    setSubmittingMember(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      await organizationsApi.addMember(activeOrg.id, {
        email: newEmail.trim().toLowerCase(),
        role: newRole,
      });
      setAddModalOpen(false);
      setNewEmail('');
      setSuccessMsg(`Member ${newEmail} added successfully.`);
      await fetchMembers();
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || err.message || 'Failed to add member');
    } finally {
      setSubmittingMember(false);
    }
  };

  const handleRoleChange = async (userId: string, role: UserRole) => {
    if (!activeOrg?.id || !isAdmin) return;
    try {
      await organizationsApi.updateMemberRole(activeOrg.id, userId, role);
      setSuccessMsg('Member role updated.');
      await fetchMembers();
    } catch (err: any) {
      alert(err.response?.data?.detail || err.message || 'Failed to update member role');
    }
  };

  const handleCreateOrg = async () => {
    if (!newOrgName.trim()) return;
    setCreatingOrg(true);
    try {
      const created = await organizationsApi.create({ name: newOrgName.trim() });
      setCreateOrgOpen(false);
      setNewOrgName('');
      switchOrganization(created.id);
      window.location.reload();
    } catch (err: any) {
      alert(err.response?.data?.detail || err.message || 'Failed to create organization');
    } finally {
      setCreatingOrg(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-surface-200 dark:border-surface-800 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-surface-900 dark:text-white">
              Organization & Access Control
            </h1>
            <Badge variant="blue" size="sm">
              <Shield className="w-3 h-3 mr-1" />
              Multi-Tenant RBAC
            </Badge>
          </div>
          <p className="text-sm text-surface-500 dark:text-surface-400 mt-1">
            Manage tenant boundaries, team permissions, security configurations, and user membership.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button variant="outline" size="sm" onClick={() => setCreateOrgOpen(true)}>
            <Building2 className="w-4 h-4 mr-1.5" />
            New Organization
          </Button>
        </div>
      </div>

      {successMsg && (
        <div className="p-4 rounded-lg bg-success-500/10 border border-success-500/20 text-success-500 text-sm flex items-center justify-between">
          <span className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4" />
            {successMsg}
          </span>
          <button onClick={() => setSuccessMsg(null)} className="text-xs font-semibold hover:underline">
            Dismiss
          </button>
        </div>
      )}

      {/* Organization Details Card */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-1">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Building2 className="w-4 h-4 text-brand-500" />
              <h3 className="text-base font-semibold text-surface-900 dark:text-white">
                Active Organization
              </h3>
            </div>
          </CardHeader>
          <CardBody className="space-y-4 text-xs">
            <div>
              <span className="text-surface-500 block">Organization Name</span>
              <span className="text-sm font-bold text-surface-900 dark:text-white">
                {activeOrg?.organization_name || activeOrg?.name || 'Default Organization'}
              </span>
            </div>

            <div>
              <span className="text-surface-500 block">Tenant Identifier</span>
              <span className="font-mono text-xs text-surface-600 dark:text-surface-300">
                {activeOrg?.id || '—'}
              </span>
            </div>

            <div>
              <span className="text-surface-500 block">Your Role</span>
              <div className="mt-1">
                <RoleBadge role={role || UserRole.VIEWER} />
              </div>
            </div>

            <div className="pt-3 border-t border-surface-200 dark:border-surface-800">
              <span className="text-surface-500 block mb-2">Switch Tenant:</span>
              <select
                value={activeOrg?.id || ''}
                onChange={(e) => switchOrganization(e.target.value)}
                className="w-full bg-surface-50 dark:bg-surface-900 border border-surface-300 dark:border-surface-700 text-surface-900 dark:text-surface-100 text-xs rounded-lg px-3 py-2"
              >
                {organizations.map((org) => (
                  <option key={org.id} value={org.id}>
                    {org.name}
                  </option>
                ))}
              </select>
            </div>
          </CardBody>
        </Card>

        {/* Security & Engine Settings Overview */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center gap-2">
              <Lock className="w-4 h-4 text-brand-500" />
              <h3 className="text-base font-semibold text-surface-900 dark:text-white">
                Platform Security Architecture
              </h3>
            </div>
          </CardHeader>
          <CardBody className="space-y-4 text-xs">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-3 rounded-lg bg-surface-50 dark:bg-surface-800/40 border border-surface-200 dark:border-surface-800 space-y-1">
                <span className="font-semibold text-surface-900 dark:text-white flex items-center gap-1.5">
                  <Database className="w-3.5 h-3.5 text-brand-500" />
                  Episodic Memory Persistence
                </span>
                <p className="text-surface-600 dark:text-surface-400">
                  Relational DB backing with persistent rehydration on startup. Unverified diagnoses are never indexed.
                </p>
              </div>

              <div className="p-3 rounded-lg bg-surface-50 dark:bg-surface-800/40 border border-surface-200 dark:border-surface-800 space-y-1">
                <span className="font-semibold text-surface-900 dark:text-white flex items-center gap-1.5">
                  <Lock className="w-3.5 h-3.5 text-emerald-500" />
                  Argon2id & JWT Authentication
                </span>
                <p className="text-surface-600 dark:text-surface-400">
                  RFC 9106 Argon2id password hashing, PyJWT bearer token authorization, and tenant isolation headers.
                </p>
              </div>

              <div className="p-3 rounded-lg bg-surface-50 dark:bg-surface-800/40 border border-surface-200 dark:border-surface-800 space-y-1">
                <span className="font-semibold text-surface-900 dark:text-white flex items-center gap-1.5">
                  <Shield className="w-3.5 h-3.5 text-blue-500" />
                  Role-Based Access Control
                </span>
                <p className="text-surface-600 dark:text-surface-400">
                  Enforces ADMIN &gt; ENGINEER &gt; VIEWER hierarchy at both FastAPI route dependency and database levels.
                </p>
              </div>

              <div className="p-3 rounded-lg bg-surface-50 dark:bg-surface-800/40 border border-surface-200 dark:border-surface-800 space-y-1">
                <span className="font-semibold text-surface-900 dark:text-white flex items-center gap-1.5">
                  <UserCheck className="w-3.5 h-3.5 text-purple-500" />
                  Human-in-the-Loop Oversight
                </span>
                <p className="text-surface-600 dark:text-surface-400">
                  AI remediation runbooks require explicit on-call engineer review and approval prior to resolution.
                </p>
              </div>
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Team Members Management */}
      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <Users className="w-4 h-4 text-brand-500" />
                <h3 className="text-base font-semibold text-surface-900 dark:text-white">
                  Team Members & Roles
                </h3>
              </div>
              <p className="text-xs text-surface-500 dark:text-surface-400">
                Manage organization access, assign roles, and grant incident investigation permissions.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={fetchMembers} loading={loadingMembers}>
                <RefreshCw className="w-3.5 h-3.5" />
              </Button>

              <Button
                variant="primary"
                size="sm"
                onClick={() => setAddModalOpen(true)}
                disabled={!isAdmin}
                title={!isAdmin ? 'Requires Admin role' : undefined}
              >
                <Plus className="w-4 h-4 mr-1.5" />
                Add Member
              </Button>
            </div>
          </div>
        </CardHeader>

        <CardBody className="p-0">
          {loadingMembers ? (
            <div className="py-12 flex justify-center">
              <LoadingSpinner size="md" />
            </div>
          ) : members.length === 0 ? (
            <div className="py-8 text-center text-xs text-surface-500">
              No members found for this organization.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-surface-50 dark:bg-surface-800/50 text-surface-500 dark:text-surface-400 border-b border-surface-200 dark:border-surface-800 uppercase tracking-wider font-semibold">
                  <tr>
                    <th className="px-6 py-3.5">User</th>
                    <th className="px-6 py-3.5">Email</th>
                    <th className="px-6 py-3.5">Current Role</th>
                    <th className="px-6 py-3.5">Joined At</th>
                    <th className="px-6 py-3.5 text-right">Role Management</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-200 dark:divide-surface-800">
                  {members.map((m) => (
                    <tr
                      key={m.user_id}
                      className="hover:bg-surface-50/50 dark:hover:bg-surface-800/30 transition-colors"
                    >
                      <td className="px-6 py-4 font-semibold text-surface-900 dark:text-white">
                        {m.full_name || m.email.split('@')[0]}
                      </td>
                      <td className="px-6 py-4 font-mono text-surface-600 dark:text-surface-300">
                        {m.email}
                      </td>
                      <td className="px-6 py-4">
                        <RoleBadge role={m.role} />
                      </td>
                      <td className="px-6 py-4 text-surface-500 dark:text-surface-400">
                        {new Date(m.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 text-right">
                        {isAdmin ? (
                          <select
                            value={m.role}
                            onChange={(e) => handleRoleChange(m.user_id, e.target.value as UserRole)}
                            className="bg-surface-50 dark:bg-surface-900 border border-surface-300 dark:border-surface-700 text-surface-900 dark:text-surface-100 text-xs rounded-lg px-2.5 py-1 focus:ring-1 focus:ring-brand-500"
                          >
                            <option value={UserRole.ADMIN}>ADMIN</option>
                            <option value={UserRole.ENGINEER}>ENGINEER</option>
                            <option value={UserRole.VIEWER}>VIEWER</option>
                          </select>
                        ) : (
                          <span className="text-surface-400 text-[11px] italic">Admin only</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardBody>
      </Card>

      {/* Add Member Modal */}
      <Modal isOpen={addModalOpen} onClose={() => setAddModalOpen(false)} title="Add Team Member">
        <div className="space-y-4 text-sm">
          {errorMsg && (
            <div className="p-3 rounded-lg bg-danger-500/10 border border-danger-500/20 text-danger-500 text-xs">
              {errorMsg}
            </div>
          )}

          <Input
            label="User Email Address *"
            type="email"
            placeholder="engineer@company.com"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
          />

          <Select
            label="Assigned Role *"
            value={newRole}
            onChange={(e) => setNewRole(e.target.value as UserRole)}
            options={[
              { value: UserRole.ADMIN, label: 'ADMIN — Full administrative control & membership management' },
              { value: UserRole.ENGINEER, label: 'ENGINEER — Run AI investigations, resolve incidents & add services' },
              { value: UserRole.VIEWER, label: 'VIEWER — Read-only telemetry access & audit log inspection' },
            ]}
          />

          <div className="flex justify-end gap-3 pt-3 border-t border-surface-200 dark:border-surface-800">
            <Button variant="ghost" onClick={() => setAddModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleAddMember} loading={submittingMember}>
              Add to Organization
            </Button>
          </div>
        </div>
      </Modal>

      {/* Create Org Modal */}
      <Modal isOpen={createOrgOpen} onClose={() => setCreateOrgOpen(false)} title="Create Organization">
        <div className="space-y-4 text-sm">
          <Input
            label="Organization Name *"
            placeholder="e.g. Acme Corp Infrastructure"
            value={newOrgName}
            onChange={(e) => setNewOrgName(e.target.value)}
          />

          <div className="flex justify-end gap-3 pt-3 border-t border-surface-200 dark:border-surface-800">
            <Button variant="ghost" onClick={() => setCreateOrgOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleCreateOrg} loading={creatingOrg}>
              Create Organization
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};
