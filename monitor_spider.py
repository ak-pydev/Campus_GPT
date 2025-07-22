#!/usr/bin/env python3
"""
Real-time monitoring script for the CampusGPT spider.
Shows progress, memory usage, and checkpoint status.
"""

import json
import time
import pickle
import psutil
from pathlib import Path
from datetime import datetime, timedelta

def get_memory_usage():
    """Get current memory usage of Python processes."""
    total_memory = 0
    scrapy_processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cmdline']):
        try:
            if 'python' in proc.info['name'].lower():
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'scrapy' in cmdline.lower() or 'nku_info' in cmdline.lower():
                    memory_mb = proc.info['memory_info'].rss / 1024 / 1024
                    total_memory += memory_mb
                    scrapy_processes.append({
                        'pid': proc.info['pid'],
                        'memory_mb': memory_mb,
                        'cmdline': cmdline[:100] + '...' if len(cmdline) > 100 else cmdline
                    })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
            
    return total_memory, scrapy_processes

def read_checkpoint_info():
    """Read current checkpoint status."""
    checkpoint_file = Path("crawler_checkpoint.pkl")
    visited_urls_file = Path("visited_urls.json")
    
    info = {
        'pages_scraped': 0,
        'urls_visited': 0,
        'urls_failed': 0,
        'last_updated': None,
        'checkpoint_exists': False
    }
    
    try:
        if visited_urls_file.exists():
            with open(visited_urls_file, 'r') as f:
                data = json.load(f)
                info.update({
                    'pages_scraped': data.get('pages_scraped', 0),
                    'urls_visited': len(data.get('visited', [])),
                    'urls_failed': len(data.get('failed', [])),
                    'last_updated': data.get('last_updated'),
                    'checkpoint_exists': True
                })
        elif checkpoint_file.exists():
            with open(checkpoint_file, 'rb') as f:
                checkpoint = pickle.load(f)
                info.update({
                    'pages_scraped': checkpoint.get('pages_scraped', 0),
                    'urls_visited': len(checkpoint.get('visited_urls', [])),
                    'urls_failed': len(checkpoint.get('failed_urls', [])),
                    'last_updated': checkpoint.get('timestamp'),
                    'checkpoint_exists': True
                })
    except Exception as e:
        info['error'] = str(e)
        
    return info

def get_output_file_info():
    """Check output files status."""
    output_files = {
        'scraped_data.json': 'crawler/output/scraped_data.json',
        'text_files': 'crawler/output/text',
        'crawl_meta.json': 'crawler/src/crawl_meta.json'
    }
    
    file_info = {}
    for name, path in output_files.items():
        path_obj = Path(path)
        if path_obj.exists():
            if path_obj.is_file():
                file_info[name] = {
                    'exists': True,
                    'size_mb': path_obj.stat().st_size / 1024 / 1024,
                    'modified': datetime.fromtimestamp(path_obj.stat().st_mtime)
                }
            elif path_obj.is_dir():
                file_count = sum(1 for _ in path_obj.glob('*') if _.is_file())
                total_size = sum(f.stat().st_size for f in path_obj.glob('*') if f.is_file())
                file_info[name] = {
                    'exists': True,
                    'file_count': file_count,
                    'total_size_mb': total_size / 1024 / 1024,
                    'modified': datetime.fromtimestamp(path_obj.stat().st_mtime) if file_count > 0 else None
                }
        else:
            file_info[name] = {'exists': False}
            
    return file_info

def format_time_diff(timestamp_str):
    """Format time difference from timestamp string."""
    if not timestamp_str:
        return "Unknown"
    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        diff = datetime.now() - timestamp.replace(tzinfo=None)
        
        if diff.total_seconds() < 60:
            return f"{int(diff.total_seconds())}s ago"
        elif diff.total_seconds() < 3600:
            return f"{int(diff.total_seconds() / 60)}m ago"
        else:
            return f"{int(diff.total_seconds() / 3600)}h {int((diff.total_seconds() % 3600) / 60)}m ago"
    except:
        return "Unknown"

def print_status():
    """Print current status information."""
    print("\033[2J\033[H", end="")  # Clear screen and move cursor to top
    print("🕷️  CampusGPT Spider Monitor")
    print("=" * 60)
    print(f"⏰ Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Memory usage
    total_memory, processes = get_memory_usage()
    print(f"\n💾 Memory Usage:")
    if processes:
        print(f"   Total Spider Memory: {total_memory:.1f} MB")
        for proc in processes:
            print(f"   PID {proc['pid']}: {proc['memory_mb']:.1f} MB")
            if total_memory > 400:
                print("   ⚠️  HIGH MEMORY USAGE!")
    else:
        print("   No Scrapy processes detected")
    
    # Checkpoint info
    checkpoint_info = read_checkpoint_info()
    print(f"\n📊 Progress:")
    if checkpoint_info['checkpoint_exists']:
        print(f"   Pages scraped: {checkpoint_info['pages_scraped']}")
        print(f"   URLs visited: {checkpoint_info['urls_visited']}")
        print(f"   Failed URLs: {checkpoint_info['urls_failed']}")
        print(f"   Last updated: {format_time_diff(checkpoint_info['last_updated'])}")
        
        # Calculate rate
        if checkpoint_info['last_updated']:
            try:
                timestamp = datetime.fromisoformat(checkpoint_info['last_updated'].replace('Z', '+00:00'))
                elapsed = datetime.now() - timestamp.replace(tzinfo=None)
                if elapsed.total_seconds() > 0 and checkpoint_info['pages_scraped'] > 0:
                    rate = checkpoint_info['pages_scraped'] / (elapsed.total_seconds() / 60)
                    print(f"   Average rate: {rate:.1f} pages/min")
            except:
                pass
    else:
        print("   No checkpoint found - spider may not be running")
    
    # Output files
    output_info = get_output_file_info()
    print(f"\n📁 Output Files:")
    for name, info in output_info.items():
        if info['exists']:
            if 'size_mb' in info:
                print(f"   {name}: {info['size_mb']:.1f} MB ({format_time_diff(info['modified'].isoformat())})")
            elif 'file_count' in info:
                print(f"   {name}: {info['file_count']} files, {info['total_size_mb']:.1f} MB")
        else:
            print(f"   {name}: Not found")
    
    # System info
    system_info = psutil.virtual_memory()
    cpu_percent = psutil.cpu_percent()
    print(f"\n🖥️  System:")
    print(f"   CPU Usage: {cpu_percent}%")
    print(f"   RAM: {system_info.percent}% ({system_info.used / 1024**3:.1f}GB / {system_info.total / 1024**3:.1f}GB)")
    
    print(f"\n🔄 Monitoring... (Press Ctrl+C to stop)")

def main():
    print("🚀 Starting CampusGPT Spider Monitor...")
    print("This will refresh every 5 seconds.\n")
    
    try:
        while True:
            print_status()
            time.sleep(5)
    except KeyboardInterrupt:
        print("\n\n👋 Monitor stopped.")
    except Exception as e:
        print(f"\n❌ Monitor error: {e}")

if __name__ == "__main__":
    try:
        import psutil
    except ImportError:
        print("❌ psutil not installed. Install with: pip install psutil")
        exit(1)
        
    main()
