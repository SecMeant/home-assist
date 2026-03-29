#!/bin/env python3

import os
import numpy as np
import speech_recognition as sr
from faster_whisper import WhisperModel

DEVICE = 'cpu'
COMPUTE_TYPE = 'int8'

def main():
    # You have an RTX 4080 Super, so you can easily use "large-v3" or "distil-large-v3"
    # We are using "small.en" for absolute lowest latency, but feel free to change it!
    model_size = "small.en"

    print(f"Loading {model_size} model in {DEVICE} with {COMPUTE_TYPE} compute type...")
    # float16 is highly optimized for RTX 40-series cards
    model = WhisperModel(model_size, device=DEVICE, compute_type=COMPUTE_TYPE)
    print("Model loaded successfully!")

    # Initialize the speech recognizer
    r = sr.Recognizer()

    # Use the default microphone
    with sr.Microphone(sample_rate=16000) as source:
        print("\nAdjusting for ambient noise... Please wait 1 second.")
        r.adjust_for_ambient_noise(source, duration=1)
        print("\nReady! Speak into your microphone. (Press Ctrl+C to stop)")

        while True:
            try:
                # Listen for speech. It will automatically stop recording when you pause.
                print('Listening...', end='', flush = True)
                audio = r.listen(source)
                print('DONE')

                # Convert the raw audio data to a numpy array (required by faster-whisper)
                audio_data = np.frombuffer(audio.get_raw_data(), np.int16).astype(np.float32) / 32768.0

                # Transcribe the audio
                # vad_filter=True prevents hallucinating text on silent/background noise
                segments, info = model.transcribe(audio_data, beam_size=5, vad_filter=True)

                # Print the transcribed text
                text = "".join([segment.text for segment in segments])
                if text.strip():
                    print(f"You: {text.strip()}")

            except KeyboardInterrupt:
                print("\nStopping transcription...")
                break
            except Exception as e:
                print(f"\nError: {e}")

if __name__ == "__main__":
    main()
