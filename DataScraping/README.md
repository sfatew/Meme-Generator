# Meme Character Extraction Pipeline - Unified UI

A streamlined pipeline to scrape meme images from bovagau.vn, segment characters using **SAM3**, and immediately sort them - all from a single UI.

## 🎯 What's New

**Unified workflow**: Configure everything in one UI, then the pipeline runs automatically:

- Download memes → Segment characters → **Immediately sort** (no intermediate storage)
- Characters appear in the UI as they're extracted
- Only sorted characters are saved (Bo/Gau/Others/Discarded)
- Real-time progress tracking and statistics

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

**requirements.txt:**

```
selenium
webdriver-manager
pillow
torch
torchvision
transformers
accelerate
```

### 2. Login to Hugging Face

```bash
huggingface-cli login
```

Accept the SAM3 model license at: https://huggingface.co/facebook/sam3

### 3. Run the Pipeline

```bash
python unified_pipeline.py
```

The UI will open with:

- **Configuration panel**: Set start ID, count, delay, directories
- **Progress tracker**: Real-time pipeline status
- **Sorting interface**: Characters appear as they're extracted

## 🎮 How to Use

### 1. Configure the Pipeline

In the UI, set:

- **Start Meme ID**: Which meme to start from (e.g., 0)
- **Count**: How many memes to process (e.g., 5)
- **Delay**: Seconds between downloads (e.g., 2)
- **Download Dir**: Where to save downloaded memes
- **Output Dir**: Where to save sorted characters

### 2. Start the Pipeline

Click **▶ START PIPELINE** - the system will:

1. Download memes from bovagau.vn
2. Segment characters with SAM3
3. Show each character in the UI for sorting
4. Save only the sorted characters

### 3. Sort Characters

As characters appear, use keyboard shortcuts:

| Key               | Action           |
| ----------------- | ---------------- |
| **← Left Arrow**  | Sort to Bo       |
| **→ Right Arrow** | Sort to Gau      |
| **↑ Up Arrow**    | Sort to Others   |
| **↓ Down Arrow**  | Discard          |
| **⌫ Backspace**   | Undo last action |
| **ESC**           | Stop pipeline    |

### 4. Track Progress

The UI shows:

- Current meme being processed
- Number of characters found
- Real-time statistics (Bo: X, Gau: Y, etc.)
- Pipeline status (downloading, segmenting, etc.)

## 📁 Output Structure

```
project/
├── unified_pipeline.py       # Main unified application
├── scraper.py                # Meme scraper
├── character_segment.py      # SAM3 segmentation
├── meme_downloads/           # Downloaded memes
│   └── metadata.json
└── sorted_characters/        # Output (no intermediate crops!)
    ├── Bo/                   # Bo characters
    ├── Gau/                  # Gau characters
    ├── Others/               # Other characters
    ├── Discarded/           # Discarded images
    └── sorting_metadata.json # Tracking file
```

## 💡 Key Features

### No Intermediate Storage

- Characters are **not** saved after segmentation
- They appear directly in the UI for sorting
- Only sorted characters are saved to disk
- Saves disk space and simplifies workflow

### Real-Time Processing

- Download and segment in background
- Characters appear as soon as they're extracted
- Sort while the next meme is being processed
- Efficient pipeline that doesn't wait for you

### Resume & Undo

- **Resume**: Already-sorted characters are skipped
- **Undo**: Press Backspace to undo last action
- **Stop**: Press ESC to stop anytime (progress saved)

### Progress Tracking

- Shows which meme is being processed
- Real-time character count
- Live statistics for each category
- Completion summary with totals

## ⚙️ Configuration Tips

### For Testing

```
Start Meme ID: 0
Count: 3-5
Delay: 2
```

### For Production

```
Start Meme ID: 0
Count: 20-50
Delay: 2-3 (be respectful to server)
```

### For Continuing

```
Start Meme ID: 50 (last ID + 1)
Count: 50
Delay: 2
```

## 📊 Statistics & Metadata

### Real-Time Stats

Shown in the UI:

- Memes processed
- Memes downloaded/skipped
- Bo/Gau/Others/Discarded counts

### Metadata File (`sorting_metadata.json`)

```json
{
  "sorted_images": {
    "sorted_characters/Bo/meme_5_char_01.png": {
      "meme_id": 5,
      "char_idx": 1,
      "category": "Bo",
      "score": 0.856
    }
  },
  "session_stats": {
    "memes_processed": 10,
    "memes_downloaded": 8,
    "memes_skipped": 2,
    "Bo": 15,
    "Gau": 23,
    "Others": 8,
    "Discarded": 4
  }
}
```

## 🔧 Troubleshooting

### Hugging Face Authentication

```bash
huggingface-cli login
```

