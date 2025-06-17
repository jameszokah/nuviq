import { useState, useEffect, useCallback } from 'react';
import type { VoiceSample } from '../types';

const STORAGE_KEY = 'chatterbox-voice-library';
const DB_NAME = 'chatterbox-voices';
const DB_VERSION = 1;
const STORE_NAME = 'voice-files';

// IndexedDB utilities for storing audio files
const openDB = (): Promise<IDBDatabase> => {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => {
      console.error('Failed to open IndexedDB:', request.error);
      reject(request.error);
    };

    request.onsuccess = () => resolve(request.result);

    request.onupgradeneeded = () => {
      const db = request.result;
      try {
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, { keyPath: 'id' });
        }
      } catch (error) {
        console.error('Failed to create object store:', error);
        reject(error);
      }
    };

    request.onblocked = () => {
      console.warn('IndexedDB connection blocked');
      reject(new Error('Database connection blocked'));
    };
  });
};

const storeVoiceFile = async (id: string, file: File): Promise<void> => {
  // Convert file to array buffer first, outside of the transaction
  const arrayBuffer = await file.arrayBuffer();

  const db = await openDB();
  const transaction = db.transaction([STORE_NAME], 'readwrite');
  const store = transaction.objectStore(STORE_NAME);

  await new Promise<void>((resolve, reject) => {
    const request = store.put({
      id,
      data: arrayBuffer,
      type: file.type,
      name: file.name,
      size: file.size
    });
    request.onsuccess = () => resolve();
    request.onerror = () => reject(request.error);

    // Also handle transaction errors
    transaction.onerror = () => reject(transaction.error);
    transaction.onabort = () => reject(new Error('Transaction aborted'));
  });
};

const getVoiceFile = async (id: string): Promise<File | null> => {
  try {
    const db = await openDB();
    const transaction = db.transaction([STORE_NAME], 'readonly');
    const store = transaction.objectStore(STORE_NAME);

    return new Promise((resolve, reject) => {
      const request = store.get(id);
      request.onsuccess = () => {
        const result = request.result;
        if (result) {
          const file = new File([result.data], result.name, { type: result.type });
          resolve(file);
        } else {
          resolve(null);
        }
      };
      request.onerror = () => reject(request.error);
    });
  } catch (error) {
    console.error('Error retrieving voice file:', error);
    return null;
  }
};

const deleteVoiceFile = async (id: string): Promise<void> => {
  try {
    const db = await openDB();
    const transaction = db.transaction([STORE_NAME], 'readwrite');
    const store = transaction.objectStore(STORE_NAME);

    await new Promise<void>((resolve, reject) => {
      const request = store.delete(id);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });
  } catch (error) {
    console.error('Error deleting voice file:', error);
  }
};

interface StoredVoiceMetadata {
  id: string;
  name: string;
  uploadDate: string;
  fileSize: number;
  fileType: string;
}

export function useVoiceLibrary() {
  const [voices, setVoices] = useState<VoiceSample[]>([]);
  const [selectedVoice, setSelectedVoice] = useState<VoiceSample | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Load voices from storage on mount
  useEffect(() => {
    const loadVoices = async () => {
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) {
          const metadata: StoredVoiceMetadata[] = JSON.parse(stored);

          const loadedVoices: VoiceSample[] = [];
          for (const meta of metadata) {
            const file = await getVoiceFile(meta.id);
            if (file) {
              const audioUrl = URL.createObjectURL(file);
              loadedVoices.push({
                id: meta.id,
                name: meta.name,
                file,
                audioUrl,
                uploadDate: new Date(meta.uploadDate)
              });
            }
          }

          setVoices(loadedVoices);
        }
      } catch (error) {
        console.error('Error loading voice library:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadVoices();

    // Cleanup URLs on unmount
    return () => {
      voices.forEach(voice => URL.revokeObjectURL(voice.audioUrl));
    };
  }, []);

  // Save metadata to localStorage whenever voices change
  useEffect(() => {
    if (!isLoading) {
      const metadata: StoredVoiceMetadata[] = voices.map(voice => ({
        id: voice.id,
        name: voice.name,
        uploadDate: voice.uploadDate.toISOString(),
        fileSize: voice.file.size,
        fileType: voice.file.type
      }));
      localStorage.setItem(STORAGE_KEY, JSON.stringify(metadata));
    }
  }, [voices, isLoading]);

  const addVoice = useCallback(async (file: File, customName?: string) => {
    const id = Date.now().toString() + Math.random().toString(36).substr(2, 9);
    const name = customName || file.name.replace(/\.[^/.]+$/, "");

    try {
      // Store file in IndexedDB
      await storeVoiceFile(id, file);

      // Create URL for immediate use
      const audioUrl = URL.createObjectURL(file);

      const voice: VoiceSample = {
        id,
        name,
        file,
        audioUrl,
        uploadDate: new Date()
      };

      setVoices(prev => [...prev, voice]);
      return voice;
    } catch (error) {
      console.error('Error adding voice:', error);
      throw error;
    }
  }, []);

  const deleteVoice = useCallback(async (voiceId: string) => {
    const voice = voices.find(v => v.id === voiceId);
    if (voice) {
      // Revoke URL
      URL.revokeObjectURL(voice.audioUrl);

      // Remove from IndexedDB
      await deleteVoiceFile(voiceId);

      // Clear selection if this voice was selected
      if (selectedVoice?.id === voiceId) {
        setSelectedVoice(null);
      }

      // Remove from state
      setVoices(prev => prev.filter(v => v.id !== voiceId));
    }
  }, [voices, selectedVoice]);

  const renameVoice = useCallback((voiceId: string, newName: string) => {
    setVoices(prev => prev.map(voice =>
      voice.id === voiceId ? { ...voice, name: newName } : voice
    ));
  }, []);

  return {
    voices,
    selectedVoice,
    setSelectedVoice,
    addVoice,
    deleteVoice,
    renameVoice,
    isLoading
  };
} 