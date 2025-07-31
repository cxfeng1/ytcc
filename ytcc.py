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
from urllib.parse import urlparse, parse_qs

def find_yt_dlp():
    """Checks if yt-dlp is installed and accessible in the system's PATH."""
    path = shutil.which('yt-dlp')
    if path is None:
        print("FATAL ERROR: 'yt-dlp' is not installed or not in your system's PATH.", file=sys.stderr)
        print("Please install it to use this script. See: https://github.com/yt-dlp/yt-dlp", file=sys.stderr)
        sys.exit(1)
    return path

def extract_video_id(url):
    """Extract video ID from YouTube URL for better file matching."""
    try:
        parsed = urlparse(url)
        if 'youtube.com' in parsed.netloc:
            if 'watch' in parsed.path:
                return parse_qs(parsed.query).get('v', [None])[0]
            elif 'embed' in parsed.path:
                return parsed.path.split('/')[-1]
        elif 'youtu.be' in parsed.netloc:       
            return parsed.path.lstrip('/')
    except:
        pass
    return None

def check_if_playlist_url(url):
    """检查URL是否包含播放列表参数，并返回相关信息"""
    try:
        verbose_print(f"解析URL: {url}")
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        verbose_print(f"解析后的查询参数: {query_params}")
        
        if 'list' in query_params:
            list_id = query_params['list'][0]
            video_id = query_params.get('v', [None])[0]
            verbose_print(f"检测到播放列表 - list_id: {list_id}, video_id: {video_id}")
            return True, list_id, video_id
        verbose_print("未检测到播放列表参数")
        return False, None, None
    except Exception as e:
        verbose_print(f"URL解析出错: {e}")
        return False, None, None

