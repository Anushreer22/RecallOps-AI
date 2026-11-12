import { apiClient } from './client';
import { WebhookEventItem } from '../types';

export const webhooksApi = {
  listEvents: async (provider?: string, limit = 50): Promise<WebhookEventItem[]> => {
    const params: Record<string, any> = { limit };
    if (provider && provider !== 'ALL') params.provider = provider;
    const res = await apiClient.get<WebhookEventItem[]>('/webhooks/events', { params });
    return res.data;
  },
};
