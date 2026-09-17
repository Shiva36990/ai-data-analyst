"""
Central place to construct chat model instances.
"""

from langchain_google_genai import ChatGoogleGenerativeAI
from src.config import settings


def get_llm(temperature: float = 0):
    return ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_api_key,
        temperature=temperature,
    )