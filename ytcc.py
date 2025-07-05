#!/usr/bin/env python3

import argparse
import subprocess
import pyperclip
import re
import sys
import shutil
import os
import glob
import time
import random

def find_yt_dlp():
    """Checks if yt-dlp is installed and accessible in the system's PATH."""
    path = shutil.which('yt-dlp')
    if path is None:
        print("FATAL ERROR: 'yt-dlp' is not installed or not in your system's PATH.", file=sys.stderr)
        print("Please install it to use this script. See: https://github.com/yt-dlp/yt-dlp", file=sys.stderr)
        sys.exit(1)
    return path

def parse_srt(srt_content):
    """
    Parses SRT content to extract only the spoken text.
    V16.1: Added deduplication to prevent repeated sentences.
    """
    lines = []
    seen_lines = set()  # Track seen lines to avoid duplicates
    
    for line in srt_content.strip().split('\n'):
        line = line.strip()
        # Skip sequence numbers, timestamps, and empty lines
        if not line or line.isdigit() or '-->' in line:
            continue
        # Remove any HTML-like tags
        cleaned_line = re.sub(r'<[^>]+>', '', line)
        cleaned_line = cleaned_line.strip()
        
        # Only add non-empty, unique lines
        if cleaned_line and cleaned_line not in seen_lines:
            lines.append(cleaned_line)
            seen_lines.add(cleaned_line)
    
    return ' '.join(lines)

