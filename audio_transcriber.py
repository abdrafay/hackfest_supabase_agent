import requests
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_WHISPER_MODEL = "whisper-large-v3"

# ------------- AUDIO TRANSCRIBER AND SUMMARIZER -------------

def transcribe_audio_from_url(audio_url):
    try:
        # Download audio from URL
        audio_response = requests.get(audio_url)
        audio_response.raise_for_status()

        files = {
            'file': ('audio.mp3', audio_response.content, 'audio/mpeg')
        }

        headers = {
            'Authorization': f'Bearer {GROQ_API_KEY}',
        }

        data = {
            "model": GROQ_WHISPER_MODEL,
        }

        # Send transcription request
        whisper_url = "https://api.groq.com/openai/v1/audio/transcriptions"
        response = requests.post(whisper_url, headers=headers, data=data, files=files)
        result = response.json()

        transcription = result.get("text", None)
        if not transcription:
            return "No transcription found."

        # Now summarize the transcription
        summary = summarize_text(transcription)
        return summary

    except Exception as e:
        return f"Error during transcription: {str(e)}"

def summarize_text(transcription_text):
    try:
        summarize_url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "llama-3.3-70b-versatile",  # or another available LLM model from Groq
            "messages": [
                {"role": "system", "content": "You are a helpful assistant that summarizes text in english."},
                {"role": "user", "content": f"Please summarize this transcription and convert in english: {transcription_text}"}
            ],
            "temperature": 0.5
        }

        response = requests.post(summarize_url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()

        return result["choices"][0]["message"]["content"]

    except Exception as e:
        return f"Error during summarization: {str(e)}"