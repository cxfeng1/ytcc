# ytcc - YouTube Transcript Extractor

A streamlined command-line tool to extract YouTube auto-generated subtitles and copy them to your clipboard.

## Features

- 🎯 **Auto-generated subtitles only**: Focuses on AI-generated English subtitles
- 📋 **Clipboard integration**: Automatically copies extracted text to clipboard
- 🧹 **Smart deduplication**: Removes repeated sentences common in auto-generated subtitles
- 🚀 **Simple usage**: No quotes needed for URLs, just `ytcc <url>`
- 🔧 **Robust**: Built on top of the reliable `yt-dlp` tool

## Prerequisites

- Python 3.6 or higher
- `yt-dlp` installed and available in your system PATH
- `pyperclip` Python package

## Installation

1. **Install yt-dlp** (if not already installed):
   ```bash
   # Using pip
   pip install yt-dlp
   
   # Using Homebrew (macOS)
   brew install yt-dlp
   ```

2. **Install pyperclip**:
   ```bash
   pip install pyperclip
   ```

3. **Clone this repository**:
   ```bash
   git clone https://github.com/YOUR_USERNAME/ytcc.git
   cd ytcc
   ```

4. **Make the script executable and create a global command**:
   ```bash
   chmod +x ytcc.py
   sudo ln -sf "$(pwd)/ytcc.py" /usr/local/bin/ytcc
   ```

## Usage

Simply run `ytcc` followed by any YouTube URL:

```bash
ytcc https://www.youtube.com/watch?v=VIDEO_ID
```

### Examples

```bash
# Extract subtitles from a YouTube video
ytcc https://www.youtube.com/watch?v=dQw4w9WgXcQ

# Works with any YouTube URL format
ytcc https://youtu.be/dQw4w9WgXcQ
```

The tool will:
1. Download the auto-generated English subtitles
2. Parse and clean the text (removing timestamps and duplicates)
3. Copy the final transcript to your clipboard
4. Display the transcript in your terminal

## How It Works

`ytcc` is a smart wrapper around `yt-dlp` that:

1. **Calls yt-dlp** with optimized parameters for subtitle extraction
2. **Processes SRT files** to extract clean text content
3. **Removes duplicates** that are common in auto-generated subtitles
4. **Handles cleanup** of temporary files automatically

The tool uses this `yt-dlp` command internally:
```bash
yt-dlp --skip-download --write-auto-subs --sub-langs 'en.*' --convert-subs srt --output '%(title)s.%(ext)s' <URL>
```

## Supported Platforms

- ✅ macOS
- ✅ Linux
- ✅ Windows (with appropriate Python setup)

## Troubleshooting

### "yt-dlp not found" error
Make sure `yt-dlp` is installed and available in your PATH:
```bash
which yt-dlp
yt-dlp --version
```

### "No subtitle file was created" error
This means the video doesn't have auto-generated English subtitles. Try:
- Checking if the video has subtitles by visiting it on YouTube
- Waiting a bit if it's a newly uploaded video (YouTube takes time to generate subtitles)

### Clipboard not working
Install the appropriate clipboard utility for your system:
- **Linux**: `sudo apt-get install xclip` or `sudo apt-get install xsel`
- **macOS/Windows**: Should work out of the box with `pyperclip`

## Development

This project evolved from a complex browser extension to a simple, reliable command-line tool. The current approach leverages the battle-tested `yt-dlp` for all YouTube interactions, ensuring maximum compatibility and reliability.

### Version History

- **v16.1**: Added deduplication logic to prevent repeated sentences
- **v16.0**: Complete rewrite using file-based approach with SRT format
- **v15.0**: Focused on auto-generated subtitles only
- **v1.0-v14.x**: Various approaches including browser extension and direct API calls

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- Built on top of the excellent [yt-dlp](https://github.com/yt-dlp/yt-dlp) project
- Inspired by the need for a simple, reliable YouTube transcript extraction tool

## Handling Rate Limiting (429 Errors)

YouTube sometimes blocks requests with "429 Too Many Requests" errors. ytcc v16.3 includes advanced handling for this:

### Automatic Protection Features
- **Retry mechanism**: Automatically retries up to 3 times with exponential backoff
- **Built-in delays**: Adds 1-3 second delays between requests
- **Fallback mode**: Uses minimal options if standard mode fails

### If You Still Get 429 Errors
1. **Wait 10-15 minutes** before trying again
2. **Use a VPN** to change your IP address
3. **Check the video** - ensure it has auto-generated English subtitles
4. **Try during off-peak hours** when YouTube servers are less busy

### Error Messages Explained
- `Rate limited (429 error)` - YouTube is temporarily blocking your IP
- `Trying fallback mode` - Using minimal options to bypass restrictions
- `Fallback mode: Success!` - Successfully retrieved subtitles with basic method

## Examples

```bash
# Extract subtitles from a YouTube video
ytcc "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# The transcript will be automatically copied to your clipboard
``` 