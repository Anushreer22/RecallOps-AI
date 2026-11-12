import { apiClient } from './client';
import {
  InvestigationResponse,
  InvestigationFeedbackCreate,
  InvestigationFeedbackResponse,
} from '../types';

export const investigationsApi = {
  run: async (incidentId: string, provider?: string): Promise<InvestigationResponse> => {
    const params: Record<string, string> = {};
    if (provider) params.provider = provider;
    const res = await apiClient.post<InvestigationResponse>(
      `/incidents/${incidentId}/investigate`,
      null,
      { params }
    );
    return res.data;
  },

  listByIncident: async (incidentId: string, skip = 0, limit = 50): Promise<InvestigationResponse[]> => {
    const res = await apiClient.get<InvestigationResponse[]>(
      `/incidents/${incidentId}/investigations`,
      { params: { skip, limit } }
    );
    return res.data;
  },

  getById: async (id: string): Promise<InvestigationResponse> => {
    const res = await apiClient.get<InvestigationResponse>(`/investigations/${id}`);
    return res.data;
  },

  submitFeedback: async (
    id: string,
    feedback: InvestigationFeedbackCreate
  ): Promise<InvestigationFeedbackResponse> => {
    const res = await apiClient.post<InvestigationFeedbackResponse>(
      `/investigations/${id}/feedback`,
      feedback
    );
    return res.data;
  },
};
