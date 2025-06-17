# Frontend Architecture

## Overview

The frontend has been reorganized into a modular, component-based architecture that improves maintainability and separation of concerns.

## Directory Structure

```
frontend/src/
├── components/
│   ├── tts/                    # TTS-specific components
│   │   ├── ApiEndpointSelector.tsx  # API endpoint configuration
│   │   ├── TextInput.tsx           # Text input with character counter
│   │   ├── VoiceUpload.tsx         # Voice file upload component
│   │   ├── AdvancedSettings.tsx    # Advanced TTS parameters
│   │   ├── AudioPlayer.tsx         # Audio playback and download
│   │   └── index.ts               # Component exports
│   ├── theme-provider.tsx      # Theme context provider
│   ├── theme-toggle.tsx        # Theme toggle button
│   └── VoiceLibrary.tsx       # Voice library management
├── hooks/
│   └── useApiEndpoint.ts      # API endpoint management hook
├── services/
│   └── tts.ts                 # TTS API service
├── types/
│   └── index.ts               # TypeScript type definitions
├── App.tsx                    # Main application component
├── main.tsx                   # Application entry point
└── styles.css                 # Global styles
```

## Key Features

### 🔧 Configurable API Endpoint

- Users can change the API endpoint directly in the browser
- Endpoint settings persist in localStorage
- Default endpoint: `http://192.168.0.4:4123/v1`
- Click the endpoint URL to edit it inline

### 🎨 Component Architecture

- **ApiEndpointSelector**: Inline editing of API base URL
- **TextInput**: Text input with character counter
- **VoiceUpload**: Drag-and-drop voice file upload
- **AdvancedSettings**: Collapsible advanced parameters
- **AudioPlayer**: Audio playback with download functionality

### 🪝 Custom Hooks

- **useApiEndpoint**: Manages API endpoint URL with localStorage persistence

### 🔧 Services

- **createTTSService**: Factory function that creates TTS API service with configurable base URL

### 📝 TypeScript Types

- Centralized type definitions for better type safety
- Shared interfaces across components

## Usage

### Changing API Endpoint

1. Look for the "API Endpoint" section at the top of the main interface
2. Click the pencil icon next to the current endpoint URL
3. Edit the URL (e.g., `http://localhost:4123/v1`)
4. Press Enter to save or Escape to cancel
5. The new endpoint is automatically saved and used for all API calls

### Component Development

```typescript
// Import components from the tts module
import { TextInput, VoiceUpload } from './components/tts';

// Use the API endpoint hook
import { useApiEndpoint } from './hooks/useApiEndpoint';

function MyComponent() {
  const { apiBaseUrl, updateApiBaseUrl } = useApiEndpoint();
  // ...
}
```

## Benefits

1. **Modularity**: Each component has a single responsibility
2. **Reusability**: Components can be easily reused or modified
3. **Type Safety**: Centralized TypeScript definitions
4. **Maintainability**: Clear separation of concerns
5. **Flexibility**: Configurable API endpoint for different environments
6. **Developer Experience**: Clean imports and organized code structure
