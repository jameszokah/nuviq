# Copyright 2024 Nuviq, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import annotations

import asyncio
import json
import os
import weakref
from dataclasses import dataclass, replace
from typing import Any, Optional

import aiohttp

from livekit.agents import (
    APIConnectionError,
    APIConnectOptions,
    APIError,
    APIStatusError,
    APITimeoutError,
    tokenize,
    tts,
    utils,
)
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, NOT_GIVEN, NotGivenOr
from livekit.agents.utils import is_given

from .log import logger
from .models import TTSEncoding, TTSModels

# By default, use mp3 format.
_DefaultEncoding: TTSEncoding = "mp3_44100_128"
DEFAULT_VOICE_ID = "alloy"
API_BASE_URL = "http://localhost:4123/v1"


def _sample_rate_from_format(output_format: TTSEncoding) -> int:
    # e.g: mp3_44100 -> 44100
    split = output_format.split("_")
    if len(split) > 1 and split[1].isdigit():
        return int(split[1])
    return 44100  # Default sample rate

@dataclass
class Voice:
    id: str
    name: str
    category: str

@dataclass
class _TTSOptions:
    voice_id: str
    model: TTSModels | str
    language: NotGivenOr[str]
    base_url: str
    encoding: TTSEncoding
    sample_rate: int
    word_tokenizer: tokenize.WordTokenizer
    exaggeration: NotGivenOr[float]
    cfg_weight: NotGivenOr[float]
    temperature: NotGivenOr[float]
    streaming_chunk_size: NotGivenOr[int]
    streaming_strategy: NotGivenOr[str]
    streaming_quality: NotGivenOr[str]


class TTS(tts.TTS):
    def __init__(
        self,
        *,
        voice_id: str = DEFAULT_VOICE_ID,
        model: TTSModels | str = "noviq_tts_1",
        encoding: NotGivenOr[TTSEncoding] = NOT_GIVEN,
        base_url: NotGivenOr[str] = NOT_GIVEN,
        word_tokenizer: NotGivenOr[tokenize.WordTokenizer] = NOT_GIVEN,
        http_session: aiohttp.ClientSession | None = None,
        language: NotGivenOr[str] = NOT_GIVEN,
        exaggeration: NotGivenOr[float] = NOT_GIVEN,
        cfg_weight: NotGivenOr[float] = NOT_GIVEN,
        temperature: NotGivenOr[float] = NOT_GIVEN,
        streaming_chunk_size: NotGivenOr[int] = NOT_GIVEN,
        streaming_strategy: NotGivenOr[str] = NOT_GIVEN,
        streaming_quality: NotGivenOr[str] = NOT_GIVEN,
    ) -> None:
        if not is_given(encoding):
            encoding = _DefaultEncoding

        super().__init__(
            capabilities=tts.TTSCapabilities(streaming=True),
            sample_rate=_sample_rate_from_format(encoding),
            num_channels=1,
        )

        if not is_given(word_tokenizer):
            word_tokenizer = tokenize.basic.WordTokenizer(ignore_punctuation=False)

        self._opts = _TTSOptions(
            voice_id=voice_id,
            model=model, # model is not used by nuviq api, but we keep it for compatibility
            base_url=base_url if is_given(base_url) else API_BASE_URL,
            encoding=encoding,
            sample_rate=self.sample_rate,
            word_tokenizer=word_tokenizer,
            language=language,
            exaggeration=exaggeration,
            cfg_weight=cfg_weight,
            temperature=temperature,
            streaming_chunk_size=streaming_chunk_size,
            streaming_strategy=streaming_strategy,
            streaming_quality=streaming_quality,
        )
        self._session = http_session
        self._streams = weakref.WeakSet[SynthesizeStream]()

    def _ensure_session(self) -> aiohttp.ClientSession:
        if not self._session:
            self._session = utils.http_context.http_session()
        return self._session

    async def list_voices(self) -> list[Voice]:
        async with self._ensure_session().get(
            f"{self._opts.base_url}/voices",
        ) as resp:
            data = await resp.json()
            voices: list[Voice] = []
            for voice_data in data.get("voices", []):
                voices.append(Voice(id=voice_data["voice_id"], name=voice_data["name"], category=voice_data.get("category", "custom")))
            return voices

    def update_options(
        self,
        *,
        voice_id: NotGivenOr[str] = NOT_GIVEN,
        language: NotGivenOr[str] = NOT_GIVEN,
        exaggeration: NotGivenOr[float] = NOT_GIVEN,
        cfg_weight: NotGivenOr[float] = NOT_GIVEN,
        temperature: NotGivenOr[float] = NOT_GIVEN,
        streaming_chunk_size: NotGivenOr[int] = NOT_GIVEN,
        streaming_strategy: NotGivenOr[str] = NOT_GIVEN,
        streaming_quality: NotGivenOr[str] = NOT_GIVEN,
    ) -> None:
        if is_given(voice_id):
            self._opts.voice_id = voice_id
        if is_given(language):
            self._opts.language = language
        if is_given(exaggeration):
            self._opts.exaggeration = exaggeration
        if is_given(cfg_weight):
            self._opts.cfg_weight = cfg_weight
        if is_given(temperature):
            self._opts.temperature = temperature
        if is_given(streaming_chunk_size):
            self._opts.streaming_chunk_size = streaming_chunk_size
        if is_given(streaming_strategy):
            self._opts.streaming_strategy = streaming_strategy
        if is_given(streaming_quality):
            self._opts.streaming_quality = streaming_quality

    def stream(self, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS) -> "SynthesizeStream":
        stream = SynthesizeStream(tts=self, conn_options=conn_options)
        self._streams.add(stream)
        return stream

    async def aclose(self) -> None:
        for stream in list(self._streams):
            await stream.aclose()
        self._streams.clear()


