import os
import uuid
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import current_app

class LocalStorageService:
    """
    Local file storage abstraction.
    Designed so it can be swapped with AWS S3 or Google Cloud Storage in later milestones
    without changing application route logic.
    """

    @staticmethod
    def is_allowed_file(filename):
        """Check if file extension matches allowed extensions (PDF, TXT)."""
        if not filename or '.' not in filename:
            return False
        ext = filename.rsplit('.', 1)[1].lower()
        return ext in current_app.config['ALLOWED_EXTENSIONS']

    @staticmethod
    def get_extension(filename):
        """Extract lowercase file extension."""
        return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

    @classmethod
    def save_file(cls, file_obj, user_id):
        """
        Validates, securely names, and stores an uploaded file.
        Returns a dictionary of file metadata or raises ValueError.
        """
        if not file_obj or file_obj.filename == '':
            raise ValueError("No file selected.")

        original_filename = secure_filename(file_obj.filename)
        if not original_filename:
            # Fallback if filename contains only non-ASCII characters
            original_filename = f"document_{uuid.uuid4().hex[:8]}"

        if not cls.is_allowed_file(original_filename):
            allowed = ", ".join(current_app.config['ALLOWED_EXTENSIONS']).upper()
            raise ValueError(f"Invalid file type. Only {allowed} files are allowed.")

        # Create user-specific upload directory: uploads/<user_id>/
        user_folder = Path(current_app.config['UPLOAD_FOLDER']) / str(user_id)
        user_folder.mkdir(parents=True, exist_ok=True)

        # Generate a unique storage filename to prevent overwriting and path collisions
        ext = cls.get_extension(original_filename)
        unique_name = f"{uuid.uuid4().hex}_{original_filename}"
        destination_path = user_folder / unique_name

        # Save to disk
        file_obj.save(str(destination_path))

        # Determine file size
        file_size = destination_path.stat().st_size

        # Check maximum file size
        if file_size > current_app.config['MAX_CONTENT_LENGTH']:
            destination_path.unlink(missing_ok=True)
            max_mb = current_app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
            raise ValueError(f"File size exceeds maximum allowed limit of {max_mb} MB.")

        # Store relative file path for database portability
        relative_path = str(Path(str(user_id)) / unique_name)

        return {
            'filename': unique_name,
            'original_filename': file_obj.filename,
            'file_path': relative_path,
            'file_size': file_size,
            'file_type': ext.upper()
        }

    @classmethod
    def get_absolute_path(cls, relative_path):
        """Safely resolve relative storage path to absolute filesystem path."""
        base_dir = Path(current_app.config['UPLOAD_FOLDER']).resolve()
        target_path = (base_dir / relative_path).resolve()
        
        # Security: Prevent Directory Traversal attacks
        if not str(target_path).startswith(str(base_dir)):
            raise PermissionError("Access denied: Invalid file path.")

        return target_path

    @classmethod
    def delete_file(cls, relative_path):
        """Delete file from disk storage."""
        try:
            target_path = cls.get_absolute_path(relative_path)
            if target_path.exists():
                target_path.unlink()
                return True
        except Exception:
            pass
        return False
