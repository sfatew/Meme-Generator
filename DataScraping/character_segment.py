"""
character_segmenter.py - Segment and crop characters from meme images using SAM3
"""
import os
import json
from pathlib import Path
import torch
import numpy as np
from PIL import Image
from transformers import AutoProcessor, AutoModel

class CharacterSegmenter:
    def __init__(
        self, 
        output_dir="character_crops",
        model_name="facebook/sam3",
        device=None
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
    
    def save_metadata(self):
        """Save metadata to file"""
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)
    
    def setup_sam3(self):
        """Initialize SAM3 model from Hugging Face"""
        print(f"Loading SAM3 model from Hugging Face: {self.model_name}")
        
        try:
            # Load processor and model
            self.processor = AutoProcessor.from_pretrained(self.model_name)
            self.model = AutoModel.from_pretrained(self.model_name).to(self.device)
            self.model.eval()
            
            print(f"✓ SAM3 model loaded on {self.device}")
            
        except Exception as e:
            print(f"✗ Error loading SAM3: {e}")
            print("Note: SAM3 requires authentication. Run: huggingface-cli login")
    
    def generate_point_grid(self, width, height, grid_size=8):
        """
        Generate a grid of points for prompting
        
        Args:
            width: Image width
            height: Image height
            grid_size: Number of points per dimension
            
        Returns:
            List of (x, y) coordinates
        """
        points = []
        for i in range(1, grid_size + 1):
            for j in range(1, grid_size + 1):
                x = int(width * i / (grid_size + 1))
                y = int(height * j / (grid_size + 1))
                points.append([x, y])
        return points
    
    def segment_with_text_prompt(self, image, prompt="character"):
        """
        Segment using text prompt
        
        Args:
            image: PIL Image
            prompt: Text prompt for segmentation
            
        Returns:
            List of masks
        """
        # Prepare inputs with text prompt
        inputs = self.processor(
            images=image,
            text=prompt,
            return_tensors="pt"
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
        
        # Get masks
        masks = outputs.pred_masks.squeeze().cpu().numpy()
        scores = outputs.iou_scores.squeeze().cpu().numpy()
        
        return masks, scores
    
    def segment_with_points(self, image, points):
        """
        Segment using point prompts
        
        Args:
            image: PIL Image
            points: List of [x, y] coordinates
            
        Returns:
            List of masks and scores
        """
        # Prepare inputs with point prompts
        inputs = self.processor(
            images=image,
            input_points=[[points]],  # Batch of point sets
            return_tensors="pt"
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
        
        # Get masks
        masks = outputs.pred_masks.squeeze().cpu().numpy()
        scores = outputs.iou_scores.squeeze().cpu().numpy()
        
        return masks, scores
    
    def segment_automatic(self, image):
        """
        Automatic segmentation using multiple strategies
        
        Args:
            image: PIL Image
            
        Returns:
            List of (mask, bbox, score) tuples
        """
        width, height = image.size
        all_masks = []
        
        # Strategy 1: Text prompt for "character"
        print("  Running text-based segmentation...")
        try:
            masks, scores = self.segment_with_text_prompt(image, "character")
            
            # Process masks
            if masks.ndim == 2:
                masks = masks[np.newaxis, ...]
                scores = np.array([scores]) if np.isscalar(scores) else scores
            
            for mask, score in zip(masks, scores):
                if score > 0.5:  # Confidence threshold
                    all_masks.append((mask, score))
        except Exception as e:
            print(f"  Warning: Text-based segmentation failed: {e}")
        
        # Strategy 2: Grid-based point prompts
        print("  Running point-based segmentation...")
        try:
            grid_points = self.generate_point_grid(width, height, grid_size=6)
            
            for point in grid_points:
                masks, scores = self.segment_with_points(image, [point])
                
                if masks.ndim == 2:
                    masks = masks[np.newaxis, ...]
                    scores = np.array([scores]) if np.isscalar(scores) else scores
                
                for mask, score in zip(masks, scores):
                    if score > 0.6:
                        all_masks.append((mask, score))
        except Exception as e:
            print(f"  Warning: Point-based segmentation failed: {e}")
        
        # Remove duplicate/overlapping masks
        filtered_masks = self.filter_masks(all_masks, width * height)
        
        # Convert to (mask, bbox, score) format
        results = []
        for mask, score in filtered_masks:
            bbox = self.mask_to_bbox(mask)
            if bbox is not None:
                results.append((mask, bbox, score))
        
        return results
    
    def filter_masks(self, masks_with_scores, image_area, iou_threshold=0.7):
        """
        Filter overlapping and invalid masks
        
        Args:
            masks_with_scores: List of (mask, score) tuples
            image_area: Total image area
            iou_threshold: IoU threshold for considering masks as duplicates
            
        Returns:
            Filtered list of (mask, score) tuples
        """
        if not masks_with_scores:
            return []
        
        # Sort by score
        masks_with_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Filter by area
        min_area = image_area * 0.005  # Minimum 0.5%
        max_area = image_area * 0.85   # Maximum 85%
        
        valid_masks = []
        for mask, score in masks_with_scores:
            area = mask.sum()
            if min_area < area < max_area:
                valid_masks.append((mask, score))
        
        # Remove overlapping masks (non-maximum suppression)
        filtered = []
        for i, (mask1, score1) in enumerate(valid_masks):
            keep = True
            for mask2, score2 in filtered:
                iou = self.calculate_iou(mask1, mask2)
                if iou > iou_threshold:
                    keep = False
                    break
            if keep:
                filtered.append((mask1, score1))
                if len(filtered) >= 15:  # Max 15 characters
                    break
        
        return filtered
    
    def calculate_iou(self, mask1, mask2):
        """Calculate Intersection over Union between two masks"""
        intersection = np.logical_and(mask1, mask2).sum()
        union = np.logical_or(mask1, mask2).sum()
        return intersection / union if union > 0 else 0
    
    def mask_to_bbox(self, mask):
        """
        Convert mask to bounding box
        
        Args:
            mask: Binary mask array
            
        Returns:
            [x, y, width, height] or None if invalid
        """
        rows = np.any(mask, axis=1)
        cols = np.any(mask, axis=0)
        
        if not rows.any() or not cols.any():
            return None
        
        y_min, y_max = np.where(rows)[0][[0, -1]]
        x_min, x_max = np.where(cols)[0][[0, -1]]
        
        return [int(x_min), int(y_min), int(x_max - x_min), int(y_max - y_min)]
    
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
            # Verify files still exist
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
                # Extract bounding box
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
        """
        Segment characters from multiple images
        
        Args:
            image_paths: List of image file paths
            force: Force re-segmentation
            
        Returns:
            Dictionary mapping image_id to list of character crop paths
        """
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
        print(f"Average characters per image: {total_characters/len(image_paths):.1f}")
        print(f"Output directory: {self.output_dir}")
        print(f"Metadata file: {self.metadata_file}")
        
        return results
    
    def segment_directory(self, image_dir, force=False):
        """
        Segment all images in a directory
        
        Args:
            image_dir: Directory containing images
            force: Force re-segmentation
            
        Returns:
            Dictionary of results
        """
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

# # Example usage
# if __name__ == "__main__":
#     # Initialize segmenter with SAM3
#     segmenter = CharacterSegmenter(
#         output_dir="character_crops",
#         model_name="facebook/sam3"
#     )
    
#     # Segment all images from download directory
#     results = segmenter.segment_directory("meme_downloads")
    
#     # Or segment specific images
#     # results = segmenter.segment_batch([
#     #     "meme_downloads/meme_0.jpg",
#     #     "meme_downloads/meme_1.jpg"
#     # ])
    
#     # Or segment single image
#     # crops = segmenter.segment_image("meme_downloads/meme_0.jpg")