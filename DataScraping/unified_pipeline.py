"""
unified_pipeline.py - Modified: Save all crops to discard, then sort from there
Pipeline: download → segment to discard → load from discard → sort (move or keep)
"""
import os
import json
import shutil
from pathlib import Path
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont
from threading import Thread
import queue

from scraper import MemeScraper
from character_segment import CharacterSegmenter


class UnifiedPipeline:
    def __init__(self):
        """Initialize the unified pipeline"""
        self.root = None
        
        # Configuration variables
        self.start_id_var = None
        self.count_var = None
        self.delay_var = None
        self.download_dir_var = None
        self.sorted_dir_var = None
        self.hf_token_var = None
        
        # Pipeline components
        self.scraper = None
        self.segmenter = None
        
        # Output directories
        self.download_dir = None
        self.sorted_dir = None
        self.bo_folder = None
        self.gau_folder = None
        self.others_folder = None
        self.discarded_folder = None
        
        # Metadata
        self.metadata_file = None
        self.metadata = {}
        
        # Current state
        self.is_running = False
        self.current_meme_id = None
        self.images_to_sort = []  # List of image paths from discard folder
        self.current_index = 0
        self.current_image_path = None
        
        # Statistics
        self.stats = {
            'memes_processed': 0,
            'memes_downloaded': 0,
            'memes_skipped': 0,
            'Bo': 0,
            'Gau': 0,
            'Others': 0,
            'Discarded': 0,
            'total_characters': 0
        }
        
        # History for undo
        self.history = []
        
        # UI components
        self.config_frame = None
        self.progress_frame = None
        self.sorting_frame = None
        self.image_label = None
        self.info_label = None
        self.stats_label = None
        self.progress_label = None
        self.start_button = None
    
    def create_ui(self):
        """Create the unified UI"""
        self.root = tk.Tk()
        self.root.title("Meme Character Pipeline")
        self.root.geometry("1100x900")
        self.root.configure(bg='#2b2b2b')
        
        # Title
        title_font = tkfont.Font(family="Arial", size=24, weight="bold")
        title = tk.Label(
            self.root,
            text="🎯 Meme Character Extraction Pipeline",
            font=title_font,
            bg='#2b2b2b',
            fg='#ffffff'
        )
        title.pack(pady=15)
        
        # Configuration Frame
        self.create_config_frame()
        
        # Progress Frame
        self.create_progress_frame()
        
        # Sorting Frame
        self.create_sorting_frame()
        
        # Bind keyboard events
        self.root.bind('<Left>', lambda e: self.sort_character('Bo') if self.is_running else None)
        self.root.bind('<Right>', lambda e: self.sort_character('Gau') if self.is_running else None)
        self.root.bind('<Up>', lambda e: self.sort_character('Others') if self.is_running else None)
        self.root.bind('<Down>', lambda e: self.sort_character('Discarded') if self.is_running else None)
        self.root.bind('<BackSpace>', lambda e: self.undo_action() if self.is_running else None)
        self.root.bind('<Escape>', lambda e: self.stop_pipeline())
    
    def create_config_frame(self):
        """Create configuration input frame"""
        self.config_frame = tk.LabelFrame(
            self.root,
            text="Configuration",
            font=("Arial", 12, "bold"),
            bg='#2b2b2b',
            fg='#ffffff',
            relief=tk.RIDGE,
            borderwidth=2
        )
        self.config_frame.pack(pady=10, padx=20, fill=tk.X)
        
        # Grid layout for inputs
        input_font = ("Arial", 10)
        
        # Row 1: Meme IDs
        tk.Label(
            self.config_frame,
            text="Start Meme ID:",
            font=input_font,
            bg='#2b2b2b',
            fg='#cccccc'
        ).grid(row=0, column=0, padx=10, pady=5, sticky=tk.W)
        
        self.start_id_var = tk.StringVar(value="0")
        tk.Entry(
            self.config_frame,
            textvariable=self.start_id_var,
            width=15,
            font=input_font
        ).grid(row=0, column=1, padx=10, pady=5, sticky=tk.W)
        
        tk.Label(
            self.config_frame,
            text="Count:",
            font=input_font,
            bg='#2b2b2b',
            fg='#cccccc'
        ).grid(row=0, column=2, padx=10, pady=5, sticky=tk.W)
        
        self.count_var = tk.StringVar(value="5")
        tk.Entry(
            self.config_frame,
            textvariable=self.count_var,
            width=15,
            font=input_font
        ).grid(row=0, column=3, padx=10, pady=5, sticky=tk.W)
        
        # Row 2: Delay
        tk.Label(
            self.config_frame,
            text="Delay (seconds):",
            font=input_font,
            bg='#2b2b2b',
            fg='#cccccc'
        ).grid(row=1, column=0, padx=10, pady=5, sticky=tk.W)
        
        self.delay_var = tk.StringVar(value="2")
        tk.Entry(
            self.config_frame,
            textvariable=self.delay_var,
            width=15,
            font=input_font
        ).grid(row=1, column=1, padx=10, pady=5, sticky=tk.W)
        
        # Row 3: Directories
        tk.Label(
            self.config_frame,
            text="Download Dir:",
            font=input_font,
            bg='#2b2b2b',
            fg='#cccccc'
        ).grid(row=2, column=0, padx=10, pady=5, sticky=tk.W)
        
        self.download_dir_var = tk.StringVar(value="meme_downloads")
        tk.Entry(
            self.config_frame,
            textvariable=self.download_dir_var,
            width=20,
            font=input_font
        ).grid(row=2, column=1, padx=10, pady=5, sticky=tk.W, columnspan=2)
        
        tk.Label(
            self.config_frame,
            text="Output Dir:",
            font=input_font,
            bg='#2b2b2b',
            fg='#cccccc'
        ).grid(row=3, column=0, padx=10, pady=5, sticky=tk.W)
        
        self.sorted_dir_var = tk.StringVar(value="sorted_characters")
        tk.Entry(
            self.config_frame,
            textvariable=self.sorted_dir_var,
            width=20,
            font=input_font
        ).grid(row=3, column=1, padx=10, pady=5, sticky=tk.W, columnspan=2)
        
        # Row 4: HF Token
        tk.Label(
            self.config_frame,
            text="HF Token:",
            font=input_font,
            bg='#2b2b2b',
            fg='#cccccc'
        ).grid(row=4, column=0, padx=10, pady=5, sticky=tk.W)
        
        self.hf_token_var = tk.StringVar(value="")
        hf_entry = tk.Entry(
            self.config_frame,
            textvariable=self.hf_token_var,
            width=30,
            font=input_font,
            show="*"
        )
        hf_entry.grid(row=4, column=1, padx=10, pady=5, sticky=tk.W, columnspan=2)
        
        tk.Label(
            self.config_frame,
            text="(from https://huggingface.co/settings/tokens)",
            font=("Arial", 8),
            bg='#2b2b2b',
            fg='#888888'
        ).grid(row=5, column=1, padx=10, pady=2, sticky=tk.W, columnspan=2)
        
        # Start button
        self.start_button = tk.Button(
            self.config_frame,
            text="▶ START PIPELINE",
            command=self.start_pipeline,
            font=("Arial", 12, "bold"),
            bg='#4CAF50',
            fg='white',
            relief=tk.RAISED,
            borderwidth=3,
            padx=20,
            pady=10,
            cursor="hand2"
        )
        self.start_button.grid(row=0, column=4, rowspan=6, padx=20, pady=5)
    
    def create_progress_frame(self):
        """Create progress tracking frame"""
        self.progress_frame = tk.LabelFrame(
            self.root,
            text="Progress",
            font=("Arial", 12, "bold"),
            bg='#2b2b2b',
            fg='#ffffff',
            relief=tk.RIDGE,
            borderwidth=2
        )
        self.progress_frame.pack(pady=5, padx=20, fill=tk.X)
        
        self.progress_label = tk.Label(
            self.progress_frame,
            text="Ready to start...",
            font=("Arial", 10),
            bg='#2b2b2b',
            fg='#cccccc',
            justify=tk.LEFT
        )
        self.progress_label.pack(pady=5, padx=10)
    
    def create_sorting_frame(self):
        """Create character sorting frame"""
        self.sorting_frame = tk.LabelFrame(
            self.root,
            text="Character Sorting",
            font=("Arial", 12, "bold"),
            bg='#2b2b2b',
            fg='#ffffff',
            relief=tk.RIDGE,
            borderwidth=2
        )
        self.sorting_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        # Info label
        self.info_label = tk.Label(
            self.sorting_frame,
            text="Waiting for characters...",
            font=("Arial", 11),
            bg='#2b2b2b',
            fg='#cccccc'
        )
        self.info_label.pack(pady=5)
        
        # Image display
        image_frame = tk.Frame(self.sorting_frame, bg='#1a1a1a', relief=tk.SUNKEN, borderwidth=2)
        image_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        self.image_label = tk.Label(image_frame, bg='#1a1a1a')
        self.image_label.pack(expand=True)
        
        # Controls
        controls_frame = tk.Frame(self.sorting_frame, bg='#2b2b2b')
        controls_frame.pack(pady=10)
        
        control_font = tkfont.Font(family="Arial", size=11, weight="bold")
        controls = [
            ("← Left", "Bo", "#4CAF50"),
            ("→ Right", "Gau", "#2196F3"),
            ("↑ Up", "Others", "#FF9800"),
            ("↓ Down", "Discard", "#f44336"),
            ("⌫ Back", "Undo", "#9E9E9E")
        ]
        
        for key, action, color in controls:
            frame = tk.Frame(controls_frame, bg='#2b2b2b')
            frame.pack(side=tk.LEFT, padx=10)
            
            tk.Label(frame, text=key, font=control_font, bg='#2b2b2b', fg=color).pack()
            tk.Label(frame, text=action, font=("Arial", 9), bg='#2b2b2b', fg='#cccccc').pack()
        
        # Statistics
        self.stats_label = tk.Label(
            self.sorting_frame,
            text="",
            font=("Arial", 10),
            bg='#2b2b2b',
            fg='#aaaaaa'
        )
        self.stats_label.pack(pady=5)
        
        self.update_stats_display()
    
    def update_progress(self, message):
        """Update progress label"""
        self.progress_label.config(text=message)
        self.root.update()
    
    def update_stats_display(self):
        """Update statistics display"""
        remaining = len(self.images_to_sort) - self.current_index
        stats_text = (
            f"Memes: {self.stats['memes_processed']} processed | "
            f"Remaining: {remaining} | "
            f"Bo: {self.stats['Bo']} | Gau: {self.stats['Gau']} | "
            f"Others: {self.stats['Others']} | Discarded: {self.stats['Discarded']}"
        )
        self.stats_label.config(text=stats_text)
    
    def setup_directories(self):
        """Setup output directories"""
        self.download_dir = Path(self.download_dir_var.get())
        self.sorted_dir = Path(self.sorted_dir_var.get())
        
        self.bo_folder = self.sorted_dir / "Bo"
        self.gau_folder = self.sorted_dir / "Gau"
        self.others_folder = self.sorted_dir / "Others"
        self.discarded_folder = self.sorted_dir / "Discarded"
        
        for folder in [self.bo_folder, self.gau_folder, self.others_folder, self.discarded_folder]:
            folder.mkdir(parents=True, exist_ok=True)
        
        # Load metadata
        self.metadata_file = self.sorted_dir / "sorting_metadata.json"
        self.load_metadata()
    
    def load_metadata(self):
        """Load existing metadata"""
        if self.metadata_file and self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.metadata = data
                # Load stats
                for key in self.stats:
                    if key in data.get('session_stats', {}):
                        self.stats[key] = data['session_stats'][key]
    
    def save_metadata(self):
        """Save metadata to file"""
        self.metadata['session_stats'] = self.stats
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)
    
    def start_pipeline(self):
        """Start the pipeline in a background thread"""
        if self.is_running:
            messagebox.showwarning("Already Running", "Pipeline is already running!")
            return
        
        # Validate inputs
        try:
            start_id = int(self.start_id_var.get())
            count = int(self.count_var.get())
            delay = float(self.delay_var.get())
            
            if count <= 0:
                raise ValueError("Count must be positive")
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please check your inputs: {e}")
            return
        
        # Setup
        self.setup_directories()
        self.is_running = True
        self.start_button.config(state=tk.DISABLED, text="RUNNING...", bg='#757575')
        
        # Run pipeline in background thread
        thread = Thread(target=self.run_pipeline, daemon=True)
        thread.start()
    
    def run_pipeline(self):
        """Run the download and segmentation pipeline"""
        try:
            start_id = int(self.start_id_var.get())
            count = int(self.count_var.get())
            delay = float(self.delay_var.get())
            
            # Phase 1: Download all memes in batch
            self.update_progress("Downloading memes in batch...")
            self.scraper = MemeScraper(download_dir=str(self.download_dir))
            
            downloaded_results = self.scraper.download_batch(
                start_id=start_id,
                count=count,
                delay=delay,
                force=False
            )
            
            # Update stats from download
            downloaded_memes = [int(mid) for mid in downloaded_results.keys()]
            self.stats['memes_downloaded'] = len(downloaded_memes)
            self.stats['memes_skipped'] = len(self.scraper.get_skipped_memes())
            
            # Cleanup scraper
            if self.scraper:
                self.scraper.cleanup()
            
            if not downloaded_memes:
                self.update_progress("No memes downloaded. Nothing to segment.")
                self.show_completion()
                return
            
            # Phase 2: Load SAM3 and segment all downloaded memes
            self.update_progress("Loading SAM3 model...")
            hf_token = self.hf_token_var.get().strip() or None
            self.segmenter = CharacterSegmenter(
                output_dir=str(self.discarded_folder), 
                hf_token=hf_token
            )
            
            # Segment all downloaded memes
            total_characters = 0
            for meme_id in downloaded_memes:
                if not self.is_running:
                    break
                
                self.current_meme_id = meme_id
                meme_path = downloaded_results[meme_id]
                
                self.update_progress(f"Segmenting meme {meme_id}...")
                
                try:
                    character_paths = self.segmenter.segment_image(meme_path, force=False)
                    
                    if character_paths:
                        total_characters += len(character_paths)
                        self.update_progress(
                            f"Saved {len(character_paths)} characters from meme {meme_id}"
                        )
                    else:
                        self.update_progress(f"No characters found in meme {meme_id}")
                    
                    self.stats['memes_processed'] += 1
                    
                except Exception as e:
                    self.update_progress(f"Error segmenting meme {meme_id}: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Cleanup scraper
            if self.scraper:
                self.scraper.cleanup()
            
            # Now load all images from discard folder for sorting
            self.update_progress("Loading characters for sorting...")
            self.load_images_from_discard()
            
            self.stats['total_characters'] = total_characters
            
            # Start sorting phase
            if self.images_to_sort:
                self.update_progress(f"Ready to sort {len(self.images_to_sort)} characters")
                self.root.after(100, self.show_next_character)
            else:
                self.update_progress("No characters to sort")
                self.show_completion()
            
        except Exception as e:
            messagebox.showerror("Pipeline Error", f"An error occurred: {e}")
            import traceback
            traceback.print_exc()
            self.stop_pipeline()
    
    def load_images_from_discard(self):
        """Load all images from discard folder for sorting"""
        self.images_to_sort = []
        
        # Get all PNG files from discard folder
        for img_path in sorted(self.discarded_folder.glob("*.png")):
            # Skip if already sorted (check metadata)
            if 'sorted_images' in self.metadata:
                # Check if this file was moved (it shouldn't exist in discard if moved)
                # But we'll check metadata to see if it was already processed
                already_sorted = False
                for sorted_path, info in self.metadata['sorted_images'].items():
                    sorted_path_obj = Path(sorted_path)
                    if sorted_path_obj.name == img_path.name:
                        # Check if it was moved to another folder
                        if sorted_path_obj.parent != self.discarded_folder:
                            already_sorted = True
                            break
                
                if already_sorted:
                    continue
            
            self.images_to_sort.append(img_path)
        
        self.current_index = 0
        print(f"Loaded {len(self.images_to_sort)} images for sorting")
    
    def show_next_character(self):
        """Show next character from the list"""
        if not self.is_running:
            return
        
        if self.current_index >= len(self.images_to_sort):
            # All sorted
            self.show_completion()
            return
        
        self.current_image_path = self.images_to_sort[self.current_index]
        
        # Update info
        img_name = self.current_image_path.name
        self.info_label.config(
            text=f"Character {self.current_index + 1}/{len(self.images_to_sort)} - {img_name}"
        )
        
        # Display image
        try:
            img = Image.open(self.current_image_path)
            
            # Resize to fit
            max_size = (700, 500)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            photo = ImageTk.PhotoImage(img)
            self.image_label.config(image=photo)
            self.image_label.image = photo
        except Exception as e:
            print(f"Error loading image {self.current_image_path}: {e}")
            # Skip to next
            self.current_index += 1
            self.root.after(100, self.show_next_character)
            return
        
        self.update_stats_display()
    
    def sort_character(self, category):
        """Sort current character into category"""
        if not self.current_image_path or not self.current_image_path.exists():
            return
        
        # Determine destination
        folder_map = {
            'Bo': self.bo_folder,
            'Gau': self.gau_folder,
            'Others': self.others_folder,
            'Discarded': self.discarded_folder
        }
        destination = folder_map[category]
        
        # If discarded, just leave it there
        if category == 'Discarded':
            # Just update metadata and move to next
            if 'sorted_images' not in self.metadata:
                self.metadata['sorted_images'] = {}
            
            self.metadata['sorted_images'][str(self.current_image_path)] = {
                'category': 'Discarded',
                'original_path': str(self.current_image_path)
            }
            self.save_metadata()
            
            self.stats['Discarded'] += 1
            
            # Add to history
            self.history.append({
                'source': self.current_image_path,
                'destination': self.current_image_path,  # Same location
                'category': category,
                'action': 'keep'
            })
        else:
            # Move to destination folder
            dest_path = destination / self.current_image_path.name
            
            # Handle duplicates
            if dest_path.exists():
                counter = 1
                stem = dest_path.stem
                suffix = dest_path.suffix
                while dest_path.exists():
                    dest_path = destination / f"{stem}_{counter}{suffix}"
                    counter += 1
            
            # Move file
            shutil.move(str(self.current_image_path), str(dest_path))
            
            # Update metadata
            if 'sorted_images' not in self.metadata:
                self.metadata['sorted_images'] = {}
            
            self.metadata['sorted_images'][str(dest_path)] = {
                'category': category,
                'original_path': str(self.current_image_path)
            }
            self.save_metadata()
            
            # Update stats
            self.stats[category] += 1
            
            # Add to history
            self.history.append({
                'source': self.current_image_path,
                'destination': dest_path,
                'category': category,
                'action': 'move'
            })
        
        # Move to next character
        self.current_index += 1
        self.update_stats_display()
        
        # Show next
        self.root.after(100, self.show_next_character)
    
    def undo_action(self):
        """Undo last sorting action"""
        if not self.history:
            messagebox.showwarning("Undo", "Nothing to undo!")
            return
        
        last = self.history.pop()
        source = last['source']
        destination = last['destination']
        category = last['category']
        action = last['action']
        
        if action == 'move':
            # Move back from destination to discard
            if destination.exists():
                shutil.move(str(destination), str(source))
            
            # Update metadata
            if str(destination) in self.metadata.get('sorted_images', {}):
                del self.metadata['sorted_images'][str(destination)]
                self.save_metadata()
        else:  # action == 'keep' (for Discarded)
            # Remove from metadata
            if str(source) in self.metadata.get('sorted_images', {}):
                del self.metadata['sorted_images'][str(source)]
                self.save_metadata()
        
        # Update stats
        self.stats[category] -= 1
        
        # Go back one step
        self.current_index = max(0, self.current_index - 1)
        
        # Show previous character
        self.show_next_character()
        
        self.update_stats_display()
    
    def show_completion(self):
        """Show completion message"""
        self.is_running = False
        self.start_button.config(state=tk.NORMAL, text="▶ START PIPELINE", bg='#4CAF50')
        
        self.image_label.config(
            text="🎉 Pipeline Complete!",
            font=("Arial", 24, "bold"),
            fg='#4CAF50'
        )
        
        self.info_label.config(text="All characters sorted!")
        self.update_progress("Pipeline complete!")
        
        # Count remaining in discard folder (not in metadata as sorted)
        remaining_in_discard = 0
        for img_path in self.discarded_folder.glob("*.png"):
            if str(img_path) not in self.metadata.get('sorted_images', {}):
                remaining_in_discard += 1
        
        # Show summary
        total_sorted = sum([self.stats[k] for k in ['Bo', 'Gau', 'Others', 'Discarded']])
        summary = (
            f"Pipeline Complete!\n\n"
            f"Memes processed: {self.stats['memes_processed']}\n"
            f"Memes downloaded: {self.stats['memes_downloaded']}\n"
            f"Memes skipped: {self.stats['memes_skipped']}\n"
            f"Total characters extracted: {self.stats.get('total_characters', 0)}\n\n"
            f"Characters sorted:\n"
            f"  Bo: {self.stats['Bo']}\n"
            f"  Gau: {self.stats['Gau']}\n"
            f"  Others: {self.stats['Others']}\n"
            f"  Discarded: {self.stats['Discarded']}\n\n"
            f"Total sorted: {total_sorted}\n"
            f"Remaining unsorted: {remaining_in_discard}"
        )
        
        messagebox.showinfo("Complete", summary)
    
    def stop_pipeline(self):
        """Stop the pipeline"""
        if messagebox.askyesno("Stop", "Stop the pipeline?"):
            self.is_running = False
            self.start_button.config(state=tk.NORMAL, text="▶ START PIPELINE", bg='#4CAF50')
            self.update_progress("Pipeline stopped by user")
    
    def run(self):
        """Run the application"""
        self.create_ui()
        self.root.mainloop()


if __name__ == "__main__":
    app = UnifiedPipeline()
    app.run()