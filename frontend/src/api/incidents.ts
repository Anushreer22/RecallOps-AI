import { apiClient } from './client';
import {
  Incident,
  IncidentResolution,
  TriageQueueItem,
  BlastRadiusSummary,
  HistoricalRecallMatch,
  IncidentSeverity,
  ServiceTier,
} from '../types';

export interface IncidentCreateParams {
  title: string;
  description: string;
  service_name: string;
  severity: IncidentSeverity;
  service_tier?: ServiceTier;
  impacted_users?: number;
  raw_logs?: string;
  source?: string;
  project_id?: string;
}

export interface IncidentResolveParams {
  root_cause: string;
  action_taken: string;
  prevention_steps?: string;
  verified_by?: string;
}

export const incidentsApi = {
  list: async (status?: string, skip = 0, limit = 50): Promise<Incident[]> => {
    const params: Record<string, any> = { skip, limit };
    if (status && status !== 'ALL') params.status = status;
    const res = await apiClient.get<Incident[]>('/incidents', { params });
    return res.data;
  },

  getById: async (id: string): Promise<Incident> => {
    const res = await apiClient.get<Incident>(`/incidents/${id}`);
    return res.data;
  },

  create: async (data: IncidentCreateParams): Promise<Incident> => {
    const res = await apiClient.post<Incident>('/incidents', data);
    return res.data;
  },

  resolve: async (id: string, resolution: IncidentResolveParams): Promise<IncidentResolution> => {
    const res = await apiClient.post<IncidentResolution>(`/incidents/${id}/resolve`, resolution);
    return res.data;
  },

  diagnose: async (id: string): Promise<any> => {
    const res = await apiClient.post(`/incidents/${id}/diagnose`);
    return res.data;
  },

  getTriageQueue: async (): Promise<TriageQueueItem[]> => {
    const res = await apiClient.get<TriageQueueItem[]>('/incidents/triage/queue');
    return res.data;
  },

  getBlastRadius: async (service: string): Promise<BlastRadiusSummary> => {
    const res = await apiClient.get<BlastRadiusSummary>('/incidents/topology/blast-radius', {
      params: { service },
    });
    return res.data;
  },

  searchMemory: async (query: string, limit = 5): Promise<HistoricalRecallMatch[]> => {
    const res = await apiClient.get<HistoricalRecallMatch[]>('/incidents/memory/search', {
      params: { q: query, limit },
    });
    return res.data;
  },
};
