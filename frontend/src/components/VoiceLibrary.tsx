import React, { useState, useRef, useEffect } from 'react';
import { Trash2, Play, Pause, Upload, Edit2, Check, X } from 'lucide-react';
import { Input } from './ui/input';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import VoiceUploadModal from './VoiceUploadModal';
import type { VoiceSample } from '../types';

interface VoiceLibraryProps {
  voices: VoiceSample[];
  selectedVoice: VoiceSample | null;
  onVoiceSelect: (voice: VoiceSample | null) => void;
  onAddVoice: (file: File, customName?: string) => Promise<VoiceSample>;
  onDeleteVoice: (voiceId: string) => Promise<void>;
  onRenameVoice: (voiceId: string, newName: string) => void;
  isLoading: boolean;
}

export default function VoiceLibrary({
  voices,
  selectedVoice,
  onVoiceSelect,
  onAddVoice,
  onDeleteVoice,
  onRenameVoice,
  isLoading
}: VoiceLibraryProps) {

  const [playingVoice, setPlayingVoice] = useState<string | null>(null);
  const [editingVoice, setEditingVoice] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [showUploadModal, setShowUploadModal] = useState(false);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);

  // Cleanup audio when component unmounts
  useEffect(() => {
    return () => {
      if (currentAudioRef.current) {
        currentAudioRef.current.pause();
        currentAudioRef.current = null;
      }
    };
  }, []);

  const handleUploadVoice = async (file: File, customName?: string) => {
    try {
      await onAddVoice(file, customName);
    } catch (error) {
      throw error; // Re-throw to let the modal handle the error display
    }
  };

  const handleRename = (voiceId: string, currentName: string) => {
    setEditingVoice(voiceId);
    setEditName(currentName);
  };

  const handleSaveRename = () => {
    if (editingVoice && editName.trim()) {
      onRenameVoice(editingVoice, editName.trim());
      setEditingVoice(null);
      setEditName('');
    }
  };

  const handleCancelRename = () => {
    setEditingVoice(null);
    setEditName('');
  };

  const handleDeleteVoice = async (voiceId: string) => {
    if (confirm('Are you sure you want to delete this voice?')) {
      try {
        await onDeleteVoice(voiceId);
      } catch (error) {
        alert('Failed to delete voice. Please try again.');
      }
    }
  };

  const playPreview = (voice: VoiceSample) => {
    // If clicking the same voice that's currently playing/paused
    if (playingVoice === voice.id && currentAudioRef.current) {
      if (currentAudioRef.current.paused) {
        // Resume playback
        currentAudioRef.current.play().catch(error => {
          console.error('Error resuming voice:', error);
          alert('Failed to resume voice sample');
        });
      } else {
        // Pause playback (keep position)
        currentAudioRef.current.pause();
      }
      return;
    }

    // Stop any currently playing audio from a different voice
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current = null;
    }

    // Start playing the new audio
    const audio = new Audio(voice.audioUrl);
    currentAudioRef.current = audio;

    audio.onended = () => {
      setPlayingVoice(null);
      currentAudioRef.current = null;
    };

    audio.onerror = () => {
      setPlayingVoice(null);
      currentAudioRef.current = null;
      alert('Error playing voice sample');
    };

    audio.play().catch(error => {
      console.error('Error playing voice:', error);
      setPlayingVoice(null);
      currentAudioRef.current = null;
      alert('Failed to play voice sample');
    });

    setPlayingVoice(voice.id);
  };

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <CardTitle>Voice Library</CardTitle>
            <Button
              onClick={() => setShowUploadModal(true)}
              className="bg-primary hover:bg-primary/90 text-primary-foreground px-4 py-2 rounded-lg text-sm flex items-center gap-2 font-semibold duration-300"
            >
              <Upload className="w-4 h-4" />
              Add Voice
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center py-8 text-muted-foreground">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-2"></div>
              <p>Loading voices...</p>
            </div>
          ) : voices.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Upload className="mx-auto w-12 h-12 mb-2 opacity-50" />
              <p>No voices in library</p>
              <p className="text-sm">Upload voice samples to get started</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-60 overflow-y-auto">
              {voices.map(voice => (
                <div
                  key={voice.id}
                  className={`p-3 border rounded-lg cursor-pointer duration-300 ${selectedVoice?.id === voice.id
                    ? 'border-primary bg-primary/10'
                    : 'border-border hover:border-accent-foreground/50 hover:bg-accent/50'
                    }`}
                  onClick={() => onVoiceSelect(voice)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      {editingVoice === voice.id ? (
                        <div className="flex items-center gap-2">
                          <Input
                            type="text"
                            value={editName}
                            onChange={(e) => setEditName(e.target.value)}
                            className="flex-1 text-sm"
                            onClick={(e) => e.stopPropagation()}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') handleSaveRename();
                              if (e.key === 'Escape') handleCancelRename();
                            }}
                            autoFocus
                          />
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleSaveRename();
                            }}
                            className="p-1 hover:bg-green-100 dark:hover:bg-green-900/30 text-green-600 dark:text-green-400 rounded transition-colors duration-300"
                          >
                            <Check className="w-4 h-4" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCancelRename();
                            }}
                            className="p-1 hover:bg-destructive/10 text-destructive rounded transition-colors duration-300"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
                      ) : (
                        <>
                          <p className="font-medium text-foreground truncate">{voice.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {voice.uploadDate.toLocaleDateString()} • {(voice.file.size / 1024 / 1024).toFixed(1)}MB
                          </p>
                        </>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          playPreview(voice);
                        }}
                        className="p-1 hover:bg-accent rounded transition-colors duration-300"
                      >
                        {playingVoice === voice.id && currentAudioRef.current && !currentAudioRef.current.paused ? (
                          <Pause className="w-4 h-4 text-muted-foreground" />
                        ) : (
                          <Play className="w-4 h-4 text-muted-foreground" />
                        )}
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRename(voice.id, voice.name);
                        }}
                        className="p-1 hover:bg-accent rounded transition-colors duration-300"
                      >
                        <Edit2 className="w-4 h-4 text-muted-foreground" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteVoice(voice.id);
                        }}
                        className="p-1 hover:bg-destructive/10 text-destructive rounded transition-colors duration-300"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Voice Upload Modal */}
      <VoiceUploadModal
        open={showUploadModal}
        onOpenChange={setShowUploadModal}
        onUpload={handleUploadVoice}
      />
    </>
  );
} 