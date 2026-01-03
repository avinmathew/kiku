/** API client for backend communication. */
import axios from 'axios';
import {
  ProcessRequest,
  ProcessResponse,
  StatusResponse,
  ResultResponse,
} from './types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const processUrl = async (request: ProcessRequest): Promise<ProcessResponse> => {
  const response = await api.post<ProcessResponse>('/api/process', request);
  return response.data;
};

export const processFile = async (file: File, sourceLanguage: string, targetLanguage: string): Promise<ProcessResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('source_language', sourceLanguage);
  formData.append('target_language', targetLanguage);
  
  // Axios automatically sets Content-Type with boundary for FormData, so don't override default headers
  // Use a new axios instance without default headers for this request
  const response = await axios.post<ProcessResponse>(
    `${API_BASE_URL}/api/process/upload`,
    formData
  );
  return response.data;
};

export const processRecording = async (file: File, sourceLanguage: string, targetLanguage: string): Promise<ProcessResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('source_language', sourceLanguage);
  formData.append('target_language', targetLanguage);
  
  // Use the record endpoint which skips cache
  const response = await axios.post<ProcessResponse>(
    `${API_BASE_URL}/api/process/record`,
    formData
  );
  return response.data;
};

export const getStatus = async (jobId: string): Promise<StatusResponse> => {
  const response = await api.get<StatusResponse>(`/api/status/${jobId}`);
  return response.data;
};

export const getResult = async (jobId: string): Promise<ResultResponse> => {
  const response = await api.get<ResultResponse>(`/api/result/${jobId}`);
  return response.data;
};

export const getAudioUrl = (jobId: string): string => {
  return `${API_BASE_URL}/api/audio/${jobId}`;
};

export interface CacheCheckResponse {
  exists: boolean;
  file_hash: string;
}

export const checkCache = async (fileHash: string, sourceLanguage: string, targetLanguage: string): Promise<CacheCheckResponse> => {
  const response = await api.get<CacheCheckResponse>(`/api/cache/check`, {
    params: { file_hash: fileHash, source_language: sourceLanguage, target_language: targetLanguage }
  });
  return response.data;
};

/**
 * Calculate SHA256 hash of a file using Web Crypto API.
 */
export const calculateFileHash = async (file: File): Promise<string> => {
  const arrayBuffer = await file.arrayBuffer();
  const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  return hashHex;
};

