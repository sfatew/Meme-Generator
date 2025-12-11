"""
character_sorter.py - Sort character images using keyboard navigation
"""
import os
import json
import shutil
from pathlib import Path
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import messagebox, font as tkfont

class CharacterSorter:
    def __init__(self, crops_dir="character_crops", output_dir="sorted_characters"):
        """
        Initialize the character sorter
        
        Args:
            crops_dir: Directory containing cropped character images
            output_dir: Base directory for sorted images
        """
        self.crops_dir = Path(crops_dir)
        self.output_dir = Path(output_dir)
        
        # Create output folders
        self.bo_folder = self.output_dir / "Bo"
        self.gau_folder = self.output_dir / "Gau"
        self.others_folder = self.output_dir / "Others"
        self.discarded_folder = self.output_dir / ".discarded"  # Hidden folder
        
        for folder in [self.bo_folder, self.gau_folder, self.others_folder, self.discarded_folder]:
            folder.mkdir(parents=True, exist_ok=True)
        
        # Load metadata
        self.metadata_file = self.output_dir / "sorting_metadata.json"
        self.metadata = self.load_metadata()
        
        # Get list of images to sort
        self.image_files = self.get_unsorted_images()
        self.current_index = 0
        
        # History for undo
        self.history = []
        
        # Statistics
        self.stats = {
            'Bo': 0,
            'Gau': 0,
            'Others': 0,
            'Discarded': 0
        }
        
        # Load existing stats from metadata
        self.load_stats()
        
        # UI components
        self.root = None
        self.image_label = None
        self.info_label = None
        self.stats_label = None
        self.current_image = None
    
    def load_metadata(self):
        """Load existing metadata or create new"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'sorted_images': {}, 'session_stats': {}}
    
    def save_metadata(self):
        """Save metadata to file"""
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f, indent=2, ensure_ascii=False)
    
    def load_stats(self):
        """Load statistics from metadata"""
        for category, count in self.metadata.get('session_stats', {}).items():
            if category in self.stats:
                self.stats[category] = count
    
    def save_stats(self):
        """Save statistics to metadata"""
        self.metadata['session_stats'] = self.stats
        self.save_metadata()
    
    def get_unsorted_images(self):
        """Get list of images that haven't been sorted yet"""
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        
        all_images = [
            p for p in self.crops_dir.iterdir()
            if p.suffix.lower() in image_extensions
        ]
        
        # Filter out already sorted images
        unsorted = [
            img for img in all_images
            if str(img) not in self.metadata.get('sorted_images', {})
        ]
        
        return sorted(unsorted)
    
    def move_image(self, image_path, destination_folder, category):
        """
        Move image to destination folder
        
        Args:
            image_path: Path to source image
            destination_folder: Destination folder path
            category: Category name for metadata
        """
        dest_path = destination_folder / image_path.name
        
        # Handle duplicate names
        if dest_path.exists():
            stem = dest_path.stem
            suffix = dest_path.suffix
            counter = 1
            while dest_path.exists():
                dest_path = destination_folder / f"{stem}_{counter}{suffix}"
                counter += 1
        
        # Move the file
        shutil.move(str(image_path), str(dest_path))
        
        # Update metadata
        self.metadata['sorted_images'][str(image_path)] = {
            'category': category,
            'destination': str(dest_path)
        }
        self.save_metadata()
        
        # Update stats
        self.stats[category] += 1
        self.save_stats()
        
        return dest_path
    
    def undo_last_action(self):
        """Undo the last sorting action"""
        if not self.history:
            return False
        
        last_action = self.history.pop()
        source_path = Path(last_action['source'])
        dest_path = Path(last_action['destination'])
        category = last_action['category']
        
        # Move file back
        if dest_path.exists():
            shutil.move(str(dest_path), str(source_path))
            
            # Remove from metadata
            if str(source_path) in self.metadata['sorted_images']:
                del self.metadata['sorted_images'][str(source_path)]
                self.save_metadata()
            
            # Update stats
            self.stats[category] -= 1
            self.save_stats()
            
            # Add back to image list
            self.image_files.insert(self.current_index, source_path)
            
            return True
        
        return False
    
    def sort_image(self, category):
        """
        Sort current image into a category
        
        Args:
            category: 'Bo', 'Gau', 'Others', or 'Discarded'
        """
        if self.current_index >= len(self.image_files):
            return
        
        current_image_path = self.image_files[self.current_index]
        
        # Determine destination folder
        folder_map = {
            'Bo': self.bo_folder,
            'Gau': self.gau_folder,
            'Others': self.others_folder,
            'Discarded': self.discarded_folder
        }
        
        destination_folder = folder_map[category]
        
        # Move image
        dest_path = self.move_image(current_image_path, destination_folder, category)
        
        # Add to history for undo
        self.history.append({
            'source': str(current_image_path),
            'destination': str(dest_path),
            'category': category
        })
        
        # Move to next image
        self.current_index += 1
        
        # Update display
        self.show_current_image()
    
    def create_ui(self):
        """Create the sorting UI"""
        self.root = tk.Tk()
        self.root.title("Character Sorter")
        self.root.geometry("1000x800")
        self.root.configure(bg='#2b2b2b')
        
        # Title
        title_font = tkfont.Font(family="Arial", size=20, weight="bold")
        title = tk.Label(
            self.root, 
            text="Character Sorter", 
            font=title_font,
            bg='#2b2b2b',
            fg='#ffffff'
        )
        title.pack(pady=10)
        
        # Info label
        info_font = tkfont.Font(family="Arial", size=12)
        self.info_label = tk.Label(
            self.root,
            text="",
            font=info_font,
            bg='#2b2b2b',
            fg='#cccccc'
        )
        self.info_label.pack(pady=5)
        
        # Image display area
        image_frame = tk.Frame(self.root, bg='#1a1a1a', relief=tk.SUNKEN, borderwidth=2)
        image_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        self.image_label = tk.Label(image_frame, bg='#1a1a1a')
        self.image_label.pack(expand=True)
        
        # Controls instructions
        controls_frame = tk.Frame(self.root, bg='#2b2b2b')
        controls_frame.pack(pady=10)
        
        control_font = tkfont.Font(family="Arial", size=11, weight="bold")
        controls = [
            ("← Left Arrow", "Bo", "#4CAF50"),
            ("→ Right Arrow", "Gau", "#2196F3"),
            ("↑ Up Arrow", "Others", "#FF9800"),
            ("↓ Down Arrow", "Discard", "#f44336"),
            ("Backspace", "Undo", "#9E9E9E")
        ]
        
        for key, action, color in controls:
            frame = tk.Frame(controls_frame, bg='#2b2b2b')
            frame.pack(side=tk.LEFT, padx=10)
            
            tk.Label(
                frame,
                text=key,
                font=control_font,
                bg='#2b2b2b',
                fg=color
            ).pack()
            
            tk.Label(
                frame,
                text=action,
                font=("Arial", 9),
                bg='#2b2b2b',
                fg='#cccccc'
            ).pack()
        
        # Statistics
        self.stats_label = tk.Label(
            self.root,
            text="",
            font=("Arial", 10),
            bg='#2b2b2b',
            fg='#aaaaaa',
            justify=tk.LEFT
        )
        self.stats_label.pack(pady=10)
        
        # Bind keyboard events
        self.root.bind('<Left>', lambda e: self.sort_image('Bo'))
        self.root.bind('<Right>', lambda e: self.sort_image('Gau'))
        self.root.bind('<Up>', lambda e: self.sort_image('Others'))
        self.root.bind('<Down>', lambda e: self.sort_image('Discarded'))
        self.root.bind('<BackSpace>', lambda e: self.undo_action())
        self.root.bind('<Escape>', lambda e: self.quit_application())
        
        # Show first image
        self.show_current_image()
    
    def show_current_image(self):
        """Display the current image"""
        if self.current_index >= len(self.image_files):
            self.show_completion()
            return
        
        # Update info
        remaining = len(self.image_files) - self.current_index
        total = len(self.image_files)
        progress = self.current_index
        
        self.info_label.config(
            text=f"Image {progress + 1} of {total} | {remaining} remaining"
        )
        
        # Load and display image
        image_path = self.image_files[self.current_index]
        
        try:
            # Load image
            img = Image.open(image_path)
            
            # Resize to fit screen while maintaining aspect ratio
            max_size = (800, 600)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(img)
            
            # Update label
            self.image_label.config(image=photo)
            self.image_label.image = photo  # Keep a reference
            
        except Exception as e:
            self.image_label.config(text=f"Error loading image: {e}", fg='#ff0000')
        
        # Update statistics
        self.update_stats_display()
    
    def update_stats_display(self):
        """Update statistics display"""
        stats_text = (
            f"Bo: {self.stats['Bo']} | "
            f"Gau: {self.stats['Gau']} | "
            f"Others: {self.stats['Others']} | "
            f"Discarded: {self.stats['Discarded']}"
        )
        self.stats_label.config(text=stats_text)
    
    def undo_action(self):
        """Undo last action"""
        if self.undo_last_action():
            self.current_index -= 1
            self.show_current_image()
            messagebox.showinfo("Undo", "Last action undone!")
        else:
            messagebox.showwarning("Undo", "Nothing to undo!")
    
    def show_completion(self):
        """Show completion message"""
        self.image_label.config(
            text="🎉 All images sorted!",
            font=("Arial", 24, "bold"),
            fg='#4CAF50'
        )
        
        self.info_label.config(text="Press ESC to exit")
        
        # Show final statistics
        stats_text = (
            f"\n\nFinal Statistics:\n"
            f"Bo: {self.stats['Bo']}\n"
            f"Gau: {self.stats['Gau']}\n"
            f"Others: {self.stats['Others']}\n"
            f"Discarded: {self.stats['Discarded']}\n"
            f"\nTotal sorted: {sum(self.stats.values())}"
        )
        
        messagebox.showinfo("Sorting Complete", stats_text)
    
    def quit_application(self):
        """Quit the application"""
        if messagebox.askyesno("Quit", "Are you sure you want to quit?"):
            self.root.quit()
    
    def run(self):
        """Run the sorter application"""
        if not self.image_files:
            print("No unsorted images found!")
            print(f"Looking in: {self.crops_dir}")
            print(f"Already sorted: {len(self.metadata.get('sorted_images', {}))}")
            return
        
        print(f"\n{'='*60}")
        print("CHARACTER SORTER")
        print(f"{'='*60}")
        print(f"Images to sort: {len(self.image_files)}")
        print(f"Already sorted: {len(self.metadata.get('sorted_images', {}))}")
        print(f"\nOutput folders:")
        print(f"  Bo: {self.bo_folder}")
        print(f"  Gau: {self.gau_folder}")
        print(f"  Others: {self.others_folder}")
        print(f"  Discarded: {self.discarded_folder}")
        print(f"\nControls:")
        print(f"  ← Left Arrow:  Sort to 'Bo'")
        print(f"  → Right Arrow: Sort to 'Gau'")
        print(f"  ↑ Up Arrow:    Sort to 'Others'")
        print(f"  ↓ Down Arrow:  Discard")
        print(f"  Backspace:     Undo last action")
        print(f"  ESC:           Quit")
        print(f"{'='*60}\n")
        
        # Create and run UI
        self.create_ui()
        self.root.mainloop()
        
        # Final summary
        print(f"\n{'='*60}")
        print("SORTING SESSION COMPLETE")
        print(f"{'='*60}")
        print(f"Bo: {self.stats['Bo']}")
        print(f"Gau: {self.stats['Gau']}")
        print(f"Others: {self.stats['Others']}")
        print(f"Discarded: {self.stats['Discarded']}")
        print(f"Total: {sum(self.stats.values())}")
        print(f"{'='*60}")


# # Example usage
# if __name__ == "__main__":
#     sorter = CharacterSorter(
#         crops_dir="character_crops",
#         output_dir="sorted_characters"
#     )
#     sorter.run()