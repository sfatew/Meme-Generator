"""
image_captioner.py - Auto-caption images using WD Tagger
"""
import os
import json
from pathlib import Path
import torch
import numpy as np
from PIL import Image
from transformers import AutoProcessor, AutoModelForImageClassification
from collections import Counter
from huggingface_hub import hf_hub_download
import pandas as pd

import torch
from pathlib import Path
from PIL import Image
import pandas as pd
from transformers import AutoProcessor, AutoModelForImageClassification
from huggingface_hub import hf_hub_download
import numpy as np

class ImageCaptioner:
    def __init__(
        self,
        model_name="SmilingWolf/wd-swinv2-tagger-v3",
        device=None,
        threshold=0.35
    ):
        """
        Initialize the image captioner with WD Tagger
        """
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.threshold = threshold
        
        # Data storage
        self.processor = None
        self.model = None
        self.tag_names = []       # List of tag names
        self.tag_categories = []  # List of tag categories (0=General, 4=Character, etc)
        
        self.setup_model()
    
    def setup_model(self):
        """Initialize WD Tagger model and load specific tag data"""
        print(f"Loading WD Tagger model: {self.model_name}")
        
        try:
            # 1. Download the specific tag CSV
            print("...Fetching selected_tags.csv")
            csv_path = hf_hub_download(
                repo_id=self.model_name,
                filename="selected_tags.csv"
            )
            
            # 2. Load tags using pandas
            df = pd.read_csv(csv_path)
            
            # Extract names and categories into lists (preserving index order is crucial)
            self.tag_names = df['name'].tolist()
            self.tag_categories = df['category'].tolist()
            
            # 3. Load Model & Processor
            self.processor = AutoProcessor.from_pretrained(self.model_name)
            self.model = AutoModelForImageClassification.from_pretrained(
                self.model_name
            ).to(self.device)
            self.model.eval()
            
            print(f"✓ Model loaded on {self.device}")
            print(f"✓ Loaded {len(self.tag_names)} tags")
            
        except Exception as e:
            print(f"✗ Error loading model: {e}")
            raise
    
    def caption_single_image(self, image_path, save_txt=True):
        """
        Generate caption for a single image, keeping only Category 0 tags
        """
        image_path = Path(image_path)
        
        try:
            # Load image
            image = Image.open(image_path).convert("RGB")
            
            # Prepare inputs
            inputs = self.processor(images=image, return_tensors="pt").to(self.device)
            
            # Get predictions
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits[0]
            
            # Get probabilities
            probs = torch.sigmoid(logits).cpu().numpy()
            
            tags = {}
            
            # Iterate through all probabilities
            for idx, prob in enumerate(probs):
                if prob >= self.threshold:
                    # Safety check: ensure index exists in our loaded CSV data
                    if idx < len(self.tag_names):
                        
                        # --- FILTER: ONLY KEEP CATEGORY 0 (GENERAL TAGS) ---
                        if self.tag_categories[idx] == 0:
                            
                            tag_name = self.tag_names[idx]
                            # Clean up underscores
                            tag_name_clean = tag_name.replace("_", " ")
                            tags[tag_name_clean] = float(prob)
            
            # Sort by score
            sorted_tags = dict(sorted(tags.items(), key=lambda x: x[1], reverse=True))
            
            # Save to txt file
            if save_txt and sorted_tags:
                txt_path = image_path.with_suffix('.txt')
                self.save_caption_file(txt_path, sorted_tags)
            
            return sorted_tags
            
        except Exception as e:
            print(f"✗ Error captioning {image_path.name}: {e}")
            return {}
    
    def save_caption_file(self, txt_path, tags):
        """Save tags to a text file (comma-separated)"""
        tag_string = ", ".join(tags.keys())
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(tag_string)
            
    def load_caption_file(self, txt_path):
        """Load tags from a text file"""
        try:
            with open(txt_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    return [tag.strip() for tag in content.split(',')]
            return []
        except:
            return []
    
    def caption_batch(self, image_dir, pattern="*.png"):
        """
        Caption all images in a directory
        
        Args:
            image_dir: Directory containing images
            pattern: File pattern to match
            
        Returns:
            Dictionary mapping image paths to tags
        """
        image_dir = Path(image_dir)
        image_paths = sorted(image_dir.glob(pattern))
        
        if not image_paths:
            print(f"No images found in {image_dir}")
            return {}
        
        print(f"\nCaptioning {len(image_paths)} images from {image_dir.name}...")
        
        results = {}
        for idx, img_path in enumerate(image_paths):
            print(f"  [{idx+1}/{len(image_paths)}] {img_path.name}...", end=" ")
            
            # Check if already captioned
            txt_path = img_path.with_suffix('.txt')
            if txt_path.exists():
                print("already captioned ⊙")
                tags = self.load_caption_file(txt_path)
                results[str(img_path)] = tags
                continue
            
            # Generate caption
            tags_dict = self.caption_single_image(img_path, save_txt=True)
            results[str(img_path)] = list(tags_dict.keys())
            
            print(f"✓ {len(tags_dict)} tags")
        
        print(f"\n✓ Captioned {len(results)} images")
        return results
    
    def get_tag_statistics(self, results):
        """
        Get statistics of all tags across images
        
        Args:
            results: Dictionary mapping image paths to tag lists
            
        Returns:
            Counter object with tag frequencies
        """
        all_tags = []
        for tags in results.values():
            all_tags.extend(tags)
        
        return Counter(all_tags)
    
    def remove_tag_from_all(self, tag_to_remove, image_dir):
        """
        Remove a specific tag from all caption files in a directory
        
        Args:
            tag_to_remove: Tag to remove
            image_dir: Directory containing images and .txt files
            
        Returns:
            Number of files modified
        """
        image_dir = Path(image_dir)
        txt_files = list(image_dir.glob("*.txt"))
        
        modified_count = 0
        
        for txt_path in txt_files:
            tags = self.load_caption_file(txt_path)
            
            if tag_to_remove in tags:
                # Remove the tag
                tags = [t for t in tags if t != tag_to_remove]
                
                # Save back
                tag_string = ", ".join(tags)
                with open(txt_path, 'w', encoding='utf-8') as f:
                    f.write(tag_string)
                
                modified_count += 1
        
        return modified_count
    
    def get_image_tags(self, image_path):
        """Get tags for a specific image"""
        txt_path = Path(image_path).with_suffix('.txt')
        return self.load_caption_file(txt_path)