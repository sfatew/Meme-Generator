"""
meme_scraper.py - Download memes from bovagau.vn (Fixed version)
"""
import os
import time
import json
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from datetime import datetime

class MemeScraper:
    def __init__(self, download_dir="meme_downloads"):
        """
        Initialize the meme scraper
        
        Args:
            download_dir: Directory to store downloaded images
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        
        # Create metadata file
        self.metadata_file = self.download_dir / "metadata.json"
        self.metadata = self.load_metadata()
        
        # Setup Selenium with Edge
        self.driver = None
        self.setup_selenium()
    
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
    
    def setup_selenium(self):
        """Configure Selenium WebDriver with Edge and download preferences"""
        edge_options = Options()
        edge_options.add_argument('--headless')  # Run in background
        edge_options.add_argument('--no-sandbox')
        edge_options.add_argument('--disable-dev-shm-usage')
        edge_options.add_argument('--disable-blink-features=AutomationControlled')
        
        # Set download directory
        prefs = {
            "download.default_directory": str(self.download_dir.absolute()),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        edge_options.add_experimental_option("prefs", prefs)
        edge_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        edge_options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = webdriver.Edge(options=edge_options)
        print("✓ Edge WebDriver initialized")
    
    def page_has_download_button(self):
        """
        Check if the current page has a download button
        
        Returns:
            True if download button exists, False otherwise
        """
        try:
            # Try to find the download button with a short timeout
            self.driver.find_element(By.CLASS_NAME, "download-meme")
            return True
        except NoSuchElementException:
            return False
    
    def download_meme(self, meme_id, force=False):
        """
        Download meme image from bovagau.vn
        
        Args:
            meme_id: The ID number of the meme
            force: Force download even if already exists
            
        Returns:
            Path to downloaded image, None if failed, or 'skipped' if no image
        """
        # Check if already downloaded
        if not force and str(meme_id) in self.metadata:
            metadata_entry = self.metadata[str(meme_id)]
            path_value = metadata_entry.get('path')
            
            # Only try to use existing path if it's not None and status is success
            if path_value and metadata_entry.get('status') == 'success':
                existing_path = Path(path_value)
                if existing_path.exists():
                    print(f"⊙ Meme {meme_id} already downloaded: {existing_path}")
                    return existing_path
            elif metadata_entry.get('status') == 'skipped':
                print(f"⊙ Meme {meme_id} previously skipped (no image)")
                return 'skipped'
        
        url = f"https://bovagau.vn/meme/{meme_id}"
        print(f"\nAccessing meme ID: {meme_id}")
        print(f"URL: {url}")
        
        try:
            self.driver.get(url)
            
            # Wait a bit for page to load
            time.sleep(1)
            
            # Check if download button exists
            if not self.page_has_download_button():
                print(f"⊘ No image/download button found for meme {meme_id} - Skipping")
                
                # Save to metadata as skipped
                self.metadata[str(meme_id)] = {
                    'path': None,
                    'url': url,
                    'status': 'skipped',
                    'reason': 'no_download_button',
                    'checked_at': datetime.now().isoformat()
                }
                self.save_metadata()
                
                return 'skipped'
            
            # Wait for the download button to be clickable
            wait = WebDriverWait(self.driver, 10)
            download_button = wait.until(
                EC.element_to_be_clickable((By.CLASS_NAME, "download-meme"))
            )
            
            # Get list of files before download
            before_files = set(self.download_dir.glob("*"))
            
            # Click download button (with fallback)
            try:
                # 1. Scroll element to center to avoid headers/tabs covering it
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", download_button)
                time.sleep(0.5) # Allow scroll to settle
                
                download_button.click()
                print("✓ Clicked download button")
            except (ElementClickInterceptedException, Exception):
                # 2. If standard click is still intercepted, FORCE it with JavaScript
                print("! Standard click intercepted, forcing with JS...")
                self.driver.execute_script("arguments[0].click();", download_button)
                print("✓ Clicked download button (via JS)")
            
            # Wait for download to complete (check for new file)
            timeout = 30
            start_time = time.time()
            new_file = None
            
            while time.time() - start_time < timeout:
                current_files = set(self.download_dir.glob("*"))
                new_files = current_files - before_files
                
                # Filter out partial downloads and metadata
                complete_files = [
                    f for f in new_files 
                    if not str(f).endswith(('.crdownload', '.tmp', '.json'))
                ]
                
                if complete_files:
                    new_file = complete_files[0]
                    break
                
                time.sleep(0.5)
            
            if new_file:
                # Rename with meme ID
                extension = new_file.suffix if new_file.suffix else '.jpg'
                new_name = self.download_dir / f"meme_{meme_id}{extension}"
                
                # Remove if exists
                if new_name.exists():
                    new_name.unlink()
                
                new_file.rename(new_name)
                
                # Save metadata
                self.metadata[str(meme_id)] = {
                    'path': str(new_name),
                    'url': url,
                    'status': 'success',
                    'downloaded_at': datetime.now().isoformat(),
                    'file_size': os.path.getsize(new_name)
                }
                self.save_metadata()
                
                print(f"✓ Downloaded: {new_name}")
                return new_name
            else:
                print(f"✗ Download timeout for meme {meme_id}")
                
                # Save to metadata as failed
                self.metadata[str(meme_id)] = {
                    'path': None,
                    'url': url,
                    'status': 'failed',
                    'reason': 'download_timeout',
                    'checked_at': datetime.now().isoformat()
                }
                self.save_metadata()
                
                return None
        
        except TimeoutException:
            print(f"⊘ Timeout waiting for page/button for meme {meme_id} - Skipping")
            
            # Save to metadata as skipped
            self.metadata[str(meme_id)] = {
                'path': None,
                'url': url,
                'status': 'skipped',
                'reason': 'page_timeout',
                'checked_at': datetime.now().isoformat()
            }
            self.save_metadata()
            
            return 'skipped'
                
        except Exception as e:
            print(f"✗ Error downloading meme {meme_id}: {e}")
            
            # Save to metadata as error
            self.metadata[str(meme_id)] = {
                'path': None,
                'url': url,
                'status': 'error',
                'reason': str(e),
                'checked_at': datetime.now().isoformat()
            }
            self.save_metadata()
            
            return None
    
    def download_batch(self, start_id=0, count=10, delay=2, force=False):
        """
        Download multiple memes in batch
        
        Args:
            start_id: Starting meme ID
            count: Number of memes to download
            delay: Delay between downloads (seconds)
            force: Force re-download of existing memes
            
        Returns:
            Dictionary mapping meme_id to file path (only successful downloads)
        """
        print(f"\n{'='*60}")
        print(f"Downloading {count} memes starting from ID {start_id}")
        print(f"{'='*60}")
        
        results = {}
        success_count = 0
        skip_count = 0
        fail_count = 0
        no_image_count = 0
        
        for meme_id in range(start_id, start_id + count):
            result = self.download_meme(meme_id, force=force)
            
            if result == 'skipped':
                no_image_count += 1
            elif result is None:
                fail_count += 1
            elif isinstance(result, Path):
                results[meme_id] = str(result)
                if str(meme_id) in self.metadata and not force:
                    skip_count += 1
                else:
                    success_count += 1
            
            # Be polite to the server
            if meme_id < start_id + count - 1:
                time.sleep(delay)
        
        # Summary
        print(f"\n{'='*60}")
        print("DOWNLOAD SUMMARY")
        print(f"{'='*60}")
        print(f"Total requested: {count}")
        print(f"Successfully downloaded: {success_count}")
        print(f"Already existed: {skip_count}")
        print(f"No image/button (skipped): {no_image_count}")
        print(f"Failed (errors): {fail_count}")
        print(f"Output directory: {self.download_dir}")
        print(f"Metadata file: {self.metadata_file}")
        
        return results
    
    def download_list(self, meme_ids, delay=2, force=False):
        """
        Download specific list of meme IDs
        
        Args:
            meme_ids: List of meme IDs to download
            delay: Delay between downloads (seconds)
            force: Force re-download of existing memes
            
        Returns:
            Dictionary mapping meme_id to file path
        """
        print(f"\n{'='*60}")
        print(f"Downloading {len(meme_ids)} specific memes")
        print(f"{'='*60}")
        
        results = {}
        success_count = 0
        skip_count = 0
        no_image_count = 0
        
        for i, meme_id in enumerate(meme_ids):
            result = self.download_meme(meme_id, force=force)
            
            if result == 'skipped':
                no_image_count += 1
            elif result and isinstance(result, Path):
                results[meme_id] = str(result)
                success_count += 1
            
            if i < len(meme_ids) - 1:
                time.sleep(delay)
        
        print(f"\nDownloaded: {success_count}, No image: {no_image_count}")
        
        return results
    
    def get_downloaded_memes(self):
        """Get list of successfully downloaded meme IDs"""
        return [
            int(mid) for mid, data in self.metadata.items() 
            if data.get('status') == 'success'
        ]
    
    def get_skipped_memes(self):
        """Get list of skipped meme IDs (no image)"""
        return [
            int(mid) for mid, data in self.metadata.items() 
            if data.get('status') == 'skipped'
        ]
    
    def cleanup(self):
        """Close Selenium driver"""
        if self.driver:
            self.driver.quit()
            print("\n✓ Cleaned up resources")