export type BrowserPcmRecording = {
  audioContext: AudioContext;
  chunks: Float32Array[];
  processor: ScriptProcessorNode;
  sampleRate: number;
  source: MediaStreamAudioSourceNode;
  startedAt: number;
  stream: MediaStream;
};

export type BrowserPcmRecordingResult = {
  file: File;
  durationMs: number;
  chunkCount: number;
};

type AudioWindow = Window &
  typeof globalThis & {
    webkitAudioContext?: typeof AudioContext;
  };

export function isBrowserPcmRecordingSupported() {
  if (typeof window === "undefined" || typeof navigator === "undefined") return false;
  return Boolean(getUserMediaFn() && getAudioContextCtor());
}

export async function startBrowserPcmRecording(): Promise<BrowserPcmRecording> {
  const AudioContextCtor = getAudioContextCtor();
  const getUserMedia = getUserMediaFn();
  if (!getUserMedia || !AudioContextCtor) {
    throw new Error("当前浏览器不支持录音");
  }

  const stream = await getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
    },
  });
  const audioContext = new AudioContextCtor();
  const source = audioContext.createMediaStreamSource(stream);
  const processor = audioContext.createScriptProcessor(4096, 1, 1);
  const chunks: Float32Array[] = [];

  processor.onaudioprocess = (event) => {
    chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
    event.outputBuffer.getChannelData(0).fill(0);
  };
  source.connect(processor);
  processor.connect(audioContext.destination);

  return {
    audioContext,
    chunks,
    processor,
    sampleRate: audioContext.sampleRate,
    source,
    startedAt: Date.now(),
    stream,
  };
}

export async function finishBrowserPcmWavRecording(
  recording: BrowserPcmRecording,
  filename = "sparkweave-voice.wav",
): Promise<BrowserPcmRecordingResult> {
  const durationMs = Date.now() - recording.startedAt;
  const chunkCount = recording.chunks.length;
  const wav = encodeWav(recording.chunks, recording.sampleRate, 16_000);
  stopBrowserPcmRecording(recording);
  return {
    file: new File([wav], filename, { type: "audio/wav" }),
    durationMs,
    chunkCount,
  };
}

export function stopBrowserPcmRecording(recording: BrowserPcmRecording | null) {
  if (!recording) return;
  recording.processor.disconnect();
  recording.source.disconnect();
  recording.stream.getTracks().forEach((track) => track.stop());
  void recording.audioContext.close().catch(() => undefined);
}

function getAudioContextCtor() {
  if (typeof window === "undefined") return null;
  const audioWindow = window as AudioWindow;
  return audioWindow.AudioContext || audioWindow.webkitAudioContext || null;
}

function getUserMediaFn() {
  if (typeof navigator === "undefined") return null;
  const mediaDevices = navigator.mediaDevices;
  if (!mediaDevices || typeof mediaDevices.getUserMedia !== "function") return null;
  return mediaDevices.getUserMedia.bind(mediaDevices);
}

function encodeWav(chunks: Float32Array[], sourceSampleRate: number, targetSampleRate: number) {
  const merged = mergeFloat32(chunks);
  const samples = downsampleFloat32(merged, sourceSampleRate, targetSampleRate);
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  writeAscii(view, 0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeAscii(view, 8, "WAVE");
  writeAscii(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, targetSampleRate, true);
  view.setUint32(28, targetSampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeAscii(view, 36, "data");
  view.setUint32(40, samples.length * 2, true);
  let offset = 44;
  for (const sample of samples) {
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
    offset += 2;
  }
  return new Blob([view], { type: "audio/wav" });
}

function mergeFloat32(chunks: Float32Array[]) {
  const length = chunks.reduce((total, chunk) => total + chunk.length, 0);
  const merged = new Float32Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }
  return merged;
}

function downsampleFloat32(input: Float32Array, sourceSampleRate: number, targetSampleRate: number) {
  if (sourceSampleRate === targetSampleRate) return input;
  const ratio = sourceSampleRate / targetSampleRate;
  const outputLength = Math.max(1, Math.floor(input.length / ratio));
  const output = new Float32Array(outputLength);
  for (let index = 0; index < outputLength; index += 1) {
    const start = Math.floor(index * ratio);
    const end = Math.min(Math.floor((index + 1) * ratio), input.length);
    let total = 0;
    for (let cursor = start; cursor < end; cursor += 1) total += input[cursor];
    output[index] = total / Math.max(1, end - start);
  }
  return output;
}

function writeAscii(view: DataView, offset: number, value: string) {
  for (let index = 0; index < value.length; index += 1) {
    view.setUint8(offset + index, value.charCodeAt(index));
  }
}
