import React from 'react';
import { AlertCircle, CheckCircle, Activity, Clock, Cpu } from 'lucide-react';
import type { HealthResponse, TTSProgress, TTSStatistics } from '../types';

interface StatusHeaderProps {
  health: HealthResponse | undefined;
  progress: TTSProgress | undefined;
  statistics: TTSStatistics | undefined;
  isLoadingHealth: boolean;
  hasErrors: boolean;
  apiVersion?: string;
}

export default function StatusHeader({
  health,
  progress,
  statistics,
  isLoadingHealth,
  hasErrors,
  apiVersion
}: StatusHeaderProps) {

  const getStatusInfo = () => {
    if (hasErrors) {
      return {
        color: 'text-destructive',
        icon: <AlertCircle className="w-4 h-4" />,
        status: 'Connection Error',
        subtitle: 'Unable to connect to API'
      };
    }

    if (isLoadingHealth || !health) {
      return {
        color: 'text-muted-foreground',
        icon: <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary" />,
        status: 'Loading...',
        subtitle: 'Connecting to API'
      };
    }

    if (progress?.is_processing) {
      return {
        color: 'text-green-600 dark:text-green-400',
        icon: <Activity className="w-4 h-4 animate-pulse" />,
        status: 'Processing',
        subtitle: progress.current_step || progress.status.replace('_', ' ')
      };
    }

    if (!health.model_loaded) {
      return {
        color: 'text-yellow-600 dark:text-yellow-400',
        icon: <AlertCircle className="w-4 h-4" />,
        status: 'Model Loading',
        subtitle: `${health.device} - initializing`
      };
    }

    return {
      color: 'text-green-600 dark:text-green-400',
      icon: <CheckCircle className="w-4 h-4" />,
      status: 'Ready',
      subtitle: `${health.device} - ${statistics?.total_requests || 0} requests`
    };
  };

  const statusInfo = getStatusInfo();

  const formatUptime = () => {
    if (!statistics) return null;

    if (statistics.total_requests > 0) {
      return (
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span>{statistics.total_requests} total</span>
          <span>•</span>
          <span>{statistics.success_rate.toFixed(1)}% success</span>
          {statistics.average_duration_seconds > 0 && (
            <>
              <span>•</span>
              <span>{statistics.average_duration_seconds.toFixed(1)}s avg</span>
            </>
          )}
        </div>
      );
    }

    return null;
  };

  return (
    <div className="text-center">
      <h1 className="text-4xl font-bold text-foreground mb-2">
        🎤 Chatterbox TTS
      </h1>
      <p className="text-muted-foreground mb-3">
        Convert text to speech with voice cloning
      </p>

      {/* Enhanced Status Display */}
      <div className="inline-flex flex-col items-center gap-1">
        <div className={`inline-flex items-center gap-2 text-sm ${statusInfo.color}`}>
          {statusInfo.icon}
          <span className="font-medium">{statusInfo.status}</span>
          <span>•</span>
          <span>{statusInfo.subtitle}</span>
          {apiVersion && (
            <>
              <span>•</span>
              <span className="text-muted-foreground">API v{apiVersion}</span>
            </>
          )}
        </div>

        {formatUptime()}

        {/* Current Progress (if processing) */}
        {progress?.is_processing && progress.progress_percentage !== undefined && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground mt-1">
            <Clock className="w-3 h-3" />
            <span>{progress.progress_percentage.toFixed(1)}% complete</span>
            {progress.current_chunk && progress.total_chunks && (
              <>
                <span>•</span>
                <span>{progress.current_chunk}/{progress.total_chunks} chunks</span>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
} 