#!/usr/bin/env python3
"""
EXIF Headliner - Automated Metadata Management Tool

This script processes image files and updates their EXIF/IPTC metadata based on 
directory structure patterns. It extracts year and headline information from 
folder names and applies metadata templates to ensure consistent tagging.

Author: Edmond Shapiro
Version: 1.0.2
Created: 5 September 2025
Last Modified: 8 September 2025

Dependencies:
    - exiftool (external command-line tool)
    - Python 3.6+ with standard library modules

Usage:
    python exif-headliner.py --directory "2007 Print Quality"
    python exif-headliner.py --current --debug

Version History:
    1.0.0 - Initial release
    1.0.1 - Bug fixes and stability improvements
    1.0.2 - Added version tracking and documentation headers
    1.0.3 - Added checkpoint file to prevent duplicate processing of directories
"""

__version__ = "1.0.3"
__author__ = "Edmond Shapiro"
__email__ = "eshapiro@gmail.com"
__license__ = "MIT"  
__status__ = "Production"  # Development/Beta/Production

import os
import re
import json
import argparse
import subprocess
import tempfile
from pathlib import Path

# --- FIXED ROOT DIRECTORY ---
ARCHIVE_ROOT = Path("/Volumes/photo/shapfam/")
#ARCHIVE_ROOT = Path("/Volumes/photo/shapfam-iptc-modify/")
TEMPLATE_FILE = "/Volumes/photo/other/tools/python/exif/exif-headliner/metadata_template.json"
CHECKPOINT_FILENAME = ".processed_marker"  # can add prefix/suffix if needed


def load_template(template_file):
    """Load JSON template containing desired metadata fields."""
    with open(template_file, "r", encoding="utf-8") as f:
        return json.load(f)

def extract_year_and_headline(file_path: Path, debug: bool = False):
    """
    Extract year and headline from directory structure.
    A more specific folder name (like 2006-01-01 Vail) overrides a less specific one (like 2006 Print).
    """
    parts = file_path.parts
    year, headline = None, None
    for p in parts:
        match = re.match(r"(\d{4})", p)
        if match:
            year = match.group(1)
    for p in parts:
        m = re.match(r"(\d{4})-\d{2}-\d{2}(?:[ _-]+(.+))?", p)
        if m:
            year = m.group(1)
            headline = m.group(2) if len(m.groups()) > 1 and m.group(2) else None
    for p in parts:
        m = re.match(r"(\d{4})[ _-]+(.+)", p)
        if m and not headline:
            year = m.group(1)
            headline = m.group(2)
    if not headline and len(parts) > 1:
        candidate_headline = parts[-2]
        if not re.match(r"^\d{4}$", candidate_headline):
            headline = candidate_headline
    return year, headline

def get_current_metadata_from_cli(file_path: Path):
    """
    Reads all metadata from a file and its sidecar using a direct subprocess call to exiftool,
    returning a Python dictionary.
    """
    try:
        xmp_file_path = file_path.with_suffix(".xmp")
        files_to_read = [str(file_path)]
        if xmp_file_path.exists():
            files_to_read.append(str(xmp_file_path))
        
        cmd = ["exiftool", "-j", "-m"] + files_to_read
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        metadata_list = json.loads(result.stdout)
        merged_metadata = {}
        for item in metadata_list:
            merged_metadata.update(item)            
        return merged_metadata
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        print(f"Error reading metadata from {file_path}: {e}")
        return {}

