import { apiClient } from './client';
import { ServiceItem, ServiceDependency, BlastRadiusSummary, ServiceTier } from '../types';

export interface ServiceCreateParams {
  name: string;
  tier: ServiceTier;
  owner: string;
  project_id?: string;
  description?: string;
}

export const servicesApi = {
  list: async (): Promise<ServiceItem[]> => {
    const res = await apiClient.get<ServiceItem[]>('/services');
    return res.data;
  },

  create: async (data: ServiceCreateParams): Promise<ServiceItem> => {
    const res = await apiClient.post<ServiceItem>('/services', data);
    return res.data;
  },

  getById: async (id: string): Promise<ServiceItem> => {
    const res = await apiClient.get<ServiceItem>(`/services/${id}`);
    return res.data;
  },

  addDependency: async (
    serviceId: string,
    data: { target_service: string; dependency_type?: string; tier?: string; owner?: string }
  ): Promise<ServiceDependency> => {
    const res = await apiClient.post<ServiceDependency>(`/services/${serviceId}/dependencies`, data);
    return res.data;
  },

  getDependencies: async (serviceId: string): Promise<ServiceDependency[]> => {
    const res = await apiClient.get<ServiceDependency[]>(`/services/${serviceId}/dependencies`);
    return res.data;
  },

  getBlastRadius: async (serviceId: string): Promise<BlastRadiusSummary> => {
    const res = await apiClient.get<BlastRadiusSummary>(`/services/${serviceId}/blast-radius`);
    return res.data;
  },
};
