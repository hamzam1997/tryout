"""Transcript parsing for meeting ingestion.

Turns an uploaded .vtt/.srt file or pasted text into one normalised form:

    [00:12:28] Ana: Refunds are silently delayed.

Cue times are kept rather than stripped. They are what lets the idea
extractor fill Idea.timestamp, and they are the only record of when in a
meeting something was said.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

# "00:12:28.400 --> 00:12:34.900" (vtt) or "00:12:28,400 --> ..." (srt).
# MULTILINE so detect_format can search a whole file, not just a single line.
_CUE_RANGE = re.compile(
    r"^(?P<start>\d{1,2}:\d{2}(?::\d{2})?[.,]\d{1,3})\s*-->\s*"
    r"(?P<end>\d{1,2}:\d{2}(?::\d{2})?[.,]\d{1,3})",
    re.MULTILINE,
)
# WebVTT voice span: <v Ana>text</v>, optionally <v.loud Ana>
_VOICE_TAG = re.compile(r"<v(?:\.[^\s>]+)?\s+(?P<speaker>[^>]+)>", re.IGNORECASE)
_ANY_TAG = re.compile(r"</?[^>]+>")
# "Ana: text" or "Ana Whitfield: text", but not "12: text" or a bare URL
_SPEAKER_PREFIX = re.compile(r"^(?P<speaker>[A-Za-z][\w .'-]{0,40}):\s+(?P<text>.+)$")
_SRT_INDEX = re.compile(r"^\d+$")


class TranscriptFormat(str, Enum):
    VTT = "vtt"
    SRT = "srt"
    TEXT = "text"


class TranscriptError(ValueError):
    """Raised when a transcript cannot be parsed into any usable cue."""


@dataclass
class Cue:
    """One utterance. `start` is an offset into the meeting, not a clock time."""

    start: str
    speaker: str
    text: str

    def render(self) -> str:
        prefix = f"[{self.start}] " if self.start else ""
        who = f"{self.speaker}: " if self.speaker else ""
        return f"{prefix}{who}{self.text}"


@dataclass
class ParsedTranscript:
    cues: list[Cue] = field(default_factory=list)
    speakers: list[str] = field(default_factory=list)
    source_format: TranscriptFormat = TranscriptFormat.TEXT

    @property
    def text(self) -> str:
        return "\n".join(cue.render() for cue in self.cues)

    @property
    def duration(self) -> str:
        return self.cues[-1].start if self.cues else ""


def detect_format(raw: str, filename: str | None = None) -> TranscriptFormat:
    """Prefer the file's own signature; fall back to the extension."""
    head = raw.lstrip()
    if head.upper().startswith("WEBVTT"):
        return TranscriptFormat.VTT

    if _CUE_RANGE.search(raw):
        # Both formats use cue ranges; srt separates milliseconds with a comma.
        return TranscriptFormat.SRT if _is_srt(raw) else TranscriptFormat.VTT

    if filename:
        suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if suffix in ("vtt", "srt"):
            return TranscriptFormat(suffix)

    return TranscriptFormat.TEXT


def _is_srt(raw: str) -> bool:
    match = _CUE_RANGE.search(raw)
    return bool(match) and "," in match.group("start")


def normalise_timestamp(value: str) -> str:
    """Reduce a cue time to HH:MM:SS, matching the form Idea.timestamp uses."""
    clock = re.split(r"[.,]", value.strip())[0]
    parts = clock.split(":")
    if len(parts) == 2:
        parts = ["00", *parts]
    return ":".join(part.zfill(2) for part in parts)


def _split_speaker(line: str) -> tuple[str, str]:
    """Pull a speaker name off a cue line, from a voice tag or a 'Name:' prefix."""
    voice = _VOICE_TAG.search(line)
    if voice:
        speaker = voice.group("speaker").strip()
        return speaker, _ANY_TAG.sub("", line).strip()

    clean = _ANY_TAG.sub("", line).strip()
    prefix = _SPEAKER_PREFIX.match(clean)
    if prefix:
        return prefix.group("speaker").strip(), prefix.group("text").strip()
    return "", clean


def _parse_cued(raw: str) -> list[Cue]:
    """Parse the block structure shared by vtt and srt."""
    cues: list[Cue] = []
    start = ""
    body: list[str] = []

    def flush() -> None:
        if not body:
            return
        speaker = ""
        texts: list[str] = []
        for line in body:
            line_speaker, line_text = _split_speaker(line)
            speaker = speaker or line_speaker
            if line_text:
                texts.append(line_text)
        if texts:
            cues.append(Cue(start=start, speaker=speaker, text=" ".join(texts)))

    for line in raw.splitlines():
        stripped = line.strip()
        match = _CUE_RANGE.match(stripped)
        if match:
            flush()
            start = normalise_timestamp(match.group("start"))
            body = []
            continue
        if not stripped:
            flush()
            body = []
            continue
        if stripped.upper().startswith("WEBVTT") or stripped.startswith("NOTE"):
            continue
        if _SRT_INDEX.match(stripped) and not body:
            continue
        body.append(stripped)

    flush()
    return cues


def _parse_plain(raw: str) -> list[Cue]:
    """Pasted text: no cue times, speakers only where a 'Name:' prefix exists."""
    cues: list[Cue] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        speaker, text = _split_speaker(stripped)
        if text:
            cues.append(Cue(start="", speaker=speaker, text=text))
    return cues


def _merge_consecutive(cues: list[Cue]) -> list[Cue]:
    """Join runs of cues from one speaker.

    Captions split a sentence across cues every few seconds. Merging keeps
    each speaking turn intact for the model and holds the turn's first
    timestamp, which is the one worth citing.
    """
    merged: list[Cue] = []
    for cue in cues:
        previous = merged[-1] if merged else None
        if previous and previous.speaker == cue.speaker and cue.speaker:
            previous.text = f"{previous.text} {cue.text}".strip()
            continue
        merged.append(Cue(start=cue.start, speaker=cue.speaker, text=cue.text))
    return merged


def parse_transcript(raw: str, filename: str | None = None) -> ParsedTranscript:
    """Parse an uploaded or pasted transcript into normalised cues."""
    if not raw or not raw.strip():
        raise TranscriptError("transcript is empty")

    source_format = detect_format(raw, filename)
    cues = (
        _parse_plain(raw)
        if source_format is TranscriptFormat.TEXT
        else _parse_cued(raw)
    )
    cues = _merge_consecutive(cues)

    if not cues:
        raise TranscriptError(f"no readable lines in {source_format.value} transcript")

    seen: dict[str, None] = {}
    for cue in cues:
        if cue.speaker:
            seen.setdefault(cue.speaker, None)

    return ParsedTranscript(
        cues=cues, speakers=list(seen), source_format=source_format
    )