def get_transcript_with_yt_dlp(video_url, yt_dlp_path, max_retries=3):
    """
    V16.2: Enhanced with retry mechanism and rate limiting to handle 429 errors.
    """
    print("--- Downloading auto-generated English subtitles... ---")
    
    # More conservative approach to avoid rate limiting
    command = [
        yt_dlp_path,
        '--skip-download',
        '--write-auto-subs',
        '--sub-langs', 'en',  # Just 'en' instead of 'en.*' to be more specific
        '--convert-subs', 'srt',
        '--output', '%(title)s.%(ext)s',
        '--sleep-interval', '1',  # Add sleep between requests
        '--max-sleep-interval', '3',  # Random sleep up to 3 seconds
        '--retries', '3',  # Built-in retry mechanism
        video_url
    ]
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                # Exponential backoff with jitter
                delay = (2 ** attempt) + random.uniform(0, 2)
                print(f"-> Retrying in {delay:.1f} seconds... (Attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
            
            print(f"-> Running command: {' '.join(command)}")
            result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8')
            
            # yt-dlp should have created an .srt file in the current directory
            # Find the generated subtitle file
            srt_files = glob.glob('*.en*.srt')
            if not srt_files:
                print("-> No subtitle file was created. The video might not have auto-generated English subtitles.", file=sys.stderr)
                return None
            
            # Use the first matching file
            srt_file = srt_files[0]
            print(f"-> Found subtitle file: {srt_file}")
            
            # Read and parse the SRT content
            with open(srt_file, 'r', encoding='utf-8') as f:
                srt_content = f.read()
            
            # Clean up the temporary file
            os.remove(srt_file)
            print(f"-> Cleaned up temporary file: {srt_file}")
            
            if not srt_content.strip():
                print("-> Subtitle file was empty.", file=sys.stderr)
                return None
            
            transcript = parse_srt(srt_content)
            if transcript:
                print("-> Subtitle successfully downloaded and parsed.")
                return transcript
            else:
                print("-> Failed to extract text from subtitle file.", file=sys.stderr)
                return None

        except subprocess.CalledProcessError as e:
            error_message = e.stderr.lower() if e.stderr else ""
            
            # Check if it's a 429 error (rate limiting)
            if "429" in error_message or "too many requests" in error_message:
                print(f"-> Rate limited (429 error) on attempt {attempt + 1}/{max_retries}", file=sys.stderr)
                if attempt < max_retries - 1:
                    continue  # Retry
                else:
                    print("\n--- Trying fallback mode ---", file=sys.stderr)
                    return try_fallback_mode(video_url, yt_dlp_path)
            else:
                # Other errors
                print(f"\n--- ERROR: 'yt-dlp' failed (attempt {attempt + 1}/{max_retries}) ---", file=sys.stderr)
                print(f"-> Exit Code: {e.returncode}", file=sys.stderr)
                print(f"-> Error Message:\n{e.stderr}", file=sys.stderr)
                if attempt < max_retries - 1:
                    continue  # Retry for other errors too
                else:
                    return None
                    
        except Exception as e:
            print(f"\nAN UNEXPECTED ERROR OCCURRED: {e}", file=sys.stderr)
            return None
        finally:
            # Clean up any remaining .srt files in case of errors
            for srt_file in glob.glob('*.en*.srt'):
                try:
                    os.remove(srt_file)
                    print(f"-> Cleaned up remaining file: {srt_file}")
                except:
                    pass
    
    return None

def try_fallback_mode(video_url, yt_dlp_path):
    """
    Fallback mode with minimal options to avoid rate limiting.
    """
    print("-> Attempting fallback mode with minimal options...")
    
    # Ultra-minimal command
    command = [
        yt_dlp_path,
        '--skip-download',
        '--write-auto-subs',
        '--sub-langs', 'en',
        '--output', 'fallback.%(ext)s',
        video_url
    ]
    
    try:
        # Wait a bit more before fallback
        time.sleep(5)
        print(f"-> Running fallback command: {' '.join(command)}")
        result = subprocess.run(command, capture_output=True, text=True, check=True, encoding='utf-8')
        
        # Look for any subtitle file
        subtitle_files = glob.glob('fallback.*.vtt') + glob.glob('fallback.*.srt')
        if not subtitle_files:
            print("-> Fallback mode: No subtitle file created.", file=sys.stderr)
            return None
        
        subtitle_file = subtitle_files[0]
        print(f"-> Fallback mode: Found subtitle file: {subtitle_file}")
        
        # Read the content
        with open(subtitle_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Clean up
        os.remove(subtitle_file)
        print(f"-> Cleaned up fallback file: {subtitle_file}")
        
        if not content.strip():
            print("-> Fallback mode: Subtitle file was empty.", file=sys.stderr)
            return None
        
        # Parse based on file type
        if subtitle_file.endswith('.srt'):
            transcript = parse_srt(content)
        else:
            # Basic VTT parsing
            transcript = parse_vtt(content)
        
        if transcript:
            print("-> Fallback mode: Success!")
            return transcript
        else:
            print("-> Fallback mode: Failed to parse subtitle content.", file=sys.stderr)
            return None
            
    except subprocess.CalledProcessError as e:
        print(f"-> Fallback mode also failed: {e.stderr}", file=sys.stderr)
        print("-> Suggestions:", file=sys.stderr)
        print("   1. Wait 10-15 minutes before trying again", file=sys.stderr)
        print("   2. Try using a VPN to change your IP address", file=sys.stderr)
        print("   3. Check if the video has subtitles available", file=sys.stderr)
        return None
    except Exception as e:
        print(f"-> Fallback mode error: {e}", file=sys.stderr)
        return None
    finally:
        # Clean up any remaining fallback files
        for file in glob.glob('fallback.*'):
            try:
                os.remove(file)
            except:
                pass

def parse_vtt(vtt_content):
    """
    Basic VTT (WebVTT) parser to extract text content.
    """
    lines = []
    seen_lines = set()
    
    for line in vtt_content.split('\n'):
        line = line.strip()
        # Skip WebVTT headers, timestamps, and empty lines
        if (not line or line.startswith('WEBVTT') or 
            line.startswith('NOTE') or '-->' in line or
            line.startswith('<') or line.isdigit()):
            continue
        
        # Remove any HTML-like tags
        cleaned_line = re.sub(r'<[^>]+>', '', line)
        cleaned_line = cleaned_line.strip()
        
        # Only add non-empty, unique lines
        if cleaned_line and cleaned_line not in seen_lines:
            lines.append(cleaned_line)
            seen_lines.add(cleaned_line)
    
    return ' '.join(lines)

def main():
    parser = argparse.ArgumentParser(
        description="ytcc v16.3: A streamlined tool to extract YouTube auto-generated subtitles to clipboard (with advanced rate limiting protection and fallback mode).",
        epilog="Example: ytcc https://www.youtube.com/watch?v=VIDEO_ID"
    )
    parser.add_argument("url", help="YouTube video URL (no quotes needed)")
    args = parser.parse_args()

    yt_dlp_path = find_yt_dlp()
    transcript = get_transcript_with_yt_dlp(args.url, yt_dlp_path)

    if transcript:
        print("\n✅ --- FINAL TRANSCRIPT --- ✅\n")
        print(transcript)
        print("\n--------------------------\n")
        try:
            pyperclip.copy(transcript)
            print("Success: Transcript has been copied to the clipboard.")
        except pyperclip.PyperclipException:
            print(f"Warning: Could not copy to clipboard.", file=sys.stderr)
    else:
        print("\n❌ Failed to extract transcript. Please check the video URL and try again.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()