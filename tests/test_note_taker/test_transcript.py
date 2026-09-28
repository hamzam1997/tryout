"""Transcript parsing: format detection, speaker attribution, cue handling."""

import unittest

from agents.transcript import (
    TranscriptError,
    TranscriptFormat,
    normalise_timestamp,
    parse_transcript,
)

VTT = """WEBVTT

NOTE recorded automatically

00:00:04.100 --> 00:00:09.800
<v Marco Reyes>Alright, weekly ops.

00:00:10.200 --> 00:00:14.600
<v Dana Whitfield>Ticket volume was up twelve percent.

00:00:15.000 --> 00:00:19.400
<v Dana Whitfield>Mostly refund status questions.
"""

SRT = """1
00:00:04,100 --> 00:00:09,800
Marco Reyes: Alright, weekly ops.

2
00:00:10,200 --> 00:00:14,600
Dana Whitfield: Ticket volume was up twelve percent.
"""

PLAIN = """Marco Reyes: Alright, weekly ops.
Dana Whitfield: Ticket volume was up twelve percent.

Priya Raman: The delay is mostly the provider.
"""


class TestFormatDetection(unittest.TestCase):
    def test_vtt_detected_from_signature(self):
        self.assertIs(parse_transcript(VTT).source_format, TranscriptFormat.VTT)

    def test_srt_detected_from_comma_milliseconds(self):
        """The only structural difference from vtt is the decimal separator."""
        self.assertIs(parse_transcript(SRT).source_format, TranscriptFormat.SRT)

    def test_plain_text_detected_without_cues(self):
        self.assertIs(parse_transcript(PLAIN).source_format, TranscriptFormat.TEXT)

    def test_extension_used_when_content_is_ambiguous(self):
        parsed = parse_transcript("Ana: hello there", filename="notes.vtt")
        self.assertIs(parsed.source_format, TranscriptFormat.VTT)


class TestSpeakerAttribution(unittest.TestCase):
    def test_voice_tag_speakers(self):
        parsed = parse_transcript(VTT)
        self.assertEqual(parsed.speakers, ["Marco Reyes", "Dana Whitfield"])

    def test_colon_prefix_speakers(self):
        parsed = parse_transcript(SRT)
        self.assertEqual(parsed.speakers, ["Marco Reyes", "Dana Whitfield"])

    def test_speakers_are_deduplicated_in_first_seen_order(self):
        parsed = parse_transcript(PLAIN)
        self.assertEqual(
            parsed.speakers, ["Marco Reyes", "Dana Whitfield", "Priya Raman"]
        )

    def test_unattributed_lines_survive_without_a_speaker(self):
        parsed = parse_transcript("just some text with no speaker")
        self.assertEqual(parsed.speakers, [])
        self.assertEqual(parsed.cues[0].text, "just some text with no speaker")


class TestCueHandling(unittest.TestCase):
    def test_consecutive_same_speaker_cues_merge(self):
        """Captions split a sentence every few seconds; a turn should stay whole."""
        parsed = parse_transcript(VTT)
        self.assertEqual(len(parsed.cues), 2)
        self.assertEqual(
            parsed.cues[1].text,
            "Ticket volume was up twelve percent. Mostly refund status questions.",
        )

    def test_merged_cue_keeps_the_first_timestamp(self):
        parsed = parse_transcript(VTT)
        self.assertEqual(parsed.cues[1].start, "00:00:10")

    def test_cue_times_are_preserved_in_rendered_text(self):
        """These are what the idea extractor reads to fill Idea.timestamp."""
        parsed = parse_transcript(VTT)
        self.assertTrue(parsed.text.startswith("[00:00:04] Marco Reyes: Alright"))

    def test_plain_text_has_no_timestamps(self):
        parsed = parse_transcript(PLAIN)
        self.assertEqual(parsed.cues[0].start, "")
        self.assertTrue(parsed.text.startswith("Marco Reyes: Alright"))

    def test_duration_is_the_last_cue_start(self):
        self.assertEqual(parse_transcript(VTT).duration, "00:00:10")


class TestTimestampNormalisation(unittest.TestCase):
    def test_vtt_milliseconds_dropped(self):
        self.assertEqual(normalise_timestamp("00:12:28.400"), "00:12:28")

    def test_srt_comma_milliseconds_dropped(self):
        self.assertEqual(normalise_timestamp("00:12:28,400"), "00:12:28")

    def test_short_form_gains_an_hour_component(self):
        self.assertEqual(normalise_timestamp("12:28.400"), "00:12:28")

    def test_single_digit_parts_are_padded(self):
        self.assertEqual(normalise_timestamp("1:02:03.000"), "01:02:03")


class TestRejections(unittest.TestCase):
    def test_empty_transcript_rejected(self):
        with self.assertRaises(TranscriptError):
            parse_transcript("")

    def test_whitespace_only_transcript_rejected(self):
        with self.assertRaises(TranscriptError):
            parse_transcript("   \n\n  ")

    def test_cue_headers_with_no_dialogue_rejected(self):
        """A file of timings and nothing else is not a usable transcript."""
        with self.assertRaises(TranscriptError):
            parse_transcript("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\n\n")


if __name__ == "__main__":
    unittest.main()
