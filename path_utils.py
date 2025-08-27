"""
Path utilities for dynamic path detection in TikTok Creator project.
This module provides functions to dynamically find paths instead of using hardcoded ones.
"""

import os
import glob
from pathlib import Path
from typing import Optional, Union


def find_project_root(marker_files: Optional[list] = None, start_path: Optional[str] = None) -> Optional[str]:
    """
    Find the project root directory by looking for marker files/directories.
    
    Args:
        marker_files: List of files/directories that indicate the project root
        start_path: Path to start searching from (defaults to current working directory)
    
    Returns:
        Path to project root or None if not found
    """
    if marker_files is None:
        marker_files = ['CONFIG.txt', 'UI.py', 'tiktokimggen.py']
    
    if start_path is None:
        start_path = os.getcwd()
    
    current_path = Path(start_path).resolve()
    
    # Look up the directory tree for marker files
    while current_path != current_path.parent:
        if all(os.path.exists(current_path / marker) for marker in marker_files):
            return str(current_path)
        current_path = current_path.parent
    
    return None


def find_parent_directory(name: str, path: Optional[str] = None) -> Optional[str]:
    """
    Recursively looks at parent folders starting from the given path until it finds the given name.
    Enhanced version of the existing find_path function.
    
    Args:
        name: Name of the directory/file to find
        path: Starting path (defaults to current working directory)
    
    Returns:
        Path to the found directory/file or None if not found
    """
    if path is None:
        path = os.getcwd()

    current_path = Path(path).resolve()
    
    # Look up the directory tree
    while current_path != current_path.parent:
        target_path = current_path / name
        if target_path.exists():
            print(f"{name} found: {target_path}")
            return str(target_path)
        current_path = current_path.parent
    
    return None


def get_comfyui_path() -> Optional[str]:
    """
    Find the ComfyUI directory path dynamically.
    
    Returns:
        Path to ComfyUI directory or None if not found
    """
    return find_parent_directory("ComfyUI")


def get_comfyui_output_path() -> Optional[str]:
    """
    Get the ComfyUI output directory path.
    
    Returns:
        Path to ComfyUI output directory or None if not found
    """
    comfyui_path = get_comfyui_path()
    if comfyui_path:
        output_path = os.path.join(comfyui_path, "output")
        if os.path.exists(output_path):
            return output_path
    return None


def get_comfyui_audio_output_path() -> Optional[str]:
    """
    Get the ComfyUI audio output directory path.
    
    Returns:
        Path to ComfyUI audio output directory or None if not found
    """
    output_path = get_comfyui_output_path()
    if output_path:
        audio_path = os.path.join(output_path, "audio")
        if os.path.exists(audio_path):
            return audio_path
    return None


def get_project_output_directory() -> str:
    """
    Get the project's output directory from CONFIG.txt or use default.
    
    Returns:
        Path to output directory
    """
    project_root = find_project_root()
    if not project_root:
        # Fallback to current directory structure
        project_root = os.getcwd()
    
    config_path = os.path.join(project_root, "CONFIG.txt")
    
    # Try to read from CONFIG.txt
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('output_directory='):
                        output_dir = line.split('=', 1)[1].strip()
                        # Remove quotes if present
                        if (output_dir.startswith('"') and output_dir.endswith('"')) or \
                           (output_dir.startswith("'") and output_dir.endswith("'")):
                            output_dir = output_dir[1:-1]
                        
                        # If path is absolute and exists, use it
                        if os.path.isabs(output_dir) and os.path.exists(output_dir):
                            return output_dir
                        
                        # If path is relative, make it relative to project root
                        relative_path = os.path.join(project_root, output_dir)
                        if os.path.exists(relative_path):
                            return relative_path
                        
                        # Create the directory if it doesn't exist
                        os.makedirs(relative_path, exist_ok=True)
                        return relative_path
        except Exception as e:
            print(f"Error reading CONFIG.txt: {e}")
    
    # Fallback to default Output directory
    default_output = os.path.join(project_root, "Output")
    os.makedirs(default_output, exist_ok=True)
    return default_output


def get_relative_path(file_path: str, relative_to: Optional[str] = None) -> str:
    """
    Convert an absolute path to a relative path based on project structure.
    
    Args:
        file_path: The file path to convert
        relative_to: Base path to make relative to (defaults to project root)
    
    Returns:
        Relative path string
    """
    if relative_to is None:
        relative_to = find_project_root() or os.getcwd()
    
    try:
        return os.path.relpath(file_path, relative_to)
    except ValueError:
        # Can't make relative (different drives on Windows), return absolute
        return file_path


def ensure_directory_exists(path: str) -> str:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        path: Directory path to ensure exists
    
    Returns:
        The directory path
    """
    os.makedirs(path, exist_ok=True)
    return path


def find_files_by_pattern(pattern: str, search_path: Optional[str] = None) -> list:
    """
    Find files matching a pattern in the specified directory or project root.
    
    Args:
        pattern: Glob pattern to search for
        search_path: Directory to search in (defaults to project root)
    
    Returns:
        List of matching file paths
    """
    if search_path is None:
        search_path = find_project_root() or os.getcwd()
    
    return glob.glob(os.path.join(search_path, pattern))


def normalize_path_for_platform(path: str) -> str:
    """
    Normalize a path for the current platform.
    
    Args:
        path: Path to normalize
    
    Returns:
        Normalized path
    """
    return os.path.normpath(path)


def get_chrome_user_data_path() -> str:
    """
    Get the Chrome User Data path for the current user.
    
    Returns:
        Path to Chrome User Data directory
    """
    return os.path.expanduser("~\\AppData\\Local\\Google\\Chrome\\User Data")


def update_config_path(key: str, new_path: str) -> bool:
    """
    Update a path in the CONFIG.txt file to use relative paths where possible.
    
    Args:
        key: Configuration key to update
        new_path: New path value
    
    Returns:
        True if successful, False otherwise
    """
    project_root = find_project_root()
    if not project_root:
        return False
    
    config_path = os.path.join(project_root, "CONFIG.txt")
    
    try:
        # Read existing config
        config_lines = []
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config_lines = f.readlines()
        
        # Try to make path relative if it's within the project
        try:
            if os.path.commonpath([new_path, project_root]) == project_root:
                new_path = get_relative_path(new_path, project_root)
        except ValueError:
            # Different drives, keep absolute
            pass
        
        # Update or add the key
        key_found = False
        for i, line in enumerate(config_lines):
            if line.strip().startswith(f"{key}="):
                config_lines[i] = f"{key}={new_path}\n"
                key_found = True
                break
        
        if not key_found:
            config_lines.append(f"{key}={new_path}\n")
        
        # Write back to file
        with open(config_path, 'w', encoding='utf-8') as f:
            f.writelines(config_lines)
        
        return True
    except Exception as e:
        print(f"Error updating config: {e}")
        return False


# Legacy function compatibility
def find_path(name: str, path: Optional[str] = None) -> Optional[str]:
    """
    Legacy compatibility function - use find_parent_directory instead.
    """
    return find_parent_directory(name, path)
