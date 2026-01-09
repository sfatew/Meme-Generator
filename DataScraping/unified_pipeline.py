"""
unified_pipeline_v2.py - With auto-captioning and tag management
Pipeline: download → segment to discard → sort → caption → manage tags
"""
import os
import json
import shutil
from pathlib import Path
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont, scrolledtext
from threading import Thread
from collections import Counter

from scraper import MemeScraper
from character_segment import CharacterSegmenter
from image_captioner import ImageCaptioner


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
        self.captioner = None
        
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
        self.images_to_sort = []
        self.current_index = 0
        self.current_image_path = None
        
        # Captioning state
        self.caption_results = {}
        self.tag_stats = Counter()
        self.selected_image_for_tags = None
        
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
        self.notebook = None
        self.config_frame = None
        self.progress_frame = None
        self.sorting_frame = None
        self.caption_frame = None
        self.image_label = None
        self.info_label = None
        self.stats_label = None
        self.progress_label = None
        self.start_button = None
    
    def create_ui(self):
        """Create the unified UI with tabs"""
        self.root = tk.Tk()
        self.root.title("Meme Character Pipeline")
        self.root.geometry("1200x950")
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
        
        # Create notebook for tabs
        style = ttk.Style()
        style.theme_use('default')
        style.configure('TNotebook', background='#2b2b2b')
        style.configure('TNotebook.Tab', background='#3c3c3c', foreground='#ffffff', padding=[20, 10])
        style.map('TNotebook.Tab', background=[('selected', '#4CAF50')])
        
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both', padx=20, pady=10)
        
        # Tab 1: Pipeline (Download & Sort)
        pipeline_tab = tk.Frame(self.notebook, bg='#2b2b2b')
        self.notebook.add(pipeline_tab, text='📥 Pipeline')
        self.create_pipeline_tab(pipeline_tab)
        
        # Tab 2: Captioning
        caption_tab = tk.Frame(self.notebook, bg='#2b2b2b')
        self.notebook.add(caption_tab, text='🏷️ Auto-Caption')
        self.create_caption_tab(caption_tab)
        
        # Bind keyboard events
        self.root.bind('<Left>', lambda e: self.sort_character('Bo') if self.is_running else None)
        self.root.bind('<Right>', lambda e: self.sort_character('Gau') if self.is_running else None)
        self.root.bind('<Up>', lambda e: self.sort_character('Others') if self.is_running else None)
        self.root.bind('<Down>', lambda e: self.sort_character('Discarded') if self.is_running else None)
        self.root.bind('<BackSpace>', lambda e: self.undo_action() if self.is_running else None)
        self.root.bind('<Escape>', lambda e: self.stop_pipeline())
    
    def create_pipeline_tab(self, parent):
        """Create the pipeline tab (original functionality)"""
        # Configuration Frame
        self.create_config_frame(parent)
        
        # Progress Frame
        self.create_progress_frame(parent)
        
        # Sorting Frame
        self.create_sorting_frame(parent)
    
    def create_caption_tab(self, parent):
        """Create the captioning and tag management tab"""
        # Top frame: Controls
        control_frame = tk.Frame(parent, bg='#2b2b2b')
        control_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Caption button
        self.caption_button = tk.Button(
            control_frame,
            text="🏷️ Generate Captions (Bo + Gau)",
            command=self.start_captioning,
            font=("Arial", 12, "bold"),
            bg='#2196F3',
            fg='white',
            relief=tk.RAISED,
            borderwidth=3,
            padx=20,
            pady=10,
            cursor="hand2"
        )
        self.caption_button.pack(side=tk.LEFT, padx=5)
        
        # Refresh stats button
        refresh_btn = tk.Button(
            control_frame,
            text="🔄 Refresh Stats",
            command=self.refresh_tag_stats,
            font=("Arial", 11),
            bg='#FF9800',
            fg='white',
            relief=tk.RAISED,
            borderwidth=2,
            padx=15,
            pady=8,
            cursor="hand2"
        )
        refresh_btn.pack(side=tk.LEFT, padx=5)
        
        # Main content: Split view
        content_frame = tk.Frame(parent, bg='#2b2b2b')
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Left: Tag statistics
        left_frame = tk.LabelFrame(
            content_frame,
            text="Tag Statistics",
            font=("Arial", 12, "bold"),
            bg='#2b2b2b',
            fg='#ffffff',
            relief=tk.RIDGE,
            borderwidth=2
        )
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Search/filter
        search_frame = tk.Frame(left_frame, bg='#2b2b2b')
        search_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(search_frame, text="Filter:", bg='#2b2b2b', fg='#cccccc').pack(side=tk.LEFT)
        self.tag_filter_var = tk.StringVar()
        self.tag_filter_var.trace('w', lambda *args: self.filter_tags())
        filter_entry = tk.Entry(search_frame, textvariable=self.tag_filter_var, width=20)
        filter_entry.pack(side=tk.LEFT, padx=5)
        
        # Tag list with scrollbar
        list_frame = tk.Frame(left_frame, bg='#2b2b2b')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tag_listbox = tk.Listbox(
            list_frame,
            font=("Courier", 10),
            bg='#1a1a1a',
            fg='#ffffff',
            selectmode=tk.SINGLE,
            yscrollcommand=scrollbar.set,
            height=20
        )
        self.tag_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.tag_listbox.yview)
        
        self.tag_listbox.bind('<<ListboxSelect>>', self.on_tag_select)
        
        # Remove tag button
        remove_btn = tk.Button(
            left_frame,
            text="❌ Remove Selected Tag from All Images",
            command=self.remove_selected_tag,
            font=("Arial", 10, "bold"),
            bg='#f44336',
            fg='white',
            relief=tk.RAISED,
            borderwidth=2,
            padx=10,
            pady=5,
            cursor="hand2"
        )
        remove_btn.pack(pady=10)
        
        # Right: Image browser
        right_frame = tk.LabelFrame(
            content_frame,
            text="Image Tags Viewer",
            font=("Arial", 12, "bold"),
            bg='#2b2b2b',
            fg='#ffffff',
            relief=tk.RIDGE,
            borderwidth=2
        )
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Directory selector
        dir_frame = tk.Frame(right_frame, bg='#2b2b2b')
        dir_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(dir_frame, text="View:", bg='#2b2b2b', fg='#cccccc').pack(side=tk.LEFT)
        
        self.view_dir_var = tk.StringVar(value="Bo")
        for dirname in ["Bo", "Gau"]:
            tk.Radiobutton(
                dir_frame,
                text=dirname,
                variable=self.view_dir_var,
                value=dirname,
                bg='#2b2b2b',
                fg='#ffffff',
                selectcolor='#3c3c3c',
                command=self.load_images_for_viewer
            ).pack(side=tk.LEFT, padx=5)
        
        # Image list
        image_list_frame = tk.Frame(right_frame, bg='#2b2b2b')
        image_list_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(image_list_frame, text="Images:", bg='#2b2b2b', fg='#cccccc').pack(side=tk.LEFT)
        
        self.image_combo = ttk.Combobox(image_list_frame, state='readonly', width=30)
        self.image_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.image_combo.bind('<<ComboboxSelected>>', self.on_image_select)
        
        # Image preview
        preview_frame = tk.Frame(right_frame, bg='#1a1a1a', relief=tk.SUNKEN, borderwidth=2)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.preview_label = tk.Label(preview_frame, bg='#1a1a1a', fg='#888888', text="Select an image")
        self.preview_label.pack(expand=True)
        
        # Tags display
        tags_display_frame = tk.Frame(right_frame, bg='#2b2b2b')
        tags_display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        tk.Label(
            tags_display_frame,
            text="Tags:",
            font=("Arial", 10, "bold"),
            bg='#2b2b2b',
            fg='#cccccc'
        ).pack(anchor=tk.W)
        
        self.tags_text = scrolledtext.ScrolledText(
            tags_display_frame,
            font=("Arial", 10),
            bg='#1a1a1a',
            fg='#ffffff',
            height=8,
            wrap=tk.WORD
        )
        self.tags_text.pack(fill=tk.BOTH, expand=True)
    
    def create_config_frame(self, parent):
        """Create configuration input frame"""
        self.config_frame = tk.LabelFrame(
            parent,
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
    
    def create_progress_frame(self, parent):
        """Create progress tracking frame"""
        self.progress_frame = tk.LabelFrame(
            parent,
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
    
    def create_sorting_frame(self, parent):
        """Create character sorting frame"""
        self.sorting_frame = tk.LabelFrame(
            parent,
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
            
            # Phase 1: Download
            self.update_progress("Downloading memes in batch...")
            self.scraper = MemeScraper(download_dir=str(self.download_dir))
            
            downloaded_results = self.scraper.download_batch(
                start_id=start_id,
                count=count,
                delay=delay,
                force=False
            )
            
            # Update stats
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
            
            # Phase 2: Segment
            self.update_progress("Loading SAM3 model...")
            hf_token = self.hf_token_var.get().strip() or None
            self.segmenter = CharacterSegmenter(
                output_dir=str(self.discarded_folder), 
                hf_token=hf_token
            )
            
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
            
            # Phase 3: Load for sorting
            self.update_progress("Loading characters for sorting...")
            self.load_images_from_discard()
            
            self.stats['total_characters'] = total_characters
            
            # Start sorting
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
        
        for img_path in sorted(self.discarded_folder.glob("*.png")):
            if 'sorted_images' in self.metadata:
                already_sorted = False
                for sorted_path, info in self.metadata['sorted_images'].items():
                    sorted_path_obj = Path(sorted_path)
                    if sorted_path_obj.name == img_path.name:
                        if sorted_path_obj.parent != self.discarded_folder:
                            already_sorted = True
                            break
                
                if already_sorted:
                    continue
            
            self.images_to_sort.append(img_path)
        
        self.current_index = 0
        print(f"Loaded {len(self.images_to_sort)} images for sorting")
    
    def show_next_character(self):
        """Show next character"""
        if not self.is_running:
            return
        
        if self.current_index >= len(self.images_to_sort):
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
            
            max_size = (700, 400)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            photo = ImageTk.PhotoImage(img)
            self.image_label.config(image=photo)
            self.image_label.image = photo
        except Exception as e:
            print(f"Error loading image {self.current_image_path}: {e}")
            self.current_index += 1
            self.root.after(100, self.show_next_character)
            return
        
        self.update_stats_display()
    
    def sort_character(self, category):
        """Sort current character into category"""
        if not self.current_image_path or not self.current_image_path.exists():
            return
        
        folder_map = {
            'Bo': self.bo_folder,
            'Gau': self.gau_folder,
            'Others': self.others_folder,
            'Discarded': self.discarded_folder
        }
        destination = folder_map[category]
        
        if category == 'Discarded':
            if 'sorted_images' not in self.metadata:
                self.metadata['sorted_images'] = {}
            
            self.metadata['sorted_images'][str(self.current_image_path)] = {
                'category': 'Discarded',
                'original_path': str(self.current_image_path)
            }
            self.save_metadata()
            
            self.stats['Discarded'] += 1
            
            self.history.append({
                'source': self.current_image_path,
                'destination': self.current_image_path,
                'category': category,
                'action': 'keep'
            })
        else:
            dest_path = destination / self.current_image_path.name
            
            if dest_path.exists():
                counter = 1
                stem = dest_path.stem
                suffix = dest_path.suffix
                while dest_path.exists():
                    dest_path = destination / f"{stem}_{counter}{suffix}"
                    counter += 1
            
            shutil.move(str(self.current_image_path), str(dest_path))
            
            if 'sorted_images' not in self.metadata:
                self.metadata['sorted_images'] = {}
            
            self.metadata['sorted_images'][str(dest_path)] = {
                'category': category,
                'original_path': str(self.current_image_path)
            }
            self.save_metadata()
            
            self.stats[category] += 1
            
            self.history.append({
                'source': self.current_image_path,
                'destination': dest_path,
                'category': category,
                'action': 'move'
            })
        
        self.current_index += 1
        self.update_stats_display()
        
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
            if destination.exists():
                shutil.move(str(destination), str(source))
            
            if str(destination) in self.metadata.get('sorted_images', {}):
                del self.metadata['sorted_images'][str(destination)]
                self.save_metadata()
        else:
            if str(source) in self.metadata.get('sorted_images', {}):
                del self.metadata['sorted_images'][str(source)]
                self.save_metadata()
        
        self.stats[category] -= 1
        
        self.current_index = max(0, self.current_index - 1)
        
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
        
        remaining_in_discard = 0
        for img_path in self.discarded_folder.glob("*.png"):
            if str(img_path) not in self.metadata.get('sorted_images', {}):
                remaining_in_discard += 1
        
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
    
    # Captioning functions
    def start_captioning(self):
        """Start the captioning process in background"""
        self.setup_directories()
        
        # Disable button
        self.caption_button.config(state=tk.DISABLED, text="Generating...", bg='#757575')
        
        # Run in thread
        thread = Thread(target=self.run_captioning, daemon=True)
        thread.start()
    
    def run_captioning(self):
        """Run the captioning on Bo and Gau folders"""
        try:
            # Initialize captioner
            self.captioner = ImageCaptioner(threshold=0.35)
            
            # Caption Bo folder
            bo_results = self.captioner.caption_batch(self.bo_folder, pattern="*.png")
            
            # Caption Gau folder
            gau_results = self.captioner.caption_batch(self.gau_folder, pattern="*.png")
            
            # Combine results
            self.caption_results = {**bo_results, **gau_results}
            
            # Update statistics
            self.tag_stats = self.captioner.get_tag_statistics(self.caption_results)
            
            # Update UI
            self.root.after(0, self.update_caption_ui)
            
            messagebox.showinfo(
                "Captioning Complete",
                f"Successfully captioned {len(self.caption_results)} images!\n"
                f"Total unique tags: {len(self.tag_stats)}"
            )
            
        except Exception as e:
            messagebox.showerror("Captioning Error", f"An error occurred: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.caption_button.config(state=tk.NORMAL, text="🏷️ Generate Captions (Bo + Gau)", bg='#2196F3')
    
    def update_caption_ui(self):
        """Update the caption tab UI with results"""
        self.populate_tag_list()
        self.load_images_for_viewer()
    
    def populate_tag_list(self, filter_text=""):
        """Populate the tag listbox with statistics"""
        self.tag_listbox.delete(0, tk.END)
        
        if not self.tag_stats:
            self.tag_listbox.insert(tk.END, "No tags yet. Generate captions first.")
            return
        
        # Filter and sort
        filtered_tags = [
            (tag, count) for tag, count in self.tag_stats.most_common()
            if filter_text.lower() in tag.lower()
        ]
        
        # Add to listbox
        for tag, count in filtered_tags:
            display = f"{tag:<40} ({count:>3})"
            self.tag_listbox.insert(tk.END, display)
    
    def filter_tags(self):
        """Filter tags based on search input"""
        filter_text = self.tag_filter_var.get()
        self.populate_tag_list(filter_text)
    
    def on_tag_select(self, event):
        """Handle tag selection"""
        selection = self.tag_listbox.curselection()
        if not selection:
            return
        
        # Get selected tag
        item = self.tag_listbox.get(selection[0])
        tag = item.split('(')[0].strip()
        
        # Show images with this tag
        print(f"Selected tag: {tag}")
    
    def remove_selected_tag(self):
        """Remove the selected tag from all images"""
        selection = self.tag_listbox.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a tag to remove")
            return
        
        # Get selected tag
        item = self.tag_listbox.get(selection[0])
        tag = item.split('(')[0].strip()
        count = self.tag_stats[tag]
        
        # Confirm
        if not messagebox.askyesno(
            "Confirm Removal",
            f"Remove tag '{tag}' from all {count} images?"
        ):
            return
        
        # Remove from Bo folder
        modified_bo = self.captioner.remove_tag_from_all(tag, self.bo_folder)
        
        # Remove from Gau folder
        modified_gau = self.captioner.remove_tag_from_all(tag, self.gau_folder)
        
        total_modified = modified_bo + modified_gau
        
        # Refresh stats
        self.refresh_tag_stats()
        
        messagebox.showinfo(
            "Tag Removed",
            f"Removed tag '{tag}' from {total_modified} caption files"
        )
    
    def refresh_tag_stats(self):
        """Refresh tag statistics from caption files"""
        if not self.captioner:
            self.captioner = ImageCaptioner(threshold=0.35)
        
        self.caption_results = {}
        
        # Load from Bo
        for txt_file in self.bo_folder.glob("*.txt"):
            tags = self.captioner.load_caption_file(txt_file)
            img_path = txt_file.with_suffix('.png')
            if img_path.exists():
                self.caption_results[str(img_path)] = tags
        
        # Load from Gau
        for txt_file in self.gau_folder.glob("*.txt"):
            tags = self.captioner.load_caption_file(txt_file)
            img_path = txt_file.with_suffix('.png')
            if img_path.exists():
                self.caption_results[str(img_path)] = tags
        
        # Update stats
        self.tag_stats = self.captioner.get_tag_statistics(self.caption_results)
        
        # Update UI
        self.populate_tag_list()
    
    def load_images_for_viewer(self):
        """Load images for the viewer combobox"""
        dirname = self.view_dir_var.get()
        folder = self.bo_folder if dirname == "Bo" else self.gau_folder
        
        # Get all PNG files
        image_files = sorted([f.name for f in folder.glob("*.png")])
        
        self.image_combo['values'] = image_files
        
        if image_files:
            self.image_combo.current(0)
            self.on_image_select(None)
    
    def on_image_select(self, event):
        """Handle image selection in viewer"""
        if not self.image_combo.get():
            return
        
        dirname = self.view_dir_var.get()
        folder = self.bo_folder if dirname == "Bo" else self.gau_folder
        
        img_name = self.image_combo.get()
        img_path = folder / img_name
        
        if not img_path.exists():
            return
        
        # Load and display image
        try:
            img = Image.open(img_path)
            
            max_size = (300, 300)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            photo = ImageTk.PhotoImage(img)
            self.preview_label.config(image=photo, text="")
            self.preview_label.image = photo
        except Exception as e:
            print(f"Error loading preview: {e}")
        
        # Load and display tags
        if not self.captioner:
            self.captioner = ImageCaptioner(threshold=0.35)
        
        tags = self.captioner.get_image_tags(img_path)
        
        self.tags_text.delete('1.0', tk.END)
        if tags:
            self.tags_text.insert('1.0', ", ".join(tags))
        else:
            self.tags_text.insert('1.0', "No tags found. Generate captions first.")
    
    def run(self):
        """Run the application"""
        self.create_ui()
        self.root.mainloop()


if __name__ == "__main__":
    app = UnifiedPipeline()
    app.run()