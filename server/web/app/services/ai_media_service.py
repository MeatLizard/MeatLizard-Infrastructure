
import speech_recognition as sr
import moviepy
import os

from moviepy.editor import VideoFileClip
from server.web.app.models import MediaFile

class AIMediaService:
    def generate_captions(self, media_file: MediaFile) -> str:
        """
        Generates captions for a media file using speech-to-text.
        """
        if not media_file.mime_type.startswith("video"):
            return None

        video = VideoFileClip(media_file.storage_path)
        audio_path = f"{os.path.splitext(media_file.storage_path)[0]}.wav"
        video.audio.write_audiofile(audio_path)

        r = sr.Recognizer()
        with sr.AudioFile(audio_path) as source:
            audio = r.record(source)

        os.remove(audio_path)

        try:
            return r.recognize_google(audio)
        except sr.UnknownValueError:
            return "Could not understand audio"
        except sr.RequestError as e:
            return f"Could not request results from Google Speech Recognition service; {e}"

# Dependency for FastAPI
def get_ai_media_service() -> AIMediaService:
    return AIMediaService()
