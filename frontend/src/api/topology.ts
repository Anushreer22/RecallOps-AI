import { apiClient } from './client';
import { ServiceDependency, BlastRadiusSummary, TopologyCyclesResponse } from '../types';

export interface DependencyCreateParams {
  source_service: string;
  target_service: string;
  dependency_type?: 'DIRECT' | 'HARD' | 'SOFT' | 'ASYNC';
  tier?: string;
  owner?: string;
  project_id?: string;
}

export const topologyApi = {
  listDependencies: async (): Promise<ServiceDependency[]> => {
    const res = await apiClient.get<ServiceDependency[]>('/topology/dependencies');
    return res.data;
  },

  createDependency: async (data: DependencyCreateParams): Promise<ServiceDependency> => {
    const res = await apiClient.post<ServiceDependency>('/topology/dependencies', data);
    return res.data;
  },

  deleteDependency: async (id: number): Promise<{ status: string; id: number }> => {
    const res = await apiClient.delete<{ status: string; id: number }>(`/topology/dependencies/${id}`);
    return res.data;
  },

  getBlastRadius: async (service: string): Promise<BlastRadiusSummary> => {
    const res = await apiClient.get<BlastRadiusSummary>('/topology/blast-radius', {
      params: { service },
    });
    return res.data;
  },

  getCycles: async (): Promise<TopologyCyclesResponse> => {
    const res = await apiClient.get<TopologyCyclesResponse>('/topology/cycles');
    return res.data;
  },
};
