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
TEMPLATE_FILE = "/Volumes/photo/other/tools/python/exif-headliner/metadata_template.json"


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

    # This first loop correctly finds the year from any part of the path.
    for p in parts:
        match = re.match(r"(\d{4})", p)
        if match:
            year = match.group(1)

    # This second loop correctly finds a headline from a "YYYY-MM-DD Headline" folder.
    for p in parts:
        m = re.match(r"(\d{4})-\d{2}-\d{2}(?:[ _-]+(.+))?", p)
        if m:
            year = m.group(1)
            headline = m.group(2) if len(m.groups()) > 1 and m.group(2) else None
            
    # --- ADDED LOGIC FOR YYYY TEXT FOLDER NAMES ---
    # This check runs after the more specific one, so it will only match if the first one doesn't.
    for p in parts:
        m = re.match(r"(\d{4})[ _-]+(.+)", p)
        if m and not headline:
            year = m.group(1)
            headline = m.group(2)

    # --- NEW LOGIC FOR CATCH-ALL HEADLINE ---
    # After checking for all specific date patterns, if no headline has been found,
    # use the last subdirectory name as the headline.
    if not headline and len(parts) > 1:
        # We check the parent directory name, as it's the most likely headline candidate.
        candidate_headline = parts[-2]
        # Make sure the candidate is not just a year (e.g., "2001")
        if not re.match(r"^\d{4}$", candidate_headline):
            headline = candidate_headline
    # --- END NEW LOGIC ---

    return year, headline


def get_current_metadata_from_cli(file_path: Path):
    """
    Reads all metadata from a file and its sidecar using a direct subprocess call to exiftool,
    returning a Python dictionary.
    """
    try:
        # Check for a sidecar XMP file and include it if it exists
        xmp_file_path = file_path.with_suffix(".xmp")
        files_to_read = [str(file_path)]
        if xmp_file_path.exists():
            files_to_read.append(str(xmp_file_path))
        
        # Use -j to get a single JSON object for all metadata. 
        # The -m flag is used to ignore minor errors.
        cmd = ["exiftool", "-j", "-m"] + files_to_read
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        # ExifTool returns a list of dictionaries, one for each file.
        # We need to merge them into a single dictionary.
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

        # --- NEW: Clean up metadata placeholders ---
    cleaned_metadata = {}
    for key, value in metadata.items():
        if isinstance(value, str) and ("{subdir_text}" in value or "{year}" in value):
            cleaned_metadata[key] = None
        else:
            cleaned_metadata[key] = value

    metadata = cleaned_metadata
    # --- END NEW: Clean up metadata placeholders ---

    
    # Create a simplified dictionary for robust lookups
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
        
        # Handle structured tags (dictionaries)
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

        # Handle simple tags that are missing or empty
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
        relative_path = root_path.relative_to(archive_dir)
        
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
            if file.lower().endswith((".nef", ".cr3", ".psd", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic", ".heif", ".dng", ".avif", ".mov", ".mp4", ".m4a")):
                file_path = root_path / file
                year, headline = extract_year_and_headline(file_path.relative_to(archive_dir), debug=debug)
                update_metadata(file_path, template, year, headline, debug)


import argparse
from pathlib import Path

# Placeholder for ARCHIVE_ROOT and other variables
ARCHIVE_ROOT = Path("/Volumes/photo/shapfam/")
TEMPLATE_FILE = "template.json"

def load_template(file):
    # This is a placeholder function
    return {}

def traverse_and_update(directory, template, debug):
    # This is a placeholder function
    print(f"Traversing and updating {directory}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update image metadata based on directory structure.")
    
    # Add a mutually exclusive group for 'directory' and 'current'
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
    
    parser.add_argument("--debug", action="store_true", help="Enable debug mode (print changes, don’t write).")
    args = parser.parse_args()

    # Determine the target directory based on the new logic
    if args.current:
        target_dir = Path.cwd()
    else:
        target_dir = ARCHIVE_ROOT / args.directory
    
    if not target_dir.exists():
        print(f"Error: {target_dir} does not exist.")
        exit(1)

    # The rest of the logic remains the same
    template_data = load_template(TEMPLATE_FILE)
    template = template_data[0] if isinstance(template_data, list) else template_data

    print(f"Processing directory: {target_dir}")
    traverse_and_update(target_dir, template, debug=args.debug)
