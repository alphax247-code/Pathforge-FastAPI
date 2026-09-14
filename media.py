"""
Media Module
Contains all media file handling, upload, and streaming functionality
Supports Supabase Storage integration
"""

import mimetypes
from flask import Response, request, abort
from storage import storage_upload, storage_list, storage_delete, storage_signed_url
from config import VIDEOS_BUCKET

# File Upload Configuration
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm', 'mp3', 'wav', 'pdf', 'doc', 'docx'}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB for videos


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_file_type(filename):
    """Determine file type from filename"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

    if ext in ['mp4', 'webm', 'avi', 'mov']:
        return 'video'
    elif ext in ['mp3', 'wav', 'ogg']:
        return 'audio'
    elif ext in ['jpg', 'jpeg', 'png', 'gif']:
        return 'image'
    elif ext in ['pdf', 'doc', 'docx']:
        return 'document'
    else:
        return 'unknown'


def upload_file_to_storage(file, folder='videos'):
    """
    Upload file to Supabase Storage

    Args:
        file: FileStorage object from Flask request
        folder: Storage folder (default: 'videos')

    Returns:
        dict with upload info or None if failed
    """
    if not file or not allowed_file(file.filename):
        return None

    from werkzeug.utils import secure_filename
    import time

    filename = secure_filename(file.filename)
    timestamp = str(int(time.time()))
    unique_filename = f"{timestamp}_{filename}"
    storage_path = f"{folder}/{unique_filename}"

    # Read file data
    file_data = file.read()
    file.seek(0)  # Reset file pointer

    # Guess content type
    content_type = file.content_type or mimetypes.guess_type(filename)[0] or 'application/octet-stream'

    # Upload to Supabase Storage
    r = storage_upload(VIDEOS_BUCKET, storage_path, file_data, content_type)

    if r.status_code >= 400:
        return None

    # Get signed URL for private access
    signed_url_response = storage_signed_url(VIDEOS_BUCKET, storage_path, 3600)

    return {
        'filename': unique_filename,
        'original_filename': filename,
        'storage_path': storage_path,
        'file_size': len(file_data),
        'mime_type': content_type,
        'media_type': get_file_type(filename),
        'signed_url': signed_url_response.json().get('signedURL') if signed_url_response.status_code < 400 else None
    }


def list_storage_files(folder='videos'):
    """
    List files in Supabase Storage

    Args:
        folder: Storage folder to list

    Returns:
        list of file info dicts
    """
    r = storage_list(VIDEOS_BUCKET, folder)

    if r.status_code >= 400:
        return []

    try:
        files = r.json()
        return files if isinstance(files, list) else []
    except:
        return []


def delete_storage_file(storage_path):
    """
    Delete file from Supabase Storage

    Args:
        storage_path: Full path to file in storage

    Returns:
        True if successful, False otherwise
    """
    r = storage_delete(VIDEOS_BUCKET, [storage_path])
    return r.status_code < 400


def get_file_signed_url(storage_path, expires_in=3600):
    """
    Get a signed URL for accessing a file

    Args:
        storage_path: Full path to file in storage
        expires_in: URL expiration time in seconds (default: 1 hour)

    Returns:
        Signed URL string or None
    """
    r = storage_signed_url(VIDEOS_BUCKET, storage_path, expires_in)

    if r.status_code >= 400:
        return None

    try:
        return r.json().get('signedURL')
    except:
        return None


# ============================================================================
# VIDEO STREAMING WITH RANGE REQUEST SUPPORT
# ============================================================================

def stream_video_from_url(video_url):
    """
    Stream video with range request support
    Proxies requests to Supabase Storage with proper headers

    Args:
        video_url: URL of the video file

    Returns:
        Flask Response with video stream
    """
    import requests

    range_header = request.headers.get('Range')
    headers = {}

    if range_header:
        headers['Range'] = range_header

    # Fetch video from Supabase Storage
    try:
        video_response = requests.get(video_url, headers=headers, stream=True)

        # Create Flask response
        response = Response(
            video_response.iter_content(chunk_size=8192),
            status=video_response.status_code,
            content_type=video_response.headers.get('Content-Type', 'video/mp4'),
            direct_passthrough=True
        )

        # Copy relevant headers
        if 'Content-Range' in video_response.headers:
            response.headers['Content-Range'] = video_response.headers['Content-Range']
        if 'Content-Length' in video_response.headers:
            response.headers['Content-Length'] = video_response.headers['Content-Length']

        response.headers['Accept-Ranges'] = 'bytes'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Disposition'] = 'inline'

        return response

    except Exception as e:
        print(f"Error streaming video: {e}")
        abort(500)
