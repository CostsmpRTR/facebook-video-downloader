"""Video download service using yt-dlp"""
import os
import uuid
import shutil
from pathlib import Path
from typing import Dict, Any, Optional
import yt_dlp

from app.core.config import settings
from app.core.logging import logger
from app.schemas.video import VideoFormat


class VideoService:
    """Service for handling video downloads"""
    
    @staticmethod
    def validate_facebook_url(url: str) -> bool:
        """Validate if URL is a Facebook URL"""
        # Support regular videos, watch URLs, Reels, and share URLs
        facebook_patterns = [
            "facebook.com",
            "fb.com",
            "fb.watch",
            "m.facebook.com"
        ]
        return any(pattern in url.lower() for pattern in facebook_patterns)
    
    @staticmethod
    def extract_video_info(url: str) -> Dict[str, Any]:
        """Extract video information without downloading"""
        if not VideoService.validate_facebook_url(url):
            raise ValueError("Not a valid Facebook URL")
        
        download_id = str(uuid.uuid4())
        download_path = settings.DOWNLOAD_DIR / download_id
        download_path.mkdir(exist_ok=True)
        
        # Try multiple extraction strategies
        strategies = [
            # Strategy 1: Standard extraction
            {
                'format': 'best',
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-us,en;q=0.5',
                    'Sec-Fetch-Mode': 'navigate',
                },
            },
            # Strategy 2: Generic extractor with cookies
            {
                'format': 'best',
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'extractor_args': {
                    'facebook': {
                        'skip': ['dash']
                    }
                },
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                },
            },
            # Strategy 3: Mobile user agent
            {
                'format': 'best',
                'noplaylist': True,
                'quiet': True,
                'no_warnings': True,
                'skip_download': True,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
                },
            },
        ]
        
        last_error = None
        for idx, ydl_opts in enumerate(strategies):
            try:
                logger.info(f"Trying extraction strategy {idx + 1}/{len(strategies)}")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    
                    # Extract formats - filter for compatibility with standard video players
                    formats = []
                    if 'formats' in info and info['formats']:
                        for fmt in info.get('formats', []):
                            # Skip DASH, HLS, and other streaming-only formats
                            protocol = fmt.get('protocol', '')
                            format_note = fmt.get('format_note', '').lower()
                            ext = fmt.get('ext', 'mp4')
                            
                            # Skip incompatible formats
                            if any(x in protocol for x in ['m3u8', 'dash', 'http_dash_segments']):
                                continue
                            if any(x in format_note for x in ['dash', 'hls', 'fragment']):
                                continue
                            
                            # Only include video formats (not audio-only)
                            vcodec = fmt.get('vcodec', 'none')
                            if vcodec == 'none' or not vcodec:
                                continue
                            
                            # Get resolution info
                            height = fmt.get('height')
                            width = fmt.get('width')
                            if height and width:
                                resolution = f"{width}x{height}"
                            else:
                                resolution = fmt.get('resolution') or fmt.get('format_note') or 'unknown'
                            
                            # Skip if resolution is 'audio only'
                            if resolution == 'audio only':
                                continue
                            
                            # Prefer MP4 format
                            if ext not in ['mp4', 'mov', 'avi', 'mkv']:
                                continue
                            
                            # Create format entry
                            format_entry = VideoFormat(
                                format_id=fmt.get('format_id', 'best'),
                                resolution=resolution,
                                ext=ext,
                                filesize=fmt.get('filesize'),
                                format_note=f"{resolution} - {ext.upper()}" if height else f"Standard quality - {ext.upper()}"
                            )
                            
                            formats.append(format_entry)
                        
                        # Remove duplicates based on resolution
                        seen = set()
                        unique_formats = []
                        for fmt in formats:
                            if fmt.resolution not in seen:
                                seen.add(fmt.resolution)
                                unique_formats.append(fmt)
                        formats = unique_formats
                    
                    # If no compatible formats found, create a default "best" option
                    if not formats:
                        formats.append(VideoFormat(
                            format_id='best',
                            resolution='best',
                            ext='mp4',
                            filesize=None,
                            format_note='Best available quality - MP4 (recommended)'
                        ))
                    
                    # Convert duration to integer (yt-dlp returns float)
                    duration = info.get('duration')
                    if duration is not None:
                        duration = int(duration)
                    
                    logger.info(f"Successfully extracted video info using strategy {idx + 1}")
                    return {
                        'download_id': download_id,
                        'thumbnail_url': info.get('thumbnail'),
                        'title': info.get('title', 'Facebook Video'),
                        'duration': duration,
                        'formats': formats
                    }
            except Exception as e:
                last_error = e
                logger.warning(f"Strategy {idx + 1} failed: {str(e)}")
                continue
        
        # All strategies failed
        logger.error(f"All extraction strategies failed. Last error: {str(last_error)}")
        
        # Clean up directory if created
        if download_path.exists():
            shutil.rmtree(download_path)
        
        # Provide helpful error message based on the error type
        error_str = str(last_error)
        if "Cannot parse data" in error_str or "unable to extract" in error_str.lower():
            raise ValueError(
                "Unable to download this Facebook video. Facebook has updated their security measures. "
                "Please try one of these solutions:\n"
                "1. For Reels: Open the link in your browser, copy the full URL (facebook.com/reel/123456789)\n"
                "2. For regular videos: Try using the direct video URL instead of share links\n"
                "3. Some videos may be restricted and cannot be downloaded\n"
                "Note: Facebook actively blocks automated downloads and this may not work for all videos."
            )
        elif "Private video" in error_str or "login" in error_str.lower():
            raise ValueError("This video appears to be private or requires login. Only public videos can be downloaded.")
        else:
            raise ValueError(f"Could not process video: {error_str}")
    
    @staticmethod
    def download_video(url: str, download_id: str, format_id: str = "best") -> Path:
        """Download video and return file path"""
        download_path = settings.DOWNLOAD_DIR / download_id
        if not download_path.exists():
            download_path.mkdir(exist_ok=True)
        
        # Build format selector with fallbacks for better compatibility
        # Facebook Reels often have format issues, so we use a smart fallback
        if format_id == "best" or not format_id:
            format_selector = 'best'
        else:
            # Try the specific format, but fall back to best if not available
            format_selector = f'{format_id}/best'
        
        ydl_opts = {
            'format': format_selector,
            'outtmpl': str(download_path / '%(title)s.%(ext)s'),
            'noplaylist': True,
            'quiet': False,  # Show output for debugging
            'no_warnings': False,
            # Additional options for better Facebook compatibility
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            },
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                return Path(filename)
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            # If format not available, try with just 'best'
            if "Requested format is not available" in error_msg:
                logger.warning(f"Format {format_id} not available, retrying with 'best' format")
                ydl_opts['format'] = 'best'
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=True)
                        filename = ydl.prepare_filename(info)
                        return Path(filename)
                except Exception as retry_error:
                    logger.error(f"Retry failed: {str(retry_error)}")
                    raise ValueError(f"Could not download video in any available format: {str(retry_error)}")
            else:
                logger.error(f"Download error: {error_msg}")
                raise ValueError(f"Download failed: {error_msg}")
        except Exception as e:
            logger.error(f"Error downloading video: {str(e)}")
            raise ValueError(f"Unexpected error during download: {str(e)}")
    
    @staticmethod
    def cleanup_download(file_path: Path):
        """Clean up downloaded file and directory"""
        try:
            if file_path.exists():
                os.remove(file_path)
            
            # Remove parent directory if it's in downloads
            parent_dir = file_path.parent
            if parent_dir.exists() and settings.DOWNLOAD_DIR in parent_dir.parents:
                shutil.rmtree(parent_dir)
        except Exception as e:
            logger.error(f"Error cleaning up files: {str(e)}")
