#!/usr/bin/env python3

import argparse
import subprocess
import pyperclip
import re
import sys
import shutil
import os
import glob

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

def get_transcript_with_yt_dlp(video_url, yt_dlp_path):
    """
    V16.0: Uses the user's preferred yt-dlp command style with file output and SRT format.
    """
    print("--- Downloading auto-generated English subtitles... ---")
    
    # Based on the user's command, but simplified for our use case
    command = [
        yt_dlp_path,
        '--skip-download',
        '--write-auto-subs',
        '--sub-langs', 'en.*',  # Match all English variants
        '--convert-subs', 'srt',
        '--output', '%(title)s.%(ext)s',
        video_url
    ]
    
    try:
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
        print("\n--- ERROR: 'yt-dlp' failed ---", file=sys.stderr)
        print(f"-> Exit Code: {e.returncode}", file=sys.stderr)
        print(f"-> Error Message:\n{e.stderr}", file=sys.stderr)
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

def main():
    parser = argparse.ArgumentParser(
        description="ytcc v16.1: A streamlined tool to extract YouTube auto-generated subtitles to clipboard (with deduplication).",
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

if __name__ == "__main__":
    main()