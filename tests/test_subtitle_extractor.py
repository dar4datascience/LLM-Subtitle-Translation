#!/usr/bin/env python3
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.subtitle_extractor import SubtitleTrack, SubtitleExtractor


class TestSubtitleTrack(unittest.TestCase):
    
    def test_text_based_codecs(self):
        """Test text-based codec detection."""
        track = SubtitleTrack(0, 'subrip', 'eng')
        self.assertTrue(track.is_text_based)
        self.assertFalse(track.is_image_based)
        
        track = SubtitleTrack(1, 'ass', 'eng')
        self.assertTrue(track.is_text_based)
        
        track = SubtitleTrack(2, 'webvtt', 'eng')
        self.assertTrue(track.is_text_based)
    
    def test_image_based_codecs(self):
        """Test image-based codec detection."""
        track = SubtitleTrack(0, 'hdmv_pgs_subtitle', 'eng')
        self.assertTrue(track.is_image_based)
        self.assertFalse(track.is_text_based)
        
        track = SubtitleTrack(1, 'dvd_subtitle', 'eng')
        self.assertTrue(track.is_image_based)
        
        track = SubtitleTrack(2, 'vobsub', 'eng')
        self.assertTrue(track.is_image_based)
    
    def test_track_repr(self):
        """Test track string representation."""
        track = SubtitleTrack(5, 'subrip', 'eng')
        repr_str = repr(track)
        self.assertIn('Track 5', repr_str)
        self.assertIn('subrip', repr_str)
        self.assertIn('eng', repr_str)


class TestSubtitleExtractor(unittest.TestCase):
    
    def test_select_track_single(self):
        """Test automatic selection with single track."""
        tracks = [SubtitleTrack(0, 'subrip', 'eng')]
        selected = SubtitleExtractor.select_track(tracks)
        self.assertEqual(selected.index, 0)
    
    def test_select_track_auto(self):
        """Test auto-selection with specific index."""
        tracks = [
            SubtitleTrack(0, 'subrip', 'eng'),
            SubtitleTrack(2, 'ass', 'spa'),
            SubtitleTrack(5, 'webvtt', 'fra')
        ]
        selected = SubtitleExtractor.select_track(tracks, auto_select=2)
        self.assertEqual(selected.index, 2)
        self.assertEqual(selected.codec, 'ass')
    
    def test_select_track_empty(self):
        """Test selection with no tracks."""
        tracks = []
        selected = SubtitleExtractor.select_track(tracks)
        self.assertIsNone(selected)


if __name__ == '__main__':
    unittest.main()
