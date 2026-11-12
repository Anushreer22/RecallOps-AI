import { apiClient } from './client';
import { AuditLogItem } from '../types';

export const auditApi = {
  list: async (
    action?: string,
    resourceType?: string,
    limit = 50,
    offset = 0
  ): Promise<AuditLogItem[]> => {
    const params: Record<string, any> = { limit, offset };
    if (action && action !== 'ALL') params.action = action;
    if (resourceType && resourceType !== 'ALL') params.resource_type = resourceType;
    const res = await apiClient.get<AuditLogItem[]>('/audit-logs', { params });
    return res.data;
  },
};
