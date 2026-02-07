from musicdl import musicdl
from musicdl.modules.utils import SongInfo
from musicdl.modules.utils.misc import AudioLinkTester
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import os
import re
import time
import sys


#  Monkey-patch：禁用耗时的链接验证
_original_test = None
_original_probe = None

def fast_test(self, url, request_overrides=None):
    """快速验证，只返回基本信息，不发送HTTP请求"""
    return dict(ok=True, status=200, method="HEAD", final_url=url, 
                ctype="audio/mpeg", clen=None, range=True, fmt=None, reason="fast mode")

def fast_probe(self, url, request_overrides=None):
    """快速探测，不发送实际请求"""
    ext = url.split('?')[0].split('.')[-1] if '?' in url or '.' in url else 'mp3'
    return dict(file_size='NULL', ctype='audio/mpeg', ext=ext, download_url=url, final_url=url)

def enable_fast_mode():
    """启用快速搜索模式（跳过链接验证）"""
    global _original_test, _original_probe
    if _original_test is None:
        _original_test = AudioLinkTester.test
        _original_probe = AudioLinkTester.probe
    AudioLinkTester.test = fast_test
    AudioLinkTester.probe = fast_probe

def disable_fast_mode():
    """恢复正常的链接验证"""
    global _original_test, _original_probe
    if _original_test is not None and _original_probe is not None:
        AudioLinkTester.test = _original_test  # type: ignore
        AudioLinkTester.probe = _original_probe  # type: ignore


def sanitize_filename(filename):
    """清理文件名，移除非法字符"""
    illegal_chars = '<>:"/\\|?*'
    for char in illegal_chars:
        filename = filename.replace(char, '_')
    filename = ''.join(char for char in filename if ord(char) >= 32)
    filename = filename.strip(' .')
    return filename


def format_filename(song):
    """生成优化的文件名：歌手 - 歌曲名 (专辑) [音质].扩展名"""
    singer = song.singers or '未知歌手'
    songname = song.song_name or '未知歌曲'
    album = song.album or '未知专辑'
    ext = song.ext or 'mp3'
    
    quality = ''
    if hasattr(song, 'raw_data') and song.raw_data:
        download_data = song.raw_data.get('download', {})
        if isinstance(download_data, dict):
            data = download_data.get('data', {})
            if isinstance(data, dict):
                quality = data.get('quality', '')
    
    if quality:
        filename = f"{singer} - {songname} ({album}) [{quality}].{ext}"
    else:
        filename = f"{singer} - {songname} ({album}).{ext}"
    
    return sanitize_filename(filename)


def get_song_quality(song):
    """获取歌曲音质信息"""
    if hasattr(song, 'raw_data') and song.raw_data:
        download_data = song.raw_data.get('download', {})
        if isinstance(download_data, dict):
            data = download_data.get('data', {})
            if isinstance(data, dict):
                return data.get('quality', '未知音质')
    return '未知音质'


def get_song_size(song):
    """获取歌曲大小信息"""
    if hasattr(song, 'raw_data') and song.raw_data:
        download_data = song.raw_data.get('download', {})
        if isinstance(download_data, dict):
            data = download_data.get('data', {})
            if isinstance(data, dict):
                return data.get('size', song.file_size or '未知大小')
    return song.file_size or '未知大小'


def extract_song_info_from_filename(filename):
    """从文件名中提取歌手和歌名
    格式: "歌手 - 歌名 (专辑) [音质].扩展名"
    返回: (singer, songname) 或 None
    """
    # 移除扩展名
    name_without_ext = os.path.splitext(filename)[0]
    if not name_without_ext:
        return None
    
    # 尝试匹配 "歌手 - 歌名" 格式
    # 支持格式: "歌手 - 歌名", "歌手 - 歌名 (专辑)", "歌手 - 歌名 [音质]", "歌手 - 歌名 (专辑) [音质]"
    match = re.match(r'^(.+?)\s+-\s+(.+?)(?:\s*\(|\s*\[|$)', name_without_ext)
    if match:
        singer = match.group(1).strip()
        songname = match.group(2).strip()
        return (singer, songname)
    
    return None


def scan_existing_songs(directory):
    """扫描目录中已存在的歌曲
    返回: set((singer, songname))
    """
    existing_songs = set()
    
    if not os.path.exists(directory):
        return existing_songs
    
    # 支持的音频文件扩展名
    audio_extensions = {'.mp3', '.flac', '.wav', '.m4a', '.aac', '.ogg', '.wma', '.ape'}
    
    try:
        for filename in os.listdir(directory):
            # 检查是否是音频文件
            ext = os.path.splitext(filename)[1].lower()
            if ext in audio_extensions:
                info = extract_song_info_from_filename(filename)
                if info:
                    existing_songs.add(info)
                    
    except Exception as e:
        print(f"扫描目录时出错: {e}")
    
    return existing_songs


