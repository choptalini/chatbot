import os
import mimetypes
import logging
from typing import Optional

import requests


logger = logging.getLogger(__name__)


def _guess_extension(content_type: Optional[str], fallback_url: Optional[str], message_type: Optional[str]) -> str:
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(';')[0].strip())
        if ext:
            return ext
    # Fallback: inspect URL suffix
    if fallback_url and '.' in fallback_url.split('/')[-1]:
        suffix = fallback_url.split('/')[-1]
        dot = suffix.rfind('.')
        if dot != -1:
            return suffix[dot:]
    # Fallback by message type
    if message_type == 'image':
        return '.jpg'
    if message_type == 'audio':
        return '.ogg'
    if message_type == 'video':
        return '.mp4'
    return '.bin'


def upload_media_to_supabase(
    media_url: str,
    user_id: int,
    contact_id: int,
    message_id: str,
    message_type: str,
) -> Optional[str]:
    """
    Downloads a media file from the Infobip-secured URL and uploads it to Supabase Storage.
    Returns a public URL suitable for rendering in the frontend, or None on failure.
    Requires env vars: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, INFOBIP_API_KEY
    Assumes the target bucket is public.
    """
    supabase_url = os.getenv('SUPABASE_URL') or os.getenv('NEXT_PUBLIC_SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    # Store media in this bucket by default (images and audio)
    bucket = os.getenv('SUPABASE_MEDIA_BUCKET', 'swiftmessages.images')
    infobip_api_key = os.getenv('INFOBIP_API_KEY')

    if not supabase_url or not supabase_key:
        logger.warning('Supabase Storage env not configured; skipping upload')
        return None

    # 1) Download media from Infobip URL with authorization
    headers = {}
    if infobip_api_key:
        headers['Authorization'] = f'App {infobip_api_key}'
    try:
        resp = requests.get(media_url, headers=headers, timeout=30)
        resp.raise_for_status()
        content_type = resp.headers.get('Content-Type')
        data = resp.content
    except Exception as e:
        logger.error(f'Failed to download media from Infobip URL: {e}')
        return None

    # 2) Compute storage path
    ext = _guess_extension(content_type, media_url, message_type)
    path = f'{user_id}/{contact_id}/{message_id}{ext}'

    # 3) Upload to Supabase Storage via REST API
    upload_url = f"{supabase_url.rstrip('/')}/storage/v1/object/{bucket}/{path}"
    try:
        up_headers = {
            'Authorization': f'Bearer {supabase_key}',
            'Content-Type': content_type or 'application/octet-stream',
        }
        up_resp = requests.post(upload_url, headers=up_headers, data=data, timeout=30)
        # If file exists and upsert desired, try PUT
        if up_resp.status_code == 409:
            up_resp = requests.put(upload_url, headers=up_headers, data=data, timeout=30)
        up_resp.raise_for_status()
    except Exception as e:
        logger.error(f'Failed to upload media to Supabase Storage: {e}')
        return None

    # 4) Build public URL (bucket must be public)
    public_url = f"{supabase_url.rstrip('/')}/storage/v1/object/public/{bucket}/{path}"
    return public_url

