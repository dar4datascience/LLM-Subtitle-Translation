# Unit Tests

Comprehensive test suite for LLM Subtitle Translation toolkit.

## Running Tests

### Activate Virtual Environment First

```bash
# Activate venv
source venv/bin/activate

# Run all tests
python tests/run_tests.py

# Run with verbose output
python tests/run_tests.py -v

# Run specific test file
python -m unittest tests/test_language_detector.py
python -m unittest tests/test_subtitle_extractor.py
python -m unittest tests/test_audio_manager.py
python -m unittest tests/test_translator.py
```

## Test Coverage

### `test_language_detector.py`
- ✅ ISO 639-1 to 639-2 conversion
- ✅ Extract text from SRT files
- ✅ Detect language from English text
- ✅ Detect language from Spanish text
- ✅ Handle short text (should fail detection)
- ✅ Tag subtitle files with language codes
- ✅ Replace existing language tags

### `test_subtitle_extractor.py`
- ✅ Text-based codec detection (SRT, ASS, WebVTT)
- ✅ Image-based codec detection (PGS, VobSub)
- ✅ Track string representation
- ✅ Single track auto-selection
- ✅ Multi-track selection with index
- ✅ Empty track list handling

### `test_audio_manager.py`
- ✅ AudioTrack object creation
- ✅ AudioTrack string representation
- ✅ AudioTrack with missing bitrate
- ✅ Single track auto-selection
- ✅ Multi-track selection with index
- ✅ Empty track list handling

### `test_translator.py`
- ✅ Translator initialization
- ✅ Custom language configuration
- ✅ SRT output path generation

## Test Results

Last run: 15 tests
- **Passed**: 13/15
- **Errors**: 2 (import errors when venv not activated)

### Known Issues

1. **Import Errors**: Tests require virtual environment activation
   - Solution: Always run `source venv/bin/activate` first
   
2. **Language Detection**: Requires langdetect/langid installed
   - Solution: `pip install langdetect langid`

## Adding New Tests

1. Create new test file: `tests/test_<module>.py`
2. Import unittest and module to test
3. Create test class inheriting from `unittest.TestCase`
4. Add test methods starting with `test_`
5. Run tests with `python tests/run_tests.py`

### Example Test

```python
import unittest
from src.my_module import MyClass

class TestMyClass(unittest.TestCase):
    
    def test_feature(self):
        """Test specific feature."""
        obj = MyClass()
        result = obj.method()
        self.assertEqual(result, expected_value)

if __name__ == '__main__':
    unittest.main()
```

## Integration Tests

For full integration testing:

```bash
# Test complete pipeline with sample video
python scripts/pipeline.py /path/to/test/video.mkv --dry-run

# Test audio extraction
python scripts/extract_audio.py /path/to/test/video.mkv -t 0

# Test subtitle extraction with language detection
python scripts/extract_subtitles.py /path/to/test/video.mkv
```

## CI/CD Integration

Add to GitHub Actions or similar:

```yaml
- name: Run tests
  run: |
    source venv/bin/activate
    pip install -r requirements.txt
    python tests/run_tests.py
```