def is_song_exists(song, existing_songs):
    """检查歌曲是否已存在
    song: SongInfo 对象
    existing_songs: set((singer, songname))
    返回: bool
    """
    singer = song.singers or '未知歌手'
    songname = song.song_name or '未知歌曲'
    
    # 标准化处理：去除多余空格，统一大小写
    singer_normalized = singer.strip().lower()
    songname_normalized = songname.strip().lower()
    
    # 检查完全匹配
    if (singer_normalized, songname_normalized) in existing_songs:
        return True
    
    # 也检查非标准化版本
    if (singer.strip(), songname.strip()) in existing_songs:
        return True
    
    return False


def filter_duplicate_songs(songs, existing_songs):
    """过滤掉已存在的歌曲
    返回: (新歌曲列表, 跳过的歌曲数量)
    """
    new_songs = []
    skipped = 0
    
    for song in songs:
        if is_song_exists(song, existing_songs):
            skipped += 1
            print(f"  ⚠️  跳过重复: {song.singers} - {song.song_name}")
        else:
            new_songs.append(song)
    
    return new_songs, skipped


def print_progress_bar(current, total, prefix='', suffix='', length=50):
    """打印进度条"""
    if total == 0:
        return
    filled = int(length * current // total)
    bar = '█' * filled + '░' * (length - filled)
    percent = f"{100 * current / total:.1f}%"
    sys.stdout.write(f'\r{prefix} |{bar}| {percent} {suffix}')
    sys.stdout.flush()
    if current >= total:
        sys.stdout.write('\n')
        sys.stdout.flush()


def search_single_platform(client, source_name, keyword, progress_lock, completed_count, total_count):
    """搜索单个平台，带进度显示"""
    try:
        # 执行搜索
        result = client.music_clients[source_name].search(
            keyword=keyword,
            num_threadings=client.clients_threadings.get(source_name, 5)
        )
        
        # 更新进度
        with progress_lock:
            completed_count[0] += 1
            count = completed_count[0]
            print(f"\n✓ [{count}/{total_count}] {source_name} 完成 - 找到 {len(result)} 首")
        
        return source_name, result
    except Exception as e:
        with progress_lock:
            completed_count[0] += 1
            count = completed_count[0]
            print(f"\n✗ [{count}/{total_count}] {source_name} 失败: {str(e)[:50]}")
        return source_name, []


def parallel_search(music_client, sources, keyword, search_size):
    """并行搜索多个平台，实时显示进度"""
    print(f"\n{'=' * 80}")
    print(f"🔍 开始并行搜索: '{keyword}'")
    print(f"   平台数: {len(sources)} | 每平台: {search_size} 结果")
    print('=' * 80)
    
    start_time = time.time()
    results = {}
    progress_lock = Lock()
    completed_count = [0]
    total_count = len(sources)
    
    # 使用线程池并行搜索
    with ThreadPoolExecutor(max_workers=min(len(sources), 10)) as executor:
        # 提交所有搜索任务
        future_to_source = {
            executor.submit(
                search_single_platform,
                music_client,
                source,
                keyword,
                progress_lock,
                completed_count,
                total_count
            ): source for source in sources
        }
        
        # 收集结果
        for future in as_completed(future_to_source):
            source_name, result = future.result()
            results[source_name] = result
    
    elapsed = time.time() - start_time
    total_songs = sum(len(songs) for songs in results.values())
    print(f"\n{'=' * 80}")
    print(f"✅ 搜索完成！耗时 {elapsed:.1f} 秒 | 共找到 {total_songs} 首")
    print('=' * 80)
    
    return results


def download_single_song(music_client, song, save_dir, completed_count, total_count, download_lock):
    """下载单首歌曲，带进度显示"""
    try:
        # 设置保存路径
        filename = format_filename(song)
        song.work_dir = save_dir
        song._save_path = os.path.join(save_dir, filename)
        
        source = song.source
        
        # 执行下载
        with download_lock:
            current = completed_count[0] + 1
            print(f"\n[{current}/{total_count}] 📥 正在下载: {filename[:60]}...")
        
        music_client.music_clients[source].download(
            song_infos=[song],
            num_threadings=1  # 单首歌曲单线程
        )
        
        with download_lock:
            completed_count[0] += 1
            current = completed_count[0]
            if os.path.exists(song._save_path):
                file_size = os.path.getsize(song._save_path)
                size_mb = file_size / 1024 / 1024
                print(f"   ✓ 完成 ({size_mb:.2f} MB) - {filename[:50]}...")
            else:
                print(f"   ? 文件未找到 - {filename[:50]}...")
        
        return True
    except Exception as e:
        with download_lock:
            completed_count[0] += 1
            print(f"   ✗ 失败: {str(e)[:80]}")
        return False


def parallel_download(music_client, songs, save_dir, thread_count):
    """并行下载多首歌曲，实时显示进度"""
    if not songs:
        return
    
    print(f"\n{'=' * 80}")
    print(f"⬇️  开始并行下载")
    print(f"   歌曲数: {len(songs)} | 线程数: {thread_count}")
    print(f"   保存到: {save_dir}")
    print('=' * 80)
    
    os.makedirs(save_dir, exist_ok=True)
    start_time = time.time()
    completed_count = [0]
    total_count = len(songs)
    download_lock = Lock()
    
    # 使用线程池并行下载
    with ThreadPoolExecutor(max_workers=thread_count) as executor:
        futures = [
            executor.submit(
                download_single_song,
                music_client,
                song,
                save_dir,
                completed_count,
                total_count,
                download_lock
            ) for song in songs
        ]
        
        # 等待所有下载完成
        for future in as_completed(futures):
            future.result()
    
    elapsed = time.time() - start_time
    print(f"\n{'=' * 80}")
    print(f"✅ 下载完成！耗时 {elapsed:.1f} 秒 | 共 {total_count} 首")
    print('=' * 80)


def main():
    # 定义所有可用平台
    all_sources = {
        '1': ('KugouMusicClient', '酷狗音乐'),
        '2': ('NeteaseMusicClient', '网易云音乐'),
        '3': ('QQMusicClient', 'QQ音乐'),
        '4': ('KuwoMusicClient', '酷我音乐'),
        '5': ('MiguMusicClient', '咪咕音乐'),
        '6': ('QianqianMusicClient', '千千音乐'),
    }

    # 显示平台选项
    print("=" * 80)
    print("🎵 音乐下载器 (真·并行版)")
    print("=" * 80)
    
    # 选择搜索模式
    print("\n⚡ 搜索模式：")
    print("  [1] 极速模式 - 跳过链接验证，搜索快3-5倍（推荐）")
    print("  [2] 标准模式 - 完整验证，搜索慢但更稳定")
    mode_input = input("请选择模式（默认1）：").strip()
    
    if mode_input == '2':
        print("已选择：标准模式")
    else:
        enable_fast_mode()
        print("已选择：⚡ 极速模式（跳过链接预验证）")
    
    print("\n可用音乐平台：")
    for key, (_, name) in all_sources.items():
        print(f"  [{key}] {name}")
    print("  [0] 使用全部平台")

    # 选择平台
    platform_input = input("\n请选择平台编号（多个用逗号分隔，如 1,2,3）：").strip()

    if platform_input == '0':
        selected_sources = [src for src, _ in all_sources.values()]
        print(f"已选择: 全部 {len(selected_sources)} 个平台")
    else:
        selected_keys = [x.strip() for x in platform_input.split(',')]
        selected_sources = [all_sources[k][0] for k in selected_keys if k in all_sources]
        selected_names = [all_sources[k][1] for k in selected_keys if k in all_sources]
        print(f"已选择: {', '.join(selected_names)} ({len(selected_sources)} 个平台)")

    if not selected_sources:
        print("未选择有效平台")
        return

    # 配置参数
    search_size = input("\n每平台搜索结果数（默认5）：").strip()
    search_size = int(search_size) if search_size.isdigit() else 5
    
    download_threads = input("并行下载线程数（默认5）：").strip()
    download_threads = int(download_threads) if download_threads.isdigit() else 5
    
    # 初始化客户端配置
    print(f"\n正在初始化 {len(selected_sources)} 个平台...")
    init_clients_cfg = {
        source: {
            'search_size_per_source': search_size,
            'search_size_per_page': min(search_size, 20),
            'max_retries': 2,
            'maintain_session': True,
            'disable_print': True,
        }
        for source in selected_sources
    }
    
    # 每个平台的线程配置（搜索用）
    clients_threadings = {source: 3 for source in selected_sources}
    
    music_client = musicdl.MusicClient(
        music_sources=selected_sources,
        init_music_clients_cfg=init_clients_cfg,
        clients_threadings=clients_threadings
    )

    # 输入搜索关键词
    keyword = input("\n请输入要搜索的歌曲名称：").strip()
    if not keyword:
        print("搜索词不能为空")
        return

    # 选择保存目录（提前询问，用于重复检测）
    user_music_dir = os.path.join(os.path.expanduser("~"), "Music")
    if not os.path.exists(user_music_dir):
        user_music_dir = os.getcwd()
    
    print(f"\n默认保存位置: {user_music_dir}")
    save_dir_input = input(f"请输入保存目录（直接回车使用默认，或输入 . 使用当前目录）：").strip()
    
    if save_dir_input == '.':
        save_dir = os.getcwd()
    elif save_dir_input:
        save_dir = save_dir_input
    else:
        save_dir = user_music_dir
    
    os.makedirs(save_dir, exist_ok=True)
    
    # 扫描已存在的歌曲
    print(f"\n📂 正在扫描目录: {save_dir}")
    existing_songs = scan_existing_songs(save_dir)
    if existing_songs:
        print(f"   发现 {len(existing_songs)} 首已存在的歌曲")
    else:
        print(f"   目录为空或无音频文件")
    
    # 执行并行搜索
    search_results = parallel_search(music_client, selected_sources, keyword, search_size)

    # 收集所有歌曲
    all_songs = []
    for source_name, song_list in search_results.items():
        for song in song_list:
            song._source_platform = source_name
            all_songs.append(song)
    
    # 过滤重复歌曲
    if existing_songs:
        print(f"\n🔄 正在过滤重复歌曲...")
        all_songs, skipped_count = filter_duplicate_songs(all_songs, existing_songs)
        if skipped_count > 0:
            print(f"   已跳过 {skipped_count} 首重复歌曲")

    if not all_songs:
        print("\n⚠️ 未找到任何新歌曲（所有结果都已存在）")
        return

    # 显示结果
    print(f"\n{'=' * 80}")
    print("📋 搜索结果详情")
    print("=" * 80)
    
    for idx, song in enumerate(all_songs):
        singer = song.singers or '未知歌手'
        songname = song.song_name or '未知歌曲'
        album = song.album or '未知专辑'
        duration = song.duration or '未知时长'
        ext = song.ext or 'mp3'
        quality = get_song_quality(song)
        size = get_song_size(song)
        
        print(f"\n[{idx:2d}] 🎵 {singer} - {songname}")
        print(f"     💿 {album} | ⏱️ {duration} | 🎧 {quality} | 💾 {size} | 📦 {ext.upper()}")
        print(f"     🌐 {song._source_platform}")

    # 选择下载
    print(f"\n{'=' * 80}")
    print(f"📊 总计 {len(all_songs)} 首歌曲")
    print("=" * 80)

    user_input = input("\n请输入要下载的歌曲编号（多个用逗号分隔，如 0,2,3，输入 'all' 下载全部）：").strip()

    try:
        if user_input.lower() == 'all':
            selected_songs = all_songs
        else:
            indices = [int(x.strip()) for x in user_input.split(',')]
            selected_songs = [all_songs[i] for i in indices]

        # 再次扫描已存在的歌曲（以防在搜索期间有新文件）
        existing_songs = scan_existing_songs(save_dir)
        
        # 过滤掉已存在的歌曲
        new_songs = []
        skipped_in_selection = 0
        for song in selected_songs:
            if is_song_exists(song, existing_songs):
                skipped_in_selection += 1
                print(f"  ⚠️  跳过已存在: {song.singers} - {song.song_name}")
            else:
                new_songs.append(song)
        
        if skipped_in_selection > 0:
            print(f"\n   共跳过 {skipped_in_selection} 首已存在的歌曲")
        
        if not new_songs:
            print("\n⚠️ 所有选中的歌曲都已存在，无需下载")
            return
        
        selected_songs = new_songs

        confirm = input(f"\n准备下载 {len(selected_songs)} 首歌曲到 {save_dir}，确认？(y/n): ").strip().lower()
        
        if confirm == 'y':
            # 执行并行下载
            parallel_download(music_client, selected_songs, save_dir, download_threads)
            
            # 显示最终文件列表
            print("\n📁 已下载文件：")
            success_count = 0
            for song in selected_songs:
                if song._save_path and os.path.exists(song._save_path):
                    file_size = os.path.getsize(song._save_path)
                    print(f"  ✓ {os.path.basename(song._save_path)} ({file_size / 1024 / 1024:.2f} MB)")
                    success_count += 1
                else:
                    print(f"  ✗ {os.path.basename(song._save_path)} (下载失败)")
            
            print(f"\n成功: {success_count}/{len(selected_songs)} 首")
        else:
            print("已取消下载")

    except (ValueError, IndexError) as e:
        print(f"输入错误: {e}")
    except Exception as e:
        print(f"发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
