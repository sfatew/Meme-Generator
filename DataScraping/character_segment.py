"""
character_segmenter.py - Segment and crop characters from meme images using SAM3
"""
import os
import json
from pathlib import Path
import torch
import numpy as np
from PIL import Image
from transformers.models.sam3 import Sam3Processor, Sam3Model
from huggingface_hub import login, whoami

class CharacterSegmenter:
    def __init__(
        self, 
        output_dir="character_crops",
        model_name="facebook/sam3",
        device=None,
        hf_token=None
    ):
        """
        Initialize the character segmenter with SAM3
        
        Args:
            output_dir: Directory to store cropped character images
            model_name: Hugging Face model name
            device: Device to use ('cuda' or 'cpu'), auto-detect if None
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Create metadata file
        self.metadata_file = self.output_dir / "segmentation_metadata.json"
        self.metadata = self.load_metadata()
        
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.hf_token = hf_token
        
        # Setup SAM3
        self.processor = None
        self.model = None
        self.setup_sam3()
    
    def load_metadata(self):
        """Load existing metadata or create new"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def ensure_hf_login(self):
        """Ensure user is logged in to Hugging Face"""
        try:
            # Check if user is already logged in
            user_info = whoami()
            print(f"✓ Logged in to Hugging Face as: {user_info['name']}")
            return True
        except Exception:
            # If token is provided, use it
            if self.hf_token:
                try:
                    login(token=self.hf_token)
                    print("✓ Successfully logged in to Hugging Face with provided token")
                    return True
                except Exception as e:
                    print(f"✗ Error during login with provided token: {e}")
                    return False
            else:
                print("⚠ No Hugging Face token provided")
                print("SAM3 model requires Hugging Face authentication.")
                print("Please provide a token via the UI or set hf_token parameter.")
                return False
    
    def save_metadata(self):
        """Save metadata to file"""
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)
    
    def setup_sam3(self):
        """Initialize SAM3 model from Hugging Face"""
        print(f"Loading SAM3 model from Hugging Face: {self.model_name}")
        
        # Ensure HF authentication
        self.ensure_hf_login()
        
        try:
            # Load processor and model specifically for SAM3
            self.processor = Sam3Processor.from_pretrained(self.model_name)
            self.model = Sam3Model.from_pretrained(self.model_name).to(self.device)
            self.model.eval()
            
            print(f"✓ SAM3 model loaded on {self.device}")
            
        except Exception as e:
            print(f"✗ Error loading SAM3: {e}")
            print("Note: Make sure you are authenticated with Hugging Face")
    
    def segment_with_text_prompt(self, image, prompt="character", threshold=0.5):
        """
        Segment using text prompt and post-process results
        
        Args:
            image: PIL Image
            prompt: Text prompt for segmentation
            threshold: Confidence threshold
            
        Returns:
            Dictionary containing 'masks', 'boxes', 'scores'
        """
        # Prepare inputs with text prompt
        inputs = self.processor(
            images=image,
            text=prompt,
            return_tensors="pt"
        ).to(self.device)
        
        print("Successfully prepared imputs")

        with torch.no_grad():
            outputs = self.model(**inputs)
        
        # Use the correct post-processing method for SAM3
        results = self.processor.post_process_instance_segmentation(
            outputs,
            threshold=threshold,
            mask_threshold=0.5,
            target_sizes=inputs.get("original_sizes").tolist()
        )[0]
        
        print("Segmentation result obtained")

        # Move tensors to CPU and convert to numpy for easier downstream processing
        return {
            "masks": results["masks"].cpu().numpy(), # Shape: (N, H, W) bool
            "boxes": results["boxes"].cpu().numpy(), # Shape: (N, 4) xyxy
            "scores": results["scores"].cpu().numpy() # Shape: (N,)
        }

    def segment_automatic(self, image):
        """
        Automatic segmentation using text prompt strategy
        
        Args:
            image: PIL Image
            
        Returns:
            List of (mask, bbox, score) tuples
        """
        width, height = image.size
        all_masks = []
        
        print("  Running text-based segmentation...")
        try:
            # Get processed results directly
            results = self.segment_with_text_prompt(image, "character", threshold=0.4)
            
            masks = results["masks"]
            boxes = results["boxes"]
            scores = results["scores"]

            # Pack into list for filtering
            for i in range(len(scores)):
                mask = masks[i]
                bbox = boxes[i] # already in [x_min, y_min, x_max, y_max] format usually
                score = scores[i]
                
                # Convert bbox to [x, y, w, h] for consistency with rest of pipeline if needed,
                # BUT the standard output is usually [x1, y1, x2, y2]. 
                # Let's standardize to [x, y, w, h] for the filter function or adapt filter function.
                # Actually, let's keep it as is and just construct the tuple.
                # The 'filter_masks' function expects (mask, score).
                
                all_masks.append((mask, score, bbox))
                
        except Exception as e:
            print(f"  Warning: Text-based segmentation failed: {e}")
            import traceback
            traceback.print_exc()

        # Remove duplicate/overlapping masks
        # Note: filter_masks currently expects (mask, score), we need to adapt it 
        # or pass data differently. 
        filtered_results = self.filter_masks_with_boxes(all_masks, width * height)
        
        return filtered_results
    
    def filter_masks_with_boxes(self, masks_data, image_area, iou_threshold=0.7):
        """
        Filter overlapping and invalid masks, preserving pre-calculated boxes
        
        Args:
            masks_data: List of (mask, score, bbox) tuples
            image_area: Total image area
            
        Returns:
            Filtered list of (mask, bbox, score) tuples
        """
        if not masks_data:
            return []
        
        # Sort by score
        masks_data.sort(key=lambda x: x[1], reverse=True)
        
        # Filter by area
        min_area = image_area * 0.005
        max_area = image_area * 0.85
        
        valid_items = []
        for mask, score, bbox in masks_data:
            area = mask.sum()
            if min_area < area < max_area:
                valid_items.append((mask, score, bbox))
        
        # Remove overlapping (NMS)
        filtered = []
        for i, (mask1, score1, bbox1) in enumerate(valid_items):
            keep = True
            for mask2, _, _ in filtered:
                iou = self.calculate_iou(mask1, mask2)
                if iou > iou_threshold:
                    keep = False
                    break
            if keep:
                # Convert xyxy (if that's what SAM3 returns) to xywh for the cropping logic
                # SAM3 post_process returns [x1, y1, x2, y2]
                x1, y1, x2, y2 = bbox1
                w = x2 - x1
                h = y2 - y1
                final_bbox = [int(x1), int(y1), int(w), int(h)]
                
                filtered.append((mask1, final_bbox, score1))
                if len(filtered) >= 15:
                    break
        
        return filtered
    
    def calculate_iou(self, mask1, mask2):
        """Calculate Intersection over Union between two masks"""
        intersection = np.logical_and(mask1, mask2).sum()
        union = np.logical_or(mask1, mask2).sum()
        return intersection / union if union > 0 else 0
    
    def segment_image(self, image_path, force=False):
        """
        Segment characters from a single image
        
        Args:
            image_path: Path to the image file
            force: Force re-segmentation even if already processed
            
        Returns:
            List of paths to cropped character images
        """
        image_path = Path(image_path)
        image_id = image_path.stem
        
        # Check if already processed
        if not force and image_id in self.metadata:
            print(f"⊙ Image {image_id} already segmented")
            existing_crops = self.metadata[image_id].get('character_crops', [])
            if all(Path(crop).exists() for crop in existing_crops):
                return existing_crops
        
        print(f"\nSegmenting: {image_path}")
        
        if self.model is None or self.processor is None:
            print("✗ SAM3 model not loaded")
            return []
        
        try:
            # Load image
            image = Image.open(image_path).convert("RGB")
            width, height = image.size
            
            # Run automatic segmentation
            masks_data = self.segment_automatic(image)
            
            print(f"  Found {len(masks_data)} potential characters")
            
            # Crop each character
            character_images = []
            for idx, (mask, bbox, score) in enumerate(masks_data):
                # Extract bounding box [x, y, w, h]
                x, y, box_w, box_h = bbox
                x_min, y_min = x, y
                x_max, y_max = x + box_w, y + box_h
                
                # Add padding
                padding = 10
                x_min = max(0, x_min - padding)
                y_min = max(0, y_min - padding)
                x_max = min(width, x_max + padding)
                y_max = min(height, y_max + padding)
                
                # Crop image
                cropped = image.crop((x_min, y_min, x_max, y_max))
                
                # Save cropped character
                output_path = self.output_dir / f"{image_id}_char_{idx:02d}.png"
                cropped.save(output_path)
                character_images.append(str(output_path))
                print(f"  ✓ Saved character {idx}: {output_path.name} (score: {score:.3f})")
            
            # Save metadata
            self.metadata[image_id] = {
                'source_image': str(image_path),
                'character_count': len(character_images),
                'character_crops': character_images,
                'method': 'sam3_auto'
            }
            self.save_metadata()
            
            print(f"✓ Segmented {len(character_images)} characters from {image_id}")
            return character_images
            
        except Exception as e:
            print(f"✗ Error segmenting {image_path}: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def segment_batch(self, image_paths, force=False):
        """Segment characters from multiple images"""
        print(f"\n{'='*60}")
        print(f"Segmenting {len(image_paths)} images")
        print(f"{'='*60}")
        
        results = {}
        total_characters = 0
        
        for image_path in image_paths:
            character_images = self.segment_image(image_path, force=force)
            image_id = Path(image_path).stem
            results[image_id] = character_images
            total_characters += len(character_images)
        
        # Summary
        print(f"\n{'='*60}")
        print("SEGMENTATION SUMMARY")
        print(f"{'='*60}")
        print(f"Processed images: {len(image_paths)}")
        print(f"Total characters extracted: {total_characters}")
        if len(image_paths) > 0:
            print(f"Average characters per image: {total_characters/len(image_paths):.1f}")
        print(f"Output directory: {self.output_dir}")
        
        return results
    
    def segment_directory(self, image_dir, force=False):
        """Segment all images in a directory"""
        image_dir = Path(image_dir)
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        
        image_paths = [
            p for p in image_dir.iterdir() 
            if p.suffix.lower() in image_extensions
        ]
        
        if not image_paths:
            print(f"✗ No images found in {image_dir}")
            return {}
        
        return self.segment_batch(image_paths, force=force)