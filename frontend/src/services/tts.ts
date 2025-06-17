import axios from 'axios';
import type { TTSRequest, HealthResponse } from '../types';

export const createTTSService = (baseUrl: string) => ({
  generateSpeech: async (request: TTSRequest): Promise<Blob> => {
    const formData = new FormData();
    formData.append('input', request.input);
    if (request.exaggeration) formData.append('exaggeration', request.exaggeration.toString());
    if (request.cfg_weight) formData.append('cfg_weight', request.cfg_weight.toString());
    if (request.temperature) formData.append('temperature', request.temperature.toString());
    if (request.voice_file) formData.append('voice_file', request.voice_file);

    const response = await axios.post(`${baseUrl}/audio/speech/upload`, formData, {
      responseType: 'blob',
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  },

  getHealth: async (): Promise<HealthResponse> => {
    const response = await axios.get(`${baseUrl}/health`);
    return response.data;
  },

  // New status endpoints
  getStatus: async (options?: {
    includeMemory?: boolean;
    includeHistory?: boolean;
    includeStats?: boolean;
    historyLimit?: number;
  }) => {
    const params = new URLSearchParams();
    if (options?.includeMemory) params.append('include_memory', 'true');
    if (options?.includeHistory) params.append('include_history', 'true');
    if (options?.includeStats) params.append('include_stats', 'true');
    if (options?.historyLimit) params.append('history_limit', options.historyLimit.toString());

    const response = await axios.get(`${baseUrl}/status?${params.toString()}`);
    return response.data;
  },

  getProgress: async () => {
    const response = await axios.get(`${baseUrl}/status/progress`);
    return response.data;
  },

  getStatistics: async (includeMemory = false) => {
    const params = includeMemory ? '?include_memory=true' : '';
    const response = await axios.get(`${baseUrl}/status/statistics${params}`);
    return response.data;
  },

  getHistory: async (limit = 10) => {
    const response = await axios.get(`${baseUrl}/status/history?limit=${limit}`);
    return response.data;
  },

  clearHistory: async (confirm = true) => {
    const response = await axios.post(`${baseUrl}/status/history/clear?confirm=${confirm}`);
    return response.data;
  },

  getApiInfo: async () => {
    const response = await axios.get(`${baseUrl}/info`);
    return response.data;
  }
});

export type TTSService = ReturnType<typeof createTTSService>; 