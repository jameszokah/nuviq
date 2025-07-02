# Cloudflare R2 Storage Integration

This guide explains how to use Cloudflare R2 for storing voice files in the Chatterbox API.

## Overview

Cloudflare R2 is an S3-compatible object storage service that provides a cost-effective way to store and retrieve voice files. The Chatterbox API can be configured to use R2 as the storage backend for voice files, which offers several advantages:

- Fast global access to voice files
- Cost-effective storage (no egress fees)
- Durable and reliable storage
- S3-compatible API

When using R2, voice files are cached in memory for 1 hour to improve performance and reduce storage costs.

## Setup

### 1. Create a Cloudflare R2 Account

If you don't already have one, sign up for a Cloudflare account and enable R2:

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. Navigate to R2 in the sidebar
3. Create a new bucket named `chatterbox-voices` (or choose your preferred name)

### 2. Create R2 Access Keys

1. In the R2 dashboard, go to "Manage R2 API Tokens"
2. Create a new API token with read and write permissions
3. Note down the Access Key ID and Secret Access Key

### 3. Configure Chatterbox API

Create or edit your `.env` file and add the following configurations:

```
# Cloudflare R2 Storage
R2_ACCOUNT_ID=your-account-id
R2_ACCESS_KEY_ID=your-access-key
R2_SECRET_ACCESS_KEY=your-secret-key
R2_BUCKET_NAME=chatterbox-voices
R2_REGION=auto
```

- `R2_ACCOUNT_ID`: Your Cloudflare account ID (found in the URL of your Cloudflare dashboard)
- `R2_ACCESS_KEY_ID`: The Access Key ID from step 2
- `R2_SECRET_ACCESS_KEY`: The Secret Access Key from step 2
- `R2_BUCKET_NAME`: The name of your R2 bucket
- `R2_REGION`: The region for your R2 bucket (auto, wnam, enam, weur, eeur, apac)

### 4. Restart the API

Restart the API to apply the R2 configuration:

```bash
docker-compose down
docker-compose up -d
```

Or if running directly:

```bash
python start.py
```

## How It Works

### Storage Process

1. When a voice is created or updated, the audio data is:
   - Stored in Cloudflare R2
   - Cached in memory for fast access
   - Metadata is stored locally

2. When a voice is requested:
   - If in cache, served directly from memory
   - If not in cache, fetched from R2 and added to cache
   - Cache entries expire after 1 hour of no access

### Fallback Mechanism

If R2 credentials are not configured, the API falls back to local file storage automatically.

## Voice ID Usage

With R2 integration, you can now use voice IDs in the text-to-speech API:

```
POST /audio/speech/upload
```

Parameters:
- `input`: The text to synthesize
- `voice`: Voice ID or voice name to use (from your voice library)
- `response_format`: Output format (wav, mp3, flac, ogg)
- `voice_file`: (Optional) Upload a voice file directly

You can use either:
- A voice ID (from your voice library)
- A voice name (case-insensitive)
- A direct file upload

The API will prioritize in this order:
1. Voice ID/name if provided
2. Uploaded file if provided
3. Default voice sample if nothing else is provided

## Output Format Support

The API now supports multiple output formats:

- `wav`: Standard uncompressed audio (default)
- `mp3`: Compressed audio with good quality
- `flac`: Lossless compressed audio
- `ogg`: Compressed audio with good quality

Specify the format using the `response_format` parameter. 