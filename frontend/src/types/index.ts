export interface TTSRequest {
  input: string;
  exaggeration?: number;
  cfg_weight?: number;
  temperature?: number;
  voice_file?: File;
}

export interface HealthResponse {
  status: string;
  model_loaded: boolean;
  device: string;
  config: any;
}

// New status API types
export interface TTSProgress {
  is_processing: boolean;
  status: string;
  current_step?: string;
  current_chunk?: number;
  total_chunks?: number;
  progress_percentage?: number;
  duration_seconds?: number;
  estimated_completion?: number;
  text_preview?: string;
  message?: string;
}

export interface TTSStatistics {
  total_requests: number;
  completed_requests: number;
  error_requests: number;
  success_rate: number;
  average_duration_seconds: number;
  average_text_length: number;
  is_processing: boolean;
  current_memory?: {
    cpu_memory_mb: number;
    gpu_memory_allocated_mb: number;
  };
}

export interface TTSRequestHistory {
  request_id: string;
  status: string;
  start_time: number;
  end_time?: number;
  duration_seconds: number;
  text_length: number;
  text_preview: string;
  voice_source: string;
  parameters: {
    exaggeration: number;
    cfg_weight: number;
    temperature: number;
  };
}

export interface TTSStatus {
  status: string;
  is_processing: boolean;
  request_id?: string;
  start_time?: number;
  duration_seconds?: number;
  text_length?: number;
  text_preview?: string;
  voice_source?: string;
  parameters?: {
    exaggeration: number;
    cfg_weight: number;
    temperature: number;
  };
  progress?: {
    current_chunk: number;
    total_chunks: number;
    current_step: string;
    progress_percentage: number;
    estimated_completion?: number;
  };
  total_requests: number;
  message?: string;
}

export interface APIInfo {
  api_name: string;
  version: string;
  status: string;
  tts_status: TTSStatus;
  statistics: TTSStatistics;
  memory_info?: {
    cpu_memory_mb: number;
    gpu_memory_allocated_mb: number;
  };
  recent_requests: TTSRequestHistory[];
  uptime_info: {
    total_requests: number;
    success_rate: number;
    is_processing: boolean;
  };
}

export interface VoiceSample {
  id: string;
  name: string;
  file: File;
  audioUrl: string;
  uploadDate: Date;
}

export interface AudioRecord {
  id: string;
  name: string;
  audioUrl: string;
  blob: Blob;
  createdAt: Date;
  settings: {
    text: string;
    exaggeration: number;
    cfgWeight: number;
    temperature: number;
    voiceId?: string;
    voiceName?: string;
  };
} 