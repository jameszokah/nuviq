import React, { useState, useMemo } from 'react';
import { Volume2, Github, MessageCircle } from 'lucide-react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Button } from './components/ui/button';
import ThemeToggle from './components/theme-toggle';
import {
  ApiEndpointSelector,
  TextInput,
  AdvancedSettings,
  AudioPlayer
} from './components/tts';
import VoiceLibrary from './components/VoiceLibrary';
import AudioHistory from './components/AudioHistory';
import StatusHeader from './components/StatusHeader';
import StatusProgressOverlay from './components/StatusProgressOverlay';
import StatusStatisticsPanel from './components/StatusStatisticsPanel';
import { createTTSService } from './services/tts';
import { useApiEndpoint } from './hooks/useApiEndpoint';
import { useVoiceLibrary } from './hooks/useVoiceLibrary';
import { useAudioHistory } from './hooks/useAudioHistory';
import { useAdvancedSettings } from './hooks/useAdvancedSettings';
import { useTextInput } from './hooks/useTextInput';
import { useStatusMonitoring } from './hooks/useStatusMonitoring';
import { getFrontendVersion } from './lib/version';
import type { TTSRequest, HealthResponse } from './types';

function App() {
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showStatistics, setShowStatistics] = useState(false);

  // API endpoint management
  const { apiBaseUrl, updateApiBaseUrl } = useApiEndpoint();

  // Text input management with persistence
  const { text, updateText, clearText, hasText } = useTextInput();

  // Advanced settings management with persistence
  const {
    exaggeration,
    cfgWeight,
    temperature,
    updateExaggeration,
    updateCfgWeight,
    updateTemperature,
    resetToDefaults,
    isDefault
  } = useAdvancedSettings();

  // Voice library management
  const {
    voices,
    selectedVoice,
    setSelectedVoice,
    addVoice,
    deleteVoice,
    renameVoice,
    isLoading: voicesLoading
  } = useVoiceLibrary();

  // Audio history management
  const {
    audioHistory,
    addAudioRecord,
    deleteAudioRecord,
    renameAudioRecord,
    clearHistory,
    isLoading: historyLoading
  } = useAudioHistory();

  // Create TTS service with current API base URL
  const ttsService = useMemo(() => createTTSService(apiBaseUrl), [apiBaseUrl]);

  // Status monitoring with real-time updates
  const {
    progress,
    statistics,
    isProcessing,
    hasError: statusHasError,
    isLoadingStats
  } = useStatusMonitoring(apiBaseUrl);

  const { data: health, isLoading: isLoadingHealth } = useQuery({
    queryKey: ['health', apiBaseUrl],
    queryFn: ttsService.getHealth,
    refetchInterval: 30000
  });

  // Fetch API info (including version) periodically
  const { data: apiInfo } = useQuery({
    queryKey: ['apiInfo', apiBaseUrl],
    queryFn: async () => {
      const response = await fetch(`${apiBaseUrl}/info`);
      if (!response.ok) throw new Error('Failed to fetch API info');
      return response.json();
    },
    refetchInterval: 60000, // Refresh every minute
    retry: false
  });

  const generateMutation = useMutation({
    mutationFn: ttsService.generateSpeech,
    onSuccess: async (audioBlob) => {
      // Clean up previous audio URL
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }

      // Create new audio URL
      const url = URL.createObjectURL(audioBlob);
      setAudioUrl(url);

      // Save to audio history
      try {
        await addAudioRecord(
          audioBlob,
          {
            text,
            exaggeration,
            cfgWeight,
            temperature,
            voiceId: selectedVoice?.id,
            voiceName: selectedVoice?.name
          }
        );
      } catch (error) {
        console.error('Failed to save audio record:', error);
      }
    },
    onError: (error) => {
      console.error('TTS generation failed:', error);
      alert('Failed to generate speech. Please try again.');
    }
  });

  const handleGenerate = () => {
    if (!text.trim()) {
      alert('Please enter some text to convert to speech.');
      return;
    }

    generateMutation.mutate({
      input: text,
      exaggeration,
      cfg_weight: cfgWeight,
      temperature,
      voice_file: selectedVoice?.file || undefined
    });
  };



  return (
    <>
      <div className="min-h-screen flex flex-col">
        <div className="flex-1">
          <div className="container mx-auto px-4 py-8 flex flex-col items-center justify-center gap-4">
            {/* Header with Theme Toggle */}
            <div className="flex justify-between items-start w-full max-w-4xl mx-auto relative">
              <div className="flex-1">
                <StatusHeader
                  health={health}
                  progress={progress}
                  statistics={statistics}
                  isLoadingHealth={isLoadingHealth}
                  hasErrors={statusHasError}
                  apiVersion={apiInfo?.version || apiInfo?.api_version}
                />
              </div>
              <div className="absolute right-0 sm:right-4 top-0 flex items-center gap-2">
                <ThemeToggle />
              </div>
            </div>

            <div className="w-full max-w-2xl mx-auto flex flex-col items-center justify-center gap-4">

              <div className="flex flex-col items-center justify-center gap-2 w-full">
                <button
                  onClick={() => setShowStatistics(!showStatistics)}
                  className="px-3 py-1 text-xs bg-primary/10 hover:bg-primary/20 text-primary rounded-full transition-colors duration-300"
                >
                  {showStatistics ? 'Hide Stats' : 'Show Stats'}
                </button>
                {/* Statistics Panel (collapsible) */}
                {showStatistics && (
                  <StatusStatisticsPanel
                    statistics={statistics}
                    isLoading={isLoadingStats}
                    hasError={statusHasError}
                  />
                )}
              </div>

              <div className="max-w-2xl mx-auto gap-4 flex flex-col w-full">
                {/* API Endpoint Selector */}
                <div className="">
                  <ApiEndpointSelector
                    apiBaseUrl={apiBaseUrl}
                    onUrlChange={updateApiBaseUrl}
                  />
                </div>

                {/* Text Input */}
                <TextInput
                  value={text}
                  onChange={updateText}
                  onClear={clearText}
                  hasText={hasText}
                />

                {/* Voice Library */}
                <VoiceLibrary
                  voices={voices}
                  selectedVoice={selectedVoice}
                  onVoiceSelect={setSelectedVoice}
                  onAddVoice={addVoice}
                  onDeleteVoice={deleteVoice}
                  onRenameVoice={renameVoice}
                  isLoading={voicesLoading}
                />

                {/* Advanced Settings */}
                <AdvancedSettings
                  showAdvanced={showAdvanced}
                  onToggle={() => setShowAdvanced(!showAdvanced)}
                  exaggeration={exaggeration}
                  onExaggerationChange={updateExaggeration}
                  cfgWeight={cfgWeight}
                  onCfgWeightChange={updateCfgWeight}
                  temperature={temperature}
                  onTemperatureChange={updateTemperature}
                  onResetToDefaults={resetToDefaults}
                  isDefault={isDefault}
                />

                {/* Current Voice Indicator */}
                {selectedVoice && (
                  <div className="p-3 bg-primary/10 border border-primary/20 rounded-lg">
                    <div className="flex items-center gap-2 text-sm text-primary">
                      <Volume2 className="w-4 h-4" />
                      <span>Using voice: <strong>{selectedVoice.name}</strong></span>
                    </div>
                  </div>
                )}

                {/* Generate Button */}
                <div className="">
                  <Button
                    onClick={handleGenerate}
                    disabled={generateMutation.isPending || !text.trim()}
                    className="w-full py-6 px-6 text-xl [&_svg]:size-6 [&_svg:not([class*='size-'])]:size-6 flex gap-4"
                  // size="lg"
                  >
                    {generateMutation.isPending ? (
                      <>
                        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-current" />
                        Generating Speech...
                      </>
                    ) : (
                      <>
                        <Volume2 className="w-6 h-6" />
                        Generate Speech
                      </>
                    )}
                  </Button>
                </div>

                {/* Audio Player */}
                <AudioPlayer
                  audioUrl={audioUrl}
                />

                {/* Audio History */}
                <AudioHistory
                  audioHistory={audioHistory}
                  onDeleteAudioRecord={deleteAudioRecord}
                  onRenameAudioRecord={renameAudioRecord}
                  onClearHistory={clearHistory}
                  onRestoreSettings={(settings) => {
                    updateExaggeration(settings.exaggeration);
                    updateCfgWeight(settings.cfgWeight);
                    updateTemperature(settings.temperature);
                  }}
                  onRestoreText={updateText}
                  isLoading={historyLoading}
                />
              </div>
            </div>
          </div>

          {/* Footer */}
          <footer className="border-t border-border bg-card/50">
            <div className="w-full max-w-4xl mx-auto px-4 py-6">
              <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
                <div className="text-sm text-muted-foreground">
                  © 2025 Chatterbox TTS API - Open Source Voice Cloning
                  <br />
                  <span className="text-xs">Frontend v{getFrontendVersion()}</span>
                </div>
                <div className="flex items-center gap-4">
                  <a
                    href="https://github.com/travisvn/chatterbox-tts-api"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors duration-300"
                  >
                    <Github className="w-4 h-4" />
                    <span>GitHub</span>
                  </a>
                  <a
                    href="https://chatterboxtts.com/discord"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors duration-300"
                  >
                    <MessageCircle className="w-4 h-4" />
                    <span>Join Discord</span>
                  </a>
                </div>
              </div>
            </div>
          </footer>
        </div>

        {/* Progress Overlay */}
        <StatusProgressOverlay
          progress={progress}
          isVisible={generateMutation.isPending || isProcessing}
        />
      </div>
    </>
  );
}

export default App; 