class SynthesizeStream(tts.SynthesizeStream):
    def __init__(self, *, tts: TTS, conn_options: APIConnectOptions):
        super().__init__(tts=tts, conn_options=conn_options)
        self._tts: TTS = tts
        self._opts = replace(tts._opts)
        self._segments_ch = utils.aio.Chan[tokenize.WordStream]()

    async def _run(self, output_emitter: tts.AudioEmitter) -> None:
        request_id = utils.shortuuid()
        output_emitter.initialize(
            request_id=request_id,
            sample_rate=self._opts.sample_rate,
            num_channels=1,
            stream=True,
            mime_type=f"audio/{self._opts.encoding.split('_')[0]}",
        )

        async def _tokenize_input() -> None:
            word_stream = None
            async for input in self._input_ch:
                if isinstance(input, str):
                    if word_stream is None:
                        word_stream = self._opts.word_tokenizer.stream()
                        self._segments_ch.send_nowait(word_stream)
                    word_stream.push_text(input)
                elif isinstance(input, self._FlushSentinel):
                    if word_stream is not None:
                        word_stream.end_input()
                    word_stream = None
            if word_stream is not None:
                word_stream.end_input()
            self._segments_ch.close()

        async def _process_segments() -> None:
            async for word_stream in self._segments_ch:
                await self._run_stream(word_stream, output_emitter)

        tasks = [
            asyncio.create_task(_tokenize_input()),
            asyncio.create_task(_process_segments()),
        ]
        try:
            await asyncio.gather(*tasks)
        except asyncio.TimeoutError:
            raise APITimeoutError() from None
        except aiohttp.ClientResponseError as e:
            raise APIStatusError(
                message=e.message, status_code=e.status, request_id=request_id, body=None
            ) from None
        except Exception as e:
            raise APIConnectionError() from e
        finally:
            await utils.aio.gracefully_cancel(*tasks)

    async def _run_stream(
        self, word_stream: tokenize.WordStream, output_emitter: tts.AudioEmitter
    ) -> None:
        segment_id = utils.shortuuid()
        output_emitter.start_segment(segment_id=segment_id)

        # Collect all text from the word_stream
        text_parts = [data.token async for data in word_stream]
        full_text = "".join(text_parts)

        if not full_text.strip():
            # Don't send empty text to the API
            output_emitter.end_input()
            return

        form = aiohttp.FormData()
        form.add_field("input", full_text)
        form.add_field("voice", self._opts.voice_id)
        
        # Add optional parameters
        if is_given(self._opts.exaggeration):
            form.add_field('exaggeration', str(self._opts.exaggeration))
        if is_given(self._opts.cfg_weight):
            form.add_field('cfg_weight', str(self._opts.cfg_weight))
        if is_given(self._opts.temperature):
            form.add_field('temperature', str(self._opts.temperature))
        if is_given(self._opts.streaming_chunk_size):
            form.add_field('streaming_chunk_size', str(self._opts.streaming_chunk_size))
        if is_given(self._opts.streaming_strategy):
            form.add_field('streaming_strategy', self._opts.streaming_strategy)
        if is_given(self._opts.streaming_quality):
            form.add_field('streaming_quality', self._opts.streaming_quality)

        response_format = self._opts.encoding.split('_')[0]
        form.add_field("response_format", response_format)

        try:
            async with self._tts._ensure_session().post(
                f"{self._opts.base_url}/audio/speech/stream/upload",
                data=form,
                timeout=aiohttp.ClientTimeout(total=300)
            ) as resp:
                resp.raise_for_status()

                self._mark_started()
                async for data, _ in resp.content.iter_chunks():
                    output_emitter.push(data)
                
                output_emitter.end_input()

        except asyncio.TimeoutError as e:
            raise APITimeoutError() from e
        except aiohttp.ClientResponseError as e:
            raise APIStatusError(
                message=e.message,
                status_code=e.status,
                request_id=None,
                body=await resp.text(),
            ) from e
        except Exception as e:
            raise APIConnectionError() from e

def _strip_nones(data: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in data.items() if is_given(v) and v is not None}