def update_metadata(file_path: Path, template, year, headline, debug: bool = False):
    """Update only missing fields in metadata using ExifTool."""
    metadata = get_current_metadata_from_cli(file_path)
    updates = {}
    cleaned_metadata = {}
    for key, value in metadata.items():
        if isinstance(value, str) and ("{subdir_text}" in value or "{year}" in value):
            cleaned_metadata[key] = None
        else:
            cleaned_metadata[key] = value
    metadata = cleaned_metadata
    normalized_metadata = {key.replace("XMP-", "").replace("Iptc4xmpCore:", "").replace("photoshop:", "").lower(): value for key, value in metadata.items()}
    if debug:
        print(f"[DEBUG] Full Metadata Dict: {metadata}")
        print(f"[DEBUG] Normalized Metadata Dict: {normalized_metadata}")
    for key, default_value in template.items():
        if key == "SourceFile":
            continue
        normalized_key = key.replace("XMP-", "").replace("Iptc4xmpCore:", "").replace("photoshop:", "").lower()
        if debug:
            print(f"[DEBUG] Checking key: {key} (Normalized: {normalized_key})")
        current_value = normalized_metadata.get(normalized_key)
        if isinstance(current_value, list) and len(current_value) == 1:
            current_value = current_value[0]
        if debug:
            print(f"[DEBUG] Current value for '{key}': {current_value}")
        if isinstance(default_value, dict):
            existing_struct = metadata.get(key, {})
            if existing_struct is None:
                if key.startswith("XMP-"):
                    fallback_key = key[4:]
                    existing_struct = metadata.get(fallback_key, {})
            struct_to_update = {}
            for sub_key, sub_value in default_value.items():
                current_sub_value = existing_struct.get(sub_key)
                if current_sub_value is None or current_sub_value == "" or current_sub_value == []:
                    value = sub_value
                    if year and isinstance(value, str) and "{year}" in value:
                        value = value.replace("{year}", year)
                    if headline and isinstance(value, str) and "{subdir_text}" in value:
                        value = value.replace("{subdir_text}", headline)
                    if isinstance(value, str) and "{year}" not in value and "{subdir_text}" not in value:
                        struct_to_update[sub_key] = value
                    else:
                        struct_to_update[sub_key] = sub_value
            if struct_to_update:
                updates[key] = struct_to_update
            continue
        if current_value is None or current_value == "" or current_value == []:
            value_to_update = default_value
            if isinstance(default_value, str):
                value = default_value
                if year and isinstance(value, str) and "{year}" in value:
                    value = value.replace("{year}", year)
                if headline and isinstance(value, str) and "{subdir_text}" in value:
                    value = value.replace("{subdir_text}", headline)
                if "{year}" not in value and "{subdir_text}" not in value:
                    value_to_update = value
            elif isinstance(default_value, list):
                new_list = []
                for item in default_value:
                    value = item
                    if year and isinstance(value, str) and "{year}" in value:
                        value = value.replace("{year}", year)
                    if headline and isinstance(value, str) and "{subdir_text}" in value:
                        value = value.replace("{subdir_text}", headline)
                    if isinstance(value, str) and "{year}" not in value and "{subdir_text}" not in value:
                        new_list.append(value)
                    elif not isinstance(value, str):
                        new_list.append(item)
                value_to_update = new_list
            updates[key] = value_to_update
    if updates:
        json_data = [{ "SourceFile": str(file_path), **updates }]
        if debug:
            print(f"[DEBUG] Would update {file_path} with JSON:")
            print(json.dumps(json_data, indent=2))
        else:
            try:
                with tempfile.NamedTemporaryFile(mode='w+', suffix=".json", encoding="utf-8") as temp_f:
                    json.dump(json_data, temp_f)
                    temp_f.flush()
                    cmd_args = ["exiftool", f"-json={temp_f.name}", "-overwrite_original", "-m", str(file_path)]
                    result = subprocess.run(cmd_args, check=True, capture_output=True, text=True)
                    print(f"Updated {file_path}")
                    if result.stdout.strip():
                        print(result.stdout.strip())
            except subprocess.CalledProcessError as e:
                print(f"Error updating {file_path} with exiftool.")
                print(f"Stderr: {e.stderr}")
            except FileNotFoundError:
                print("Error: 'exiftool' command not found. Please ensure it is installed and in your PATH.")