def select_best_subtitle_file(srt_files, video_url):
    """
    Intelligently select the best subtitle file from multiple options.
    Priority: exact video match > shortest filename > user selection
    """
    if len(srt_files) == 1:
        return srt_files[0]
    
    print(f"-> Found {len(srt_files)} subtitle files:")
    for i, file in enumerate(srt_files, 1):
        print(f"   {i}. {file}")
    
    # Try to match by video ID first
    video_id = extract_video_id(video_url)
    if video_id:
        for file in srt_files:
            if video_id in file:
                print(f"-> Auto-selected (video ID match): {file}")
                return file
    
    # If auto mode is enabled, select shortest filename
    if AUTO_SELECT_MODE:
        selected = min(srt_files, key=len)
        print(f"-> Auto-selected (shortest name): {selected}")
        return selected
    
    # Interactive selection for multiple files
    print("\n-> Multiple subtitle files found. Please choose:")
    for i, file in enumerate(srt_files, 1):
        print(f"   {i}. {file}")
    
    while True:
        try:
            choice = input(f"-> Enter number (1-{len(srt_files)}) or press Enter for auto-select: ").strip()
            if not choice:
                # Auto-select: prefer shorter filenames (usually more specific)
                selected = min(srt_files, key=len)
                print(f"-> Auto-selected (shortest name): {selected}")
                return selected
            
            choice_num = int(choice)
            if 1 <= choice_num <= len(srt_files):
                selected = srt_files[choice_num - 1]
                print(f"-> Selected: {selected}")
                return selected
            else:
                print(f"-> Please enter a number between 1 and {len(srt_files)}")
        except ValueError:
            print("-> Please enter a valid number")
        except KeyboardInterrupt:
            print("\n-> Cancelled by user")
            return None

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
    V16.7: Enhanced with playlist detection, single video download, verbose logging, and network optimization.
    """
    print("--- Downloading auto-generated English subtitles... ---")
    verbose_print(f"开始下载流程，最大重试次数: {max_retries}")
    
    # 检查是否为播放列表URL
    is_playlist, list_id, video_id = check_if_playlist_url(video_url)
    if is_playlist:
        print(f"-> 检测到播放列表URL (list={list_id})")
        if video_id:
            print(f"-> 将只下载当前视频的字幕 (video={video_id})，不会下载整个播放列表")
        else:
            print("-> 将只下载播放列表中第一个视频的字幕，不会下载整个播放列表")
    
    # More conservative approach to avoid rate limiting with network optimization
    command = [
        yt_dlp_path,
        '--skip-download',
        '--write-auto-subs',
        '--sub-langs', 'en',  # Just 'en' instead of 'en.*' to be more specific
        '--convert-subs', 'srt',
        '--output', '%(title)s.%(ext)s',
        '--sleep-interval', '1',  # Add sleep between requests
        '--max-sleep-interval', '3',  # Random sleep up to 3 seconds
        '--retries', '5',  # 增加重试次数
        '--socket-timeout', '60',  # 增加socket超时时间到60秒
        '--fragment-retries', '10',  # 片段重试次数
        '--retry-sleep', '5',  # 重试间隔时间
    ]
    
    # 如果是播放列表URL，添加 --no-playlist 参数确保只下载单个视频
    if is_playlist:
        command.append('--no-playlist')
        verbose_print("添加 --no-playlist 参数")
    
    command.append(video_url)
    verbose_print(f"构建的yt-dlp命令: {' '.join(command)}")
    
    for attempt in range(max_retries):
        try:
            verbose_print(f"开始第 {attempt + 1} 次尝试")
            if attempt > 0:
                # Exponential backoff with jitter
                delay = (2 ** attempt) + random.uniform(0, 2)
                print(f"-> Retrying in {delay:.1f} seconds... (Attempt {attempt + 1}/{max_retries})")
                verbose_print(f"等待 {delay:.1f} 秒后重试")
                time.sleep(delay)
            
            print(f"-> Running command: {' '.join(command)}")
            verbose_print("执行yt-dlp命令...")
            verbose_print("如果长时间无响应，请尝试 Ctrl+C 中断")
            
            # 添加超时机制，防止无限等待
            try:
                result = subprocess.run(command, capture_output=True, text=True, 
                                      check=True, encoding='utf-8', timeout=120)  # 2分钟超时
                verbose_print(f"命令执行成功，返回码: {result.returncode}")
                verbose_print(f"stdout长度: {len(result.stdout)}, stderr长度: {len(result.stderr)}")
                if VERBOSE_MODE and result.stdout:
                    verbose_print(f"yt-dlp输出摘要: {result.stdout[:200]}...")
                if VERBOSE_MODE and result.stderr:
                    verbose_print(f"yt-dlp错误信息: {result.stderr[:200]}...")
            except subprocess.TimeoutExpired:
                print("-> 命令执行超时 (2分钟)，可能的原因：", file=sys.stderr)
                print("   1. 网络连接慢或不稳定", file=sys.stderr)
                print("   2. 视频可能没有可用的字幕", file=sys.stderr)
                print("   3. YouTube限制了访问", file=sys.stderr)
                verbose_print("yt-dlp命令执行超时")
                continue  # 继续重试
            
            # yt-dlp should have created an .srt file in the current directory
            # Find the generated subtitle file
            srt_files = glob.glob('*.en*.srt')
            verbose_print(f"搜索字幕文件，找到 {len(srt_files)} 个: {srt_files}")
            if not srt_files:
                print("-> No subtitle file was created. The video might not have auto-generated English subtitles.", file=sys.stderr)
                return None
            
            # Intelligently select the best subtitle file
            verbose_print("开始智能选择字幕文件...")
            selected_file = select_best_subtitle_file(srt_files, video_url)
            if not selected_file:
                print("-> No subtitle file selected.", file=sys.stderr)
                return None
            
            print(f"-> Processing subtitle file: {selected_file}")
            verbose_print(f"选定的字幕文件: {selected_file}")
            
            # Read and parse the SRT content
            verbose_print("读取字幕文件内容...")
            with open(selected_file, 'r', encoding='utf-8') as f:
                srt_content = f.read()
            
            verbose_print(f"字幕文件大小: {len(srt_content)} 字符")
            if not srt_content.strip():
                print("-> Subtitle file was empty.", file=sys.stderr)
                return None
            
            verbose_print("解析SRT内容...")
            transcript = parse_srt(srt_content)
            verbose_print(f"解析后的转录文本长度: {len(transcript) if transcript else 0} 字符")
            
            # Clean up ALL subtitle files (not just the selected one)
            verbose_print("开始清理字幕文件...")
            cleaned_files = []
            for srt_file in srt_files:
                try:
                    os.remove(srt_file)
                    cleaned_files.append(srt_file)
                    verbose_print(f"已删除文件: {srt_file}")
                except Exception as clean_error:
                    verbose_print(f"删除文件失败 {srt_file}: {clean_error}")
            
            if cleaned_files:
                print(f"-> Cleaned up {len(cleaned_files)} subtitle file(s)")
            
            if transcript:
                print("-> Subtitle successfully downloaded and parsed.")
                verbose_print("字幕下载和解析成功完成")
                return transcript
            else:
                print("-> Failed to extract text from subtitle file.", file=sys.stderr)
                verbose_print("从字幕文件提取文本失败")
                return None

        except subprocess.CalledProcessError as e:
            error_message = e.stderr.lower() if e.stderr else ""
            verbose_print(f"subprocess.CalledProcessError: 返回码={e.returncode}")
            verbose_print(f"错误信息: {e.stderr}")
            
            # Check if it's a 429 error (rate limiting)
            if "429" in error_message or "too many requests" in error_message:
                print(f"-> Rate limited (429 error) on attempt {attempt + 1}/{max_retries}", file=sys.stderr)
                verbose_print("检测到429限制错误")
                if attempt < max_retries - 1:
                    continue  # Retry
                else:
                    print("\n--- Trying fallback mode ---", file=sys.stderr)
                    verbose_print("尝试使用回退模式")
                    return try_fallback_mode(video_url, yt_dlp_path)
            else:
                # Other errors
                print(f"\n--- ERROR: 'yt-dlp' failed (attempt {attempt + 1}/{max_retries}) ---", file=sys.stderr)
                print(f"-> Exit Code: {e.returncode}", file=sys.stderr)
                print(f"-> Error Message:\n{e.stderr}", file=sys.stderr)
                verbose_print(f"其他错误，尝试次数: {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    continue  # Retry for other errors too
                else:
                    verbose_print("达到最大重试次数，返回None")
                    return None
                    
        except Exception as e:
            print(f"\nAN UNEXPECTED ERROR OCCURRED: {e}", file=sys.stderr)
            return None
        finally:
            # Clean up any remaining .srt files in case of errors
            remaining_files = glob.glob('*.en*.srt')
            for srt_file in remaining_files:
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
    verbose_print("进入回退模式")
    
    # 检查是否为播放列表URL
    is_playlist, list_id, video_id = check_if_playlist_url(video_url)
    
    # Ultra-minimal command with network optimization
    command = [
        yt_dlp_path,
        '--skip-download',
        '--write-auto-subs',
        '--sub-langs', 'en',
        '--output', 'fallback.%(ext)s',
        '--socket-timeout', '60',  # 增加超时时间
        '--retries', '3',  # 重试机制
        '--retry-sleep', '5',  # 重试间隔
    ]
    
    # 如果是播放列表URL，添加 --no-playlist 参数
    if is_playlist:
        command.append('--no-playlist')
        print("-> 回退模式：检测到播放列表，只下载单个视频")
        verbose_print("回退模式添加 --no-playlist 参数")
    
    command.append(video_url)
    verbose_print(f"回退模式命令: {' '.join(command)}")
    
    try:
        # Wait a bit more before fallback
        verbose_print("回退模式等待5秒...")
        time.sleep(5)
        print(f"-> Running fallback command: {' '.join(command)}")
        verbose_print("执行回退模式命令...")
        verbose_print("回退模式也有2分钟超时限制")
        
        try:
            result = subprocess.run(command, capture_output=True, text=True, 
                                  check=True, encoding='utf-8', timeout=120)  # 2分钟超时
            verbose_print(f"回退模式命令执行成功，返回码: {result.returncode}")
        except subprocess.TimeoutExpired:
            print("-> 回退模式也超时了，建议：", file=sys.stderr)
            print("   1. 检查网络连接", file=sys.stderr)
            print("   2. 稍后再试", file=sys.stderr)
            print("   3. 尝试不同的视频", file=sys.stderr)
            verbose_print("回退模式命令执行超时")
            return None
        
        # Look for any subtitle file
        subtitle_files = glob.glob('fallback.*.vtt') + glob.glob('fallback.*.srt')
        verbose_print(f"回退模式搜索到 {len(subtitle_files)} 个字幕文件: {subtitle_files}")
        if not subtitle_files:
            print("-> Fallback mode: No subtitle file created.", file=sys.stderr)
            verbose_print("回退模式：未找到字幕文件")
            return None
        
        subtitle_file = subtitle_files[0]
        print(f"-> Fallback mode: Found subtitle file: {subtitle_file}")
        verbose_print(f"回退模式选择文件: {subtitle_file}")
        
        # Read the content
        verbose_print("回退模式读取文件内容...")
        with open(subtitle_file, 'r', encoding='utf-8') as f:
            content = f.read()
        verbose_print(f"回退模式文件大小: {len(content)} 字符")
        
        # Clean up
        os.remove(subtitle_file)
        print(f"-> Cleaned up fallback file: {subtitle_file}")
        verbose_print(f"清理回退文件: {subtitle_file}")
        
        if not content.strip():
            print("-> Fallback mode: Subtitle file was empty.", file=sys.stderr)
            verbose_print("回退模式：字幕文件为空")
            return None
        
        # Parse based on file type
        verbose_print(f"回退模式解析文件类型: {subtitle_file}")
        if subtitle_file.endswith('.srt'):
            transcript = parse_srt(content)
            verbose_print("使用SRT解析器")
        else:
            # Basic VTT parsing
            transcript = parse_vtt(content)
            verbose_print("使用VTT解析器")
        
        verbose_print(f"回退模式解析结果长度: {len(transcript) if transcript else 0}")
        if transcript:
            print("-> Fallback mode: Success!")
            verbose_print("回退模式成功完成")
            return transcript
        else:
            print("-> Fallback mode: Failed to parse subtitle content.", file=sys.stderr)
            verbose_print("回退模式：解析字幕内容失败")
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
        description="ytcc v16.7: A streamlined tool to extract YouTube auto-generated subtitles to clipboard (with intelligent subtitle file selection, playlist handling, verbose logging, and network optimization).",
        epilog="Example: ytcc https://www.youtube.com/watch?v=VIDEO_ID or ytcc --test-connection --verbose --auto https://www.youtube.com/watch?v=VIDEO_ID&list=PLAYLIST_ID"
    )
    parser.add_argument("url", help="YouTube video URL (no quotes needed)")
    parser.add_argument("--auto", "-a", action="store_true", 
                       help="Auto-select subtitle file without user interaction")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose output for debugging")
    parser.add_argument("--test-connection", "-t", action="store_true",
                       help="Test network connection to YouTube before downloading")
    args = parser.parse_args()

    yt_dlp_path = find_yt_dlp()
    
    # Set global modes
    global AUTO_SELECT_MODE, VERBOSE_MODE
    AUTO_SELECT_MODE = args.auto
    VERBOSE_MODE = args.verbose
    
    if VERBOSE_MODE:
        print("[VERBOSE] 详细日志模式已启用")
        print(f"[VERBOSE] yt-dlp 路径: {yt_dlp_path}")
        print(f"[VERBOSE] 输入URL: {args.url}")
        print(f"[VERBOSE] 自动选择模式: {args.auto}")
        print(f"[VERBOSE] 连接测试模式: {args.test_connection}")
    
    # 如果启用了连接测试或verbose模式，先测试网络连接
    if args.test_connection or VERBOSE_MODE:
        if not test_youtube_connection(yt_dlp_path):
            if args.test_connection:
                print("\n💡 建议的解决方案：")
                print("1. 检查网络连接是否正常")
                print("2. 尝试使用VPN或更换网络")
                print("3. 稍后再试（可能是临时的网络问题）")
                print("4. 更新yt-dlp: pip install --upgrade yt-dlp")
                sys.exit(1)
            else:
                print("⚠️  网络连接有问题，但将继续尝试下载...")
    
    verbose_print("开始获取转录文本...")
    transcript = get_transcript_with_yt_dlp(args.url, yt_dlp_path)

    if transcript:
        verbose_print("成功获取转录文本")
        print("\n✅ --- FINAL TRANSCRIPT --- ✅\n")
        print(transcript)
        print("\n--------------------------\n")
        verbose_print("尝试复制到剪贴板...")
        try:
            pyperclip.copy(transcript)
            print("Success: Transcript has been copied to the clipboard.")
            verbose_print("成功复制到剪贴板")
        except pyperclip.PyperclipException as e:
            print(f"Warning: Could not copy to clipboard.", file=sys.stderr)
            verbose_print(f"复制到剪贴板失败: {e}")
    else:
        verbose_print("获取转录文本失败")
        print("\n❌ Failed to extract transcript. Please check the video URL and try again.", file=sys.stderr)
        sys.exit(1)

# Global variables
AUTO_SELECT_MODE = False
VERBOSE_MODE = False

def verbose_print(*args, **kwargs):
    """打印详细日志信息，仅在 verbose 模式下输出"""
    if VERBOSE_MODE:
        print("[VERBOSE]", *args, **kwargs)

def test_youtube_connection(yt_dlp_path):
    """测试到YouTube的网络连接"""
    print("🔗 测试网络连接到YouTube...")
    
    test_command = [
        yt_dlp_path,
        '--list-formats',
        '--socket-timeout', '30',
        'https://www.youtube.com/watch?v=jNQXAC9IVRw'  # YouTube官方测试视频
    ]
    
    try:
        verbose_print(f"测试命令: {' '.join(test_command)}")
        result = subprocess.run(test_command, capture_output=True, text=True, 
                              timeout=45, encoding='utf-8')
        
        if result.returncode == 0:
            print("✅ 网络连接正常")
            verbose_print("YouTube连接测试成功")
            return True
        else:
            print("❌ 网络连接有问题")
            print(f"错误信息: {result.stderr[:200]}")
            verbose_print(f"连接测试失败，返回码: {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        print("❌ 网络连接超时")
        print("建议检查网络连接或稍后再试")
        verbose_print("YouTube连接测试超时")
        return False
    except Exception as e:
        print(f"❌ 连接测试出错: {e}")
        verbose_print(f"连接测试异常: {e}")
        return False

if __name__ == "__main__":
    main()