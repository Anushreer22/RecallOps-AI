import { apiClient } from './client';
import { TokenResponse, User } from '../types';

export interface LoginParams {
  email: string;
  password: string;
}

export interface RegisterParams {
  email: string;
  password: string;
  full_name: string;
  organization_name?: string;
}

export const authApi = {
  login: async (credentials: LoginParams): Promise<TokenResponse> => {
    const res = await apiClient.post<TokenResponse>('/auth/login', credentials);
    return res.data;
  },

  register: async (payload: RegisterParams): Promise<TokenResponse> => {
    const res = await apiClient.post<TokenResponse>('/auth/register', payload);
    return res.data;
  },

  getMe: async (): Promise<User> => {
    const res = await apiClient.get<User>('/auth/me');
    return res.data;
  },
};