### GPU Memory Issues

Edit `unified_pipeline.py`:

```python
self.segmenter = CharacterSegmenter(
    output_dir="temp_crops",
    device="cpu"  # Force CPU
)
```

### Selenium Issues

Install Microsoft Edge browser:

```bash
# Ubuntu/Debian
sudo apt-get install microsoft-edge-stable

# macOS
brew install --cask microsoft-edge
```

### Tkinter Not Found (Linux)

```bash
sudo apt-get install python3-tk
```

## 💡 Usage Tips

### Efficient Sorting

- **Stay focused**: The pipeline feeds you characters
- **Use keyboard only**: Faster than mouse clicks
- **Undo mistakes**: Backspace is your friend
- **Take breaks**: Stop anytime, resume later

### Optimal Batch Sizes

- **First time**: Start with 3-5 memes to test
- **Regular use**: 10-20 memes per session
- **Bulk processing**: 50+ memes (but take breaks!)

### Speed Optimization

- **GPU**: 5-10x faster than CPU for segmentation
- **Delay**: Use 2-3 seconds to be respectful
- **Multitask**: Sort while next meme downloads

## 📈 Performance

### Pipeline Speed

| Task               | Time (GPU)        | Time (CPU)        |
| ------------------ | ----------------- | ----------------- |
| Download per meme  | ~2s               | ~2s               |
| Segment per meme   | ~5-10s            | ~30-60s           |
| Sort per character | 1-3s (your speed) | 1-3s (your speed) |

### Typical Session

- **5 memes** → ~25 characters → ~5-10 minutes total
- **10 memes** → ~50 characters → ~10-15 minutes total
- **20 memes** → ~100 characters → ~20-30 minutes total

## 🎯 Workflow Example

### Morning Session

```python
# Run unified_pipeline.py
# Configure: Start ID = 0, Count = 10, Delay = 2
# Click START PIPELINE
# Sort characters as they appear
# Total time: ~15 minutes
```

### Afternoon Session

```python
# Run unified_pipeline.py again
# Configure: Start ID = 10, Count = 10, Delay = 2
# Click START PIPELINE
# Continue sorting
# Total time: ~15 minutes
```

### Result

- 20 memes processed
- ~100 characters sorted
- Well-organized folders
- Full metadata tracking

## 🔐 Privacy & Security

- Hugging Face token stored in `~/.cache/huggingface/token`
- Don't commit tokens to version control
- Token only needs read access for models
- Revoke anytime at: https://huggingface.co/settings/tokens

## 📝 Comparison with Old Pipeline

### Old Workflow

```
1. Download memes (separate script)
2. Segment all characters → character_crops/
3. Open sorter UI
4. Sort all crops manually
```

### New Unified Workflow

```
1. Configure in UI
2. Click START
3. Sort characters as they're extracted
4. Done!
```

**Benefits**:

- ✅ Single UI for everything
- ✅ No intermediate crop storage
- ✅ Real-time progress
- ✅ More efficient workflow
- ✅ Less disk space used

## 🤝 Contributing

Suggestions welcome:

- UI improvements
- Additional categories
- Keyboard customization
- Performance optimizations

## ❓ FAQ

**Q: Can I change keyboard shortcuts?**
A: Yes! Edit the `bind()` calls in `unified_pipeline.py`

**Q: What if I accidentally stop?**
A: Just restart! Already-downloaded memes and sorted characters are skipped

**Q: Can I add more categories?**
A: Yes! Add folders in `setup_directories()` and update the controls

**Q: Where are unsorted characters?**
A: They're not saved - only sorted characters are stored

**Q: Can I sort offline?**
A: No, the pipeline requires internet for downloading and SAM3 model

**Q: What if a meme has no characters?**
A: It's skipped automatically and stats are updated

**Q: Can I process multiple memes simultaneously?**
A: No, but the pipeline is fast enough that you won't wait

## 🎓 Advanced Tips

### Custom Sorting Logic

Edit `sort_character()` in `unified_pipeline.py` to add custom rules

### Batch Processing Script

```python
from unified_pipeline import UnifiedPipeline

# Process 100 memes in batches of 20
for start_id in range(0, 100, 20):
    # Note: You'll still need to sort manually in UI
    print(f"Processing memes {start_id} to {start_id + 20}")
```

### Export Statistics

```python
import json

with open('sorted_characters/sorting_metadata.json', 'r') as f:
    data = json.load(f)
    stats = data['session_stats']
    print(f"Total sorted: {sum([stats[k] for k in ['Bo', 'Gau', 'Others', 'Discarded']])}")
```

## 🎉 Get Started!

```bash
python unified_pipeline.py
```

Configure your settings, click START, and begin sorting! 🚀
