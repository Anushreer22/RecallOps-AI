import { apiClient } from './client';
import { SystemHealth } from '../types';

export const healthApi = {
  check: async (): Promise<SystemHealth> => {
    const res = await apiClient.get<SystemHealth>('/health');
    return res.data;
  },
};
