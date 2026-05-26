#!/usr/bin/env python3
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.audio_manager import AudioTrack, AudioManager


class TestAudioTrack(unittest.TestCase):
    
    def test_audio_track_creation(self):
        """Test AudioTrack object creation."""
        track = AudioTrack(0, 'aac', 'eng', 2, 48000, 192000)
        self.assertEqual(track.index, 0)
        self.assertEqual(track.codec, 'aac')
        self.assertEqual(track.language, 'eng')
        self.assertEqual(track.channels, 2)
        self.assertEqual(track.sample_rate, 48000)
        self.assertEqual(track.bitrate, 192000)
    
    def test_audio_track_repr(self):
        """Test AudioTrack string representation."""
        track = AudioTrack(1, 'mp3', 'spa', 2, 44100, 128000)
        repr_str = repr(track)
        self.assertIn('Track 1', repr_str)
        self.assertIn('mp3', repr_str)
        self.assertIn('spa', repr_str)
        self.assertIn('128kbps', repr_str)
    
    def test_audio_track_no_bitrate(self):
        """Test AudioTrack with no bitrate."""
        track = AudioTrack(0, 'flac', 'eng', 2, 48000, None)
        repr_str = repr(track)
        self.assertIn('N/A', repr_str)


class TestAudioManager(unittest.TestCase):
    
    def test_select_audio_track_single(self):
        """Test automatic selection with single track."""
        tracks = [AudioTrack(0, 'aac', 'eng', 2, 48000, 192000)]
        selected = AudioManager.select_audio_track(tracks)
        self.assertEqual(selected.index, 0)
    
    def test_select_audio_track_auto(self):
        """Test auto-selection with specific index."""
        tracks = [
            AudioTrack(0, 'aac', 'eng', 2, 48000, 192000),
            AudioTrack(1, 'mp3', 'spa', 2, 44100, 128000),
            AudioTrack(2, 'flac', 'fra', 2, 48000, None)
        ]
        selected = AudioManager.select_audio_track(tracks, auto_select=1)
        self.assertEqual(selected.index, 1)
        self.assertEqual(selected.codec, 'mp3')
    
    def test_select_audio_track_empty(self):
        """Test selection with no tracks."""
        tracks = []
        selected = AudioManager.select_audio_track(tracks)
        self.assertIsNone(selected)


if __name__ == '__main__':
    unittest.main()
