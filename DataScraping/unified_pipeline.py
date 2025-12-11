"""
unified_pipeline.py - Complete pipeline with single UI: download → segment → sort
Characters are sorted immediately after segmentation without intermediate storage
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
        self.character_queue = queue.Queue()
        self.current_character = None
        self.characters_buffer = []  # Buffer of characters from current meme
        self.character_index = 0
        
        # Statistics
        self.stats = {
            'memes_processed': 0,
            'memes_downloaded': 0,
            'memes_skipped': 0,
            'Bo': 0,
            'Gau': 0,
            'Others': 0,
            'Discarded': 0
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
        self.start_button.grid(row=0, column=4, rowspan=4, padx=20, pady=5)
    
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
        stats_text = (
            f"Memes: {self.stats['memes_processed']} processed | "
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
        self.discarded_folder = self.sorted_dir / ".discarded"
        
        for folder in [self.bo_folder, self.gau_folder, self.others_folder, self.discarded_folder]:
            folder.mkdir(parents=True, exist_ok=True)
        
        # Load metadata
        self.metadata_file = self.sorted_dir / "sorting_metadata.json"
        self.load_metadata()
    
    def load_metadata(self):
        """Load existing metadata"""
        if self.metadata_file.exists():
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
        
        # Start checking for characters
        self.root.after(100, self.check_for_characters)
    
    def run_pipeline(self):
        """Run the download and segmentation pipeline"""
        try:
            start_id = int(self.start_id_var.get())
            count = int(self.count_var.get())
            delay = float(self.delay_var.get())
            
            # Initialize components
            self.update_progress("Initializing scraper...")
            self.scraper = MemeScraper(download_dir=str(self.download_dir))
            
            self.update_progress("Loading SAM3 model...")
            self.segmenter = CharacterSegmenter(output_dir="temp_crops")
            
            # Process each meme
            for meme_id in range(start_id, start_id + count):
                if not self.is_running:
                    break
                
                self.current_meme_id = meme_id
                self.update_progress(f"Downloading meme {meme_id}...")
                
                # Download
                result = self.scraper.download_meme(meme_id, force=False)
                
                if result == 'skipped':
                    self.stats['memes_skipped'] += 1
                    continue
                elif result is None:
                    continue
                
                self.stats['memes_downloaded'] += 1
                
                # Segment
                self.update_progress(f"Segmenting characters from meme {meme_id}...")
                image = Image.open(result).convert("RGB")
                
                try:
                    masks_data = self.segmenter.segment_automatic(image)
                    
                    if not masks_data:
                        self.update_progress(f"No characters found in meme {meme_id}")
                        self.stats['memes_processed'] += 1
                        continue
                    
                    # Add characters to queue for sorting
                    width, height = image.size
                    for idx, (mask, bbox, score) in enumerate(masks_data):
                        x, y, box_w, box_h = bbox
                        
                        # Add padding
                        padding = 10
                        x_min = max(0, x - padding)
                        y_min = max(0, y - padding)
                        x_max = min(width, x + box_w + padding)
                        y_max = min(height, y + box_h + padding)
                        
                        # Crop
                        cropped = image.crop((x_min, y_min, x_max, y_max))
                        
                        # Add to queue
                        self.character_queue.put({
                            'image': cropped,
                            'meme_id': meme_id,
                            'char_idx': idx,
                            'score': score
                        })
                    
                    self.update_progress(f"Found {len(masks_data)} characters in meme {meme_id}. Sorting...")
                    self.stats['memes_processed'] += 1
                    
                except Exception as e:
                    self.update_progress(f"Error segmenting meme {meme_id}: {e}")
                
                # Delay before next
                if meme_id < start_id + count - 1:
                    import time
                    time.sleep(delay)
            
            # Cleanup
            if self.scraper:
                self.scraper.cleanup()
            
            # Signal completion
            self.character_queue.put(None)
            
        except Exception as e:
            messagebox.showerror("Pipeline Error", f"An error occurred: {e}")
            self.stop_pipeline()
    
    def check_for_characters(self):
        """Check queue for new characters to sort"""
        if not self.is_running:
            return
        
        try:
            # Check if there's a character in queue
            if not self.character_queue.empty():
                character = self.character_queue.get_nowait()
                
                if character is None:
                    # Pipeline complete
                    self.show_completion()
                    return
                
                self.current_character = character
                self.show_character()
        except queue.Empty:
            pass
        
        # Check again in 100ms
        self.root.after(100, self.check_for_characters)
    
    def show_character(self):
        """Display current character for sorting"""
        if not self.current_character:
            return
        
        char = self.current_character
        
        # Update info
        self.info_label.config(
            text=f"Meme {char['meme_id']} - Character {char['char_idx'] + 1} | Score: {char['score']:.3f}"
        )
        
        # Display image
        img = char['image']
        
        # Resize to fit
        max_size = (700, 500)
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        photo = ImageTk.PhotoImage(img)
        self.image_label.config(image=photo)
        self.image_label.image = photo
        
        self.update_stats_display()
    
    def sort_character(self, category):
        """Sort current character into category"""
        if not self.current_character:
            return
        
        char = self.current_character
        
        # Determine destination
        folder_map = {
            'Bo': self.bo_folder,
            'Gau': self.gau_folder,
            'Others': self.others_folder,
            'Discarded': self.discarded_folder
        }
        destination = folder_map[category]
        
        # Save image
        filename = f"meme_{char['meme_id']}_char_{char['char_idx']:02d}.png"
        dest_path = destination / filename
        
        # Handle duplicates
        if dest_path.exists():
            counter = 1
            stem = dest_path.stem
            while dest_path.exists():
                dest_path = destination / f"{stem}_{counter}.png"
                counter += 1
        
        char['image'].save(dest_path)
        
        # Update metadata
        if 'sorted_images' not in self.metadata:
            self.metadata['sorted_images'] = {}
        
        self.metadata['sorted_images'][str(dest_path)] = {
            'meme_id': char['meme_id'],
            'char_idx': char['char_idx'],
            'category': category,
            'score': char['score']
        }
        self.save_metadata()
        
        # Update stats
        self.stats[category] += 1
        
        # Add to history
        self.history.append({
            'character': char,
            'destination': dest_path,
            'category': category
        })
        
        # Clear current and wait for next
        self.current_character = None
        self.info_label.config(text="Waiting for next character...")
        self.image_label.config(image='')
        self.update_stats_display()
    
    def undo_action(self):
        """Undo last sorting action"""
        if not self.history:
            messagebox.showwarning("Undo", "Nothing to undo!")
            return
        
        last = self.history.pop()
        dest_path = last['destination']
        category = last['category']
        
        # Delete file
        if dest_path.exists():
            dest_path.unlink()
        
        # Update metadata
        if str(dest_path) in self.metadata.get('sorted_images', {}):
            del self.metadata['sorted_images'][str(dest_path)]
            self.save_metadata()
        
        # Update stats
        self.stats[category] -= 1
        
        # Put character back in front
        self.current_character = last['character']
        self.show_character()
        
        messagebox.showinfo("Undo", "Last action undone!")
    
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
        
        # Show summary
        summary = (
            f"Pipeline Complete!\n\n"
            f"Memes processed: {self.stats['memes_processed']}\n"
            f"Memes downloaded: {self.stats['memes_downloaded']}\n"
            f"Memes skipped: {self.stats['memes_skipped']}\n\n"
            f"Characters sorted:\n"
            f"  Bo: {self.stats['Bo']}\n"
            f"  Gau: {self.stats['Gau']}\n"
            f"  Others: {self.stats['Others']}\n"
            f"  Discarded: {self.stats['Discarded']}\n\n"
            f"Total: {sum([self.stats[k] for k in ['Bo', 'Gau', 'Others', 'Discarded']])}"
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