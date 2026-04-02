#!/bin/env python3

import os
import re
import numpy as np
import speech_recognition as sr
import requests
from faster_whisper import WhisperModel

from audio_stream import AudioStreamServer

CERT_PATH = os.environ.get('SSL_CERT_PATH')

if not CERT_PATH:
    print("Warning: SSL_CERT_PATH environment variable is not set. API request might fail if the certificate is self-signed.")

def handle_command(command_text):
    """
    Handler for commands detected after 'Hey assist'.
    You can fill in the logic here later.
    """
    command = command_text.strip().lower()
    print(f"\n[COMMAND DETECTED]: {command}\n")

    # Check for the "increment <number>" command
    if command.startswith("increment"):
        # Use regex to find the first number in the command string
        match = re.search(r'increment\s+(\d+)', command)
        if match:
            number = int(match.group(1))
            print(f"Executing API request to increment number: {number}")
            
            try:
                response = requests.post(
                    "https://10.0.0.1:9560/increment",
                    json={"number": number},
                    verify=CERT_PATH if CERT_PATH else True,
                    timeout=5
                )
                
                if response.status_code == 200:
                    print(f"API Success: {response.json()}")
                else:
                    print(f"API Error ({response.status_code}): {response.text}")
                    
            except requests.exceptions.RequestException as e:
                print(f"Failed to connect to the backend API: {e}")
        else:
            print("Could not find a number to increment. Please say 'increment <number>'.")


class AudioStream:
    def __init__(self):
        self.source = None
        self.

    def open_remote(self, server_host='10.0.0.1', server_port=9570):
        self.source = AudioStreamServer(server_host, server_port)
        self.source.accept()

    def open_local(self):
        self.source = sr.Microphone(sample_rate=16000)
        self.source.adjust_for_ambient_noise(self.source, duration=1)

    def close(self):
        self.source.close()

    def read(self):
        return self.source.receive_audio()


def main():
    # model_size = "large-v3"
    # model_size = "distil-large-v3"
    model_size = "small.en"

    device = 'cpu'
    compute_type = 'int8'

    print(f"Loading {model_size} model in {device} with {compute_type} compute type...")
    
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    print("Model loaded successfully!")

    r = sr.Recognizer()
    # Increase pause threshold so that short pauses while speaking a command don't end the recording early
    r.pause_threshold = 1.5

    # Use the default microphone
    source = sr.Microphone(sample_rate=16000)

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
            text = "".join([segment.text for segment in segments]).strip()
            if text:
                print(f"You: {text}")

                # Normalize text for marker detection
                lower_text = text.lower().replace(',', '').replace('.', '').replace('!', '').replace('?', '')

                start_idx = lower_text.find("hey assist")
                if start_idx != -1:
                    # Extract what comes after the start marker
                    command = lower_text[start_idx + len("hey assist"):].strip()
                    if command:
                        handle_command(command)
                    else:
                        print("\n[DETECTED 'Hey assist' BUT NO COMMAND FOLLOWED]\n")

        except KeyboardInterrupt:
            print("\nStopping transcription...")
            break
        except Exception as e:
            print(f"\nError: {e}")

if __name__ == "__main__":
    main()
