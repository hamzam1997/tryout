"""Shared Vertex AI client."""

from google import genai

from config import settings

_client: genai.Client | None = None


def get_client() -> genai.Client:
    """Return the process-wide Vertex AI client, building it on first use."""
    global _client
    if _client is None:
        # Pass the project explicitly; ADC would otherwise infer one from the
        # local gcloud config.
        _client = genai.Client(
            vertexai=True,
            project=settings.require_project(),
            location=settings.google_cloud_location,
        )
    return _client
