import { apiClient } from './client';
import { Organization, MemberDetail, UserRole } from '../types';

export const organizationsApi = {
  list: async (): Promise<Organization[]> => {
    const res = await apiClient.get<Organization[]>('/organizations');
    return res.data;
  },

  create: async (data: { name: string; slug?: string }): Promise<Organization> => {
    const res = await apiClient.post<Organization>('/organizations', data);
    return res.data;
  },

  getById: async (id: string): Promise<Organization> => {
    const res = await apiClient.get<Organization>(`/organizations/${id}`);
    return res.data;
  },

  listMembers: async (orgId: string): Promise<MemberDetail[]> => {
    const res = await apiClient.get<MemberDetail[]>(`/organizations/${orgId}/members`);
    return res.data;
  },

  addMember: async (orgId: string, data: { email: string; role: UserRole }): Promise<MemberDetail> => {
    const res = await apiClient.post<MemberDetail>(`/organizations/${orgId}/members`, data);
    return res.data;
  },

  updateMemberRole: async (
    orgId: string,
    userId: string,
    role: UserRole
  ): Promise<MemberDetail> => {
    const res = await apiClient.put<MemberDetail>(`/organizations/${orgId}/members/${userId}`, {
      role,
    });
    return res.data;
  },
};
