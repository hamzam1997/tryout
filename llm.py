"""Shared Vertex AI client for the agent layers."""

from google import genai

from config import settings

_client: genai.Client | None = None


def build_client() -> genai.Client:
    """Construct a Vertex AI client.

    The project is always passed explicitly. Letting the SDK infer it would
    hand the call to whatever Application Default Credentials resolves from the
    local gcloud config, which is not necessarily this project.
    """
    return genai.Client(
        vertexai=True,
        project=settings.require_project(),
        location=settings.google_cloud_location,
    )


def get_client() -> genai.Client:
    """Return the process-wide client, building it on first use."""
    global _client
    if _client is None:
        _client = build_client()
    return _client