def traverse_and_update(archive_dir, template, debug: bool = False):
    """Walk through archive and update files as needed."""
    for root, dirs, files in os.walk(archive_dir):
        root_path = Path(root)
        try:
            relative_path = root_path.relative_to(archive_dir)
        except ValueError:
            relative_path = root_path  # This handles the case where archive_dir is the current directory.

        # ✅ Use root_path (real filesystem path) for completion check
        if is_directory_completed(relative_path, archive_dir):
            if debug:
                print(f"[SKIP] Already processed: {relative_path}")
            dirs[:] = []  # prevent descending further
            continue
        
        if "received" in str(relative_path).lower():
            print(f"Skipping subdirectory '{root}' due to 'Received' keyword.")
            dirs[:] = []
            continue

        path_lower = str(relative_path).lower()
        if "mobile" in path_lower and "edmond" not in path_lower:
            print(f"Skipping subdirectory '{root}' due to 'Mobile' keyword.")
            dirs[:] = []
            continue
        
        for file in files:
#            if file.lower().endswith((
#                ".nef", ".cr3", ".psd", ".jpg", ".jpeg", ".png", ".tif", ".tiff",
#                ".heic", ".heif", ".dng", ".avif", ".mov", ".mp4", ".m4a"
#            )):

            if file.lower().endswith((
                ".nef", ".cr3", ".psd", ".jpg", ".jpeg", ".png", ".tif", ".tiff",
                ".heic", ".heif", ".dng", ".avif", ".mp4", ".m4a"
            )):
                file_path = root_path / file
                
                # Check if we're using the current directory as the root
                if archive_dir == Path.cwd():
                    year, headline = extract_year_and_headline(file_path, debug=debug)
                else:
                    year, headline = extract_year_and_headline(file_path.relative_to(archive_dir), debug=debug)
                
                update_metadata(file_path, template, year, headline, debug)

        # ✅ Mark directory as completed after processing all files
        # Only mark non-root directories
        if relative_path != Path("."):
            mark_directory_completed(relative_path, archive_dir)


def is_directory_completed(relative_path: Path, root: Path) -> bool:
    """
    Returns True if the checkpoint file exists in the directory.
    """
    marker_path = root / relative_path / CHECKPOINT_FILENAME
    return marker_path.exists()


def mark_directory_completed(relative_path: Path, root: Path):
    """
    Creates a marker file in the given directory to indicate processing is done.
    """
    marker_path = root / relative_path / CHECKPOINT_FILENAME
    with open(marker_path, "w") as f:
        f.write("processed\n")
    print(f"[INFO] Marked completed: {relative_path}")



def cleanup_checkpoints(root_directory: Path):
    """
    Recursively deletes all checkpoint files under the given root directory.
    """
    removed = 0
    for marker_path in root_directory.rglob(CHECKPOINT_FILENAME):
        try:
            marker_path.unlink()
            removed += 1
        except FileNotFoundError:
            continue
    print(f"[INFO] Removed {removed} checkpoint files under {root_directory}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Update image metadata based on directory structure.",
        epilog=f"EXIF Headliner v{__version__} - Automated Metadata Management Tool"
    )
    
    # Add version argument
    parser.add_argument(
        "--version", 
        action="version", 
        version=f"%(prog)s {__version__}"
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--directory",
        help="Subdirectory under /Volumes/photo/shapfam/ to process (e.g., '2007 Print Quality')."
    )
    group.add_argument(
        "--current",
        action="store_true",
        help="Use the current working directory as the root."
    )
    
    parser.add_argument("--debug", action="store_true", help="Enable debug mode (print changes, don't write).")
    args = parser.parse_args()

    # The logic to determine the target directory remains the same.
    if args.current:
        target_dir = Path.cwd()
    else:
        target_dir = ARCHIVE_ROOT / args.directory
    
    if not target_dir.exists():
        print(f"Error: {target_dir} does not exist.")
        exit(1)

    template_data = load_template(TEMPLATE_FILE)
    template = template_data[0] if isinstance(template_data, list) else template_data

    print(f"Processing directory: {target_dir}")
    # This now calls the correct, full version of the function.
    traverse_and_update(target_dir, template, debug=args.debug)

    # Cleanup checkpoints
    cleanup_checkpoints(target_dir)