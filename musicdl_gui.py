"""
音乐下载器 GUI 版本 - 并行实时版
基于 musicdl 库的图形界面应用
支持：实时并行搜索、进度显示、每平台独立结果
"""
import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from threading import Thread, Lock
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from musicdl import musicdl
from musicdl.modules.utils.misc import AudioLinkTester


# ========== Monkey Patch: 禁用链接验证加速搜索 ==========
_original_test = None
_original_probe = None

def fast_test(self, url, request_overrides=None):
    """快速验证，不发送HTTP请求"""
    return dict(ok=True, status=200, method="HEAD", final_url=url,
                ctype="audio/mpeg", clen=None, range=True, fmt=None, reason="fast mode")

def fast_probe(self, url, request_overrides=None):
    """快速探测，不发送实际请求"""
    ext = url.split('?')[0].split('.')[-1] if '?' in url or '.' in url else 'mp3'
    return dict(file_size='NULL', ctype='audio/mpeg', ext=ext, download_url=url, final_url=url)

def enable_fast_mode():
    global _original_test, _original_probe
    if _original_test is None:
        _original_test = AudioLinkTester.test
        _original_probe = AudioLinkTester.probe
    AudioLinkTester.test = fast_test
    AudioLinkTester.probe = fast_probe

def disable_fast_mode():
    global _original_test, _original_probe
    if _original_test is not None and _original_probe is not None:
        AudioLinkTester.test = _original_test
        AudioLinkTester.probe = _original_probe
# =========================================================


class MusicDownloaderGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("🎵 音乐下载器 - 并行实时版")
        self.root.geometry("1100x750")
        self.root.minsize(1000, 650)
        
        # 配置样式
        self.style = ttk.Style()
        self.style.configure("Title.TLabel", font=("Microsoft YaHei", 16, "bold"))
        self.style.configure("Header.TLabel", font=("Microsoft YaHei", 10, "bold"))
        self.style.configure("Info.TLabel", font=("Microsoft YaHei", 9))
        
        # 初始化变量
        self.music_client = None
        self.all_songs = []
        self.search_queue = queue.Queue()
        self.download_queue = queue.Queue()
        self.searching = False
        self.downloading = False
        
        # 平台配置 - 所有平台
        self.all_sources = {
            'KugouMusicClient': {'name': '酷狗音乐', 'var': tk.BooleanVar(value=True)},
            'NeteaseMusicClient': {'name': '网易云音乐', 'var': tk.BooleanVar(value=True)},
            'QQMusicClient': {'name': 'QQ音乐', 'var': tk.BooleanVar(value=False)},
            'KuwoMusicClient': {'name': '酷我音乐', 'var': tk.BooleanVar(value=False)},
            'MiguMusicClient': {'name': '咪咕音乐', 'var': tk.BooleanVar(value=False)},
            'QianqianMusicClient': {'name': '千千音乐', 'var': tk.BooleanVar(value=False)},
        }
        
        self.setup_ui()
        self.update_ui()
        
    def setup_ui(self):
        """设置界面布局"""
        # 主容器
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(4, weight=1)  # 结果区域可扩展
        
        # ===== 标题 =====
        title_label = ttk.Label(
            main_frame, 
            text="🎵 音乐下载器 - 并行实时版", 
            style="Title.TLabel"
        )
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 10))
        
        # ===== 平台选择区 =====
        platform_frame = ttk.LabelFrame(main_frame, text="选择音乐平台", padding="10")
        platform_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        platform_frame.columnconfigure(0, weight=1)
        
        # 平台复选框
        col = 0
        for source_id, source_info in self.all_sources.items():
            cb = ttk.Checkbutton(
                platform_frame, 
                text=source_info['name'], 
                variable=source_info['var']
            )
            cb.grid(row=0, column=col, padx=10, pady=5, sticky=tk.W)
            col += 1
            if col > 5:
                col = 0
        
        # 全选/取消按钮
        btn_frame = ttk.Frame(platform_frame)
        btn_frame.grid(row=1, column=0, columnspan=6, pady=(5, 0))
        
        ttk.Button(btn_frame, text="全选", command=self.select_all_platforms, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消全选", command=self.deselect_all_platforms, width=8).pack(side=tk.LEFT, padx=5)
        
        # ===== 搜索区 =====
        search_frame = ttk.LabelFrame(main_frame, text="搜索设置", padding="10")
        search_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        search_frame.columnconfigure(1, weight=1)
        
        # 搜索输入
        ttk.Label(search_frame, text="歌曲名称：").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.search_entry = ttk.Entry(search_frame, font=("Microsoft YaHei", 10))
        self.search_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5, pady=5)
        self.search_entry.bind('<Return>', lambda e: self.start_search())
        
        # 搜索按钮
        self.search_btn = ttk.Button(search_frame, text="🔍 开始搜索", command=self.start_search, width=12)
        self.search_btn.grid(row=0, column=2, padx=5, pady=5)
        
        # 配置选项
        config_frame = ttk.Frame(search_frame)
        config_frame.grid(row=1, column=0, columnspan=3, pady=5, sticky=tk.W)
        
        ttk.Label(config_frame, text="每平台结果数：").pack(side=tk.LEFT)
        self.search_size_var = tk.StringVar(value="5")
        search_size_spin = ttk.Spinbox(config_frame, from_=1, to=20, textvariable=self.search_size_var, width=5)
        search_size_spin.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(config_frame, text="搜索模式：").pack(side=tk.LEFT, padx=(20, 0))
        self.search_mode_var = tk.StringVar(value="fast")
        ttk.Radiobutton(config_frame, text="⚡ 极速", variable=self.search_mode_var, value="fast").pack(side=tk.LEFT)
        ttk.Radiobutton(config_frame, text="标准", variable=self.search_mode_var, value="normal").pack(side=tk.LEFT, padx=5)
        
        ttk.Label(config_frame, text="下载线程数：").pack(side=tk.LEFT, padx=(20, 0))
        self.thread_count_var = tk.StringVar(value="5")
        thread_count_spin = ttk.Spinbox(config_frame, from_=1, to=20, textvariable=self.thread_count_var, width=5)
        thread_count_spin.pack(side=tk.LEFT, padx=5)
        
        # ===== 搜索进度区 =====
        progress_frame = ttk.LabelFrame(main_frame, text="搜索进度", padding="10")
        progress_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        progress_frame.columnconfigure(0, weight=1)
        
        # 总体进度条
        self.search_progress_var = tk.DoubleVar(value=0)
        self.search_progress_bar = ttk.Progressbar(progress_frame, variable=self.search_progress_var, maximum=100, mode='determinate')
        self.search_progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # 状态文本
        self.search_status_var = tk.StringVar(value="就绪")
        ttk.Label(progress_frame, textvariable=self.search_status_var).grid(row=1, column=0, sticky=tk.W)
        
        # ===== 结果显示区 =====
        result_frame = ttk.LabelFrame(main_frame, text="搜索结果 (实时更新)", padding="10")
        result_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        result_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        
        # 创建Treeview
        columns = ('序号', '歌手', '歌曲', '专辑', '时长', '音质', '大小', '格式', '来源')
        self.tree = ttk.Treeview(result_frame, columns=columns, show='headings', height=12)
        
        # 设置列宽
        self.tree.column('序号', width=40, anchor='center')
        self.tree.column('歌手', width=120)
        self.tree.column('歌曲', width=150)
        self.tree.column('专辑', width=120)
        self.tree.column('时长', width=60, anchor='center')
        self.tree.column('音质', width=80, anchor='center')
        self.tree.column('大小', width=60, anchor='center')
        self.tree.column('格式', width=50, anchor='center')
        self.tree.column('来源', width=80, anchor='center')
        
        # 设置表头
        for col in columns:
            self.tree.heading(col, text=col)
        
        # 滚动条
        scrollbar_y = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(result_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
        
        self.tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar_y.grid(row=0, column=1, sticky=(tk.N, tk.S))
        scrollbar_x.grid(row=1, column=0, sticky=(tk.W, tk.E))
        
        # 结果操作按钮
        result_btn_frame = ttk.Frame(result_frame)
        result_btn_frame.grid(row=2, column=0, columnspan=2, pady=(5, 0))
        
        ttk.Button(result_btn_frame, text="全选", command=self.select_all_songs, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(result_btn_frame, text="取消选择", command=self.deselect_all_songs, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(result_btn_frame, text="反选", command=self.invert_selection, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(result_btn_frame, text="清空结果", command=self.clear_results, width=10).pack(side=tk.LEFT, padx=5)
        
        # ===== 下载控制区 =====
        download_frame = ttk.LabelFrame(main_frame, text="下载设置", padding="10")
        download_frame.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        download_frame.columnconfigure(0, weight=1)
        
        # 保存路径
        path_frame = ttk.Frame(download_frame)
        path_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 5))
        path_frame.columnconfigure(0, weight=1)
        
        ttk.Label(path_frame, text="保存路径：").pack(side=tk.LEFT)
        self.save_path_var = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Music"))
        self.path_entry = ttk.Entry(path_frame, textvariable=self.save_path_var, font=("Microsoft YaHei", 9))
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(path_frame, text="浏览...", command=self.browse_folder, width=8).pack(side=tk.LEFT)
        
        # 下载进度条
        self.download_progress_var = tk.DoubleVar(value=0)
        self.download_progress_bar = ttk.Progressbar(download_frame, variable=self.download_progress_var, maximum=100, mode='determinate')
        self.download_progress_bar.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        
        # 下载按钮
        self.download_btn = ttk.Button(
            download_frame, 
            text="⬇️ 开始下载", 
            command=self.start_download,
            width=20
        )
        self.download_btn.grid(row=2, column=0, pady=(5, 0))
        
        # ===== 状态栏 =====
        status_frame = ttk.Frame(main_frame, relief=tk.SUNKEN)
        status_frame.grid(row=6, column=0, columnspan=2, sticky=(tk.W, tk.E))
        status_frame.columnconfigure(0, weight=1)
        
        self.status_var = tk.StringVar(value="就绪 - 请选择平台并输入歌曲名称")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, padding=(5, 2))
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        self.count_label = ttk.Label(status_frame, text="找到 0 首歌曲", padding=(5, 2))
        self.count_label.grid(row=0, column=2)
        
    def select_all_platforms(self):
        """全选平台"""
        for source_info in self.all_sources.values():
            source_info['var'].set(True)
            
    def deselect_all_platforms(self):
        """取消全选平台"""
        for source_info in self.all_sources.values():
            source_info['var'].set(False)
            
    def select_all_songs(self):
        """全选歌曲"""
        for item in self.tree.get_children():
            self.tree.selection_add(item)
            
    def deselect_all_songs(self):
        """取消选择所有歌曲"""
        self.tree.selection_remove(self.tree.selection())
        
    def invert_selection(self):
        """反选歌曲"""
        all_items = self.tree.get_children()
        selected = set(self.tree.selection())
        
        for item in all_items:
            if item in selected:
                self.tree.selection_remove(item)
            else:
                self.tree.selection_add(item)
    
    def clear_results(self):
        """清空结果"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.all_songs.clear()
        self.count_label.config(text="找到 0 首歌曲")
                
    def browse_folder(self):
        """浏览文件夹"""
        folder = filedialog.askdirectory(initialdir=self.save_path_var.get())
        if folder:
            self.save_path_var.set(folder)
            
    def get_selected_platforms(self):
        """获取选中的平台"""
        selected = []
        for source_id, source_info in self.all_sources.items():
            if source_info['var'].get():
                selected.append(source_id)
        return selected
    
    def get_song_quality(self, song):
        """获取歌曲音质"""
        if hasattr(song, 'raw_data') and song.raw_data:
            download_data = song.raw_data.get('download', {})
            if isinstance(download_data, dict):
                data = download_data.get('data', {})
                if isinstance(data, dict):
                    return data.get('quality', '-')
        return '-'
        
    def get_song_size(self, song):
        """获取歌曲大小"""
        if hasattr(song, 'raw_data') and song.raw_data:
            download_data = song.raw_data.get('download', {})
            if isinstance(download_data, dict):
                data = download_data.get('data', {})
                if isinstance(data, dict):
                    return data.get('size', song.file_size or '-')
        return song.file_size or '-'
    
    def format_filename(self, song):
        """格式化文件名"""
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
            
        # 清理非法字符
        illegal_chars = '<>:"/\\|?*'
        for char in illegal_chars:
            filename = filename.replace(char, '_')
        filename = ''.join(char for char in filename if ord(char) >= 32)
        filename = filename.strip(' .')
        
        return filename
    
    def extract_song_info_from_filename(self, filename):
        """从文件名中提取歌手和歌名"""
        import re
        name_without_ext = os.path.splitext(filename)[0]
        if not name_without_ext:
            return None
        
        match = re.match(r'^(.+?)\s+-\s+(.+?)(?:\s*\(|\s*\[|$)', name_without_ext)
        if match:
            singer = match.group(1).strip()
            songname = match.group(2).strip()
            return (singer.lower(), songname.lower())
        
        return None
    
    def scan_existing_songs(self, directory):
        """扫描目录中已存在的歌曲"""
        existing_songs = set()
        
        if not os.path.exists(directory):
            return existing_songs
        
        audio_extensions = {'.mp3', '.flac', '.wav', '.m4a', '.aac', '.ogg', '.wma', '.ape'}
        
        try:
            for filename in os.listdir(directory):
                ext = os.path.splitext(filename)[1].lower()
                if ext in audio_extensions:
                    info = self.extract_song_info_from_filename(filename)
                    if info:
                        existing_songs.add(info)
        except Exception:
            pass
        
        return existing_songs
    
    def is_song_exists(self, song, existing_songs):
        """检查歌曲是否已存在"""
        singer = (song.singers or '未知歌手').strip().lower()
        songname = (song.song_name or '未知歌曲').strip().lower()
        
        return (singer, songname) in existing_songs
    
    def filter_duplicate_songs(self, songs, save_dir):
        """过滤掉已存在的歌曲，返回新歌曲列表和跳过的数量"""
        existing_songs = self.scan_existing_songs(save_dir)
        
        if not existing_songs:
            return songs, 0, 0
        
        new_songs = []
        skipped = 0
        
        for song in songs:
            if self.is_song_exists(song, existing_songs):
                skipped += 1
            else:
                new_songs.append(song)
        
        return new_songs, skipped, len(existing_songs)
        
    def start_search(self):
        """开始搜索"""
        if self.searching:
            return
            
        keyword = self.search_entry.get().strip()
        if not keyword:
            messagebox.showwarning("警告", "请输入歌曲名称")
            return
            
        selected_platforms = self.get_selected_platforms()
        if not selected_platforms:
            messagebox.showwarning("警告", "请至少选择一个平台")
            return
        
        # 检查是否极速模式
        if self.search_mode_var.get() == "fast":
            enable_fast_mode()
        else:
            disable_fast_mode()
            
        # 清空之前的结果
        self.clear_results()
        
        # 设置搜索状态
        self.searching = True
        self.search_btn.config(state='disabled')
        self.search_progress_var.set(0)
        self.search_status_var.set(f"准备搜索: {keyword}")
        
        # 在新线程中执行搜索
        Thread(target=self.search_thread, args=(keyword, selected_platforms), daemon=True).start()
    
    def search_single_platform(self, source_name, keyword, search_size, progress_lock, completed_count, total_count):
        """搜索单个平台"""
        try:
            # 初始化单个客户端
            init_cfg = {
                'search_size_per_source': search_size,
                'search_size_per_page': min(search_size, 20),
                'max_retries': 2,
                'maintain_session': True,
                'disable_print': True,
            }
            
            # 创建独立客户端
            from musicdl.modules.sources import BuildMusicClient
            client = BuildMusicClient(module_cfg={'type': source_name, **init_cfg})
            
            # 执行搜索
            results = client.search(keyword=keyword, num_threadings=3)
            
            # 更新进度并通知UI
            with progress_lock:
                completed_count[0] += 1
                progress = (completed_count[0] / total_count) * 100
                self.search_queue.put(('platform_done', source_name, results, progress, completed_count[0], total_count))
            
            return source_name, results
        except Exception as e:
            with progress_lock:
                completed_count[0] += 1
                progress = (completed_count[0] / total_count) * 100
                self.search_queue.put(('platform_error', source_name, str(e), progress, completed_count[0], total_count))
            return source_name, []
    
    def search_thread(self, keyword, selected_platforms):
        """搜索线程 - 真正的并行搜索"""
        try:
            search_size = int(self.search_size_var.get())
            total_count = len(selected_platforms)
            
            self.search_queue.put(('status', f"开始并行搜索 '{keyword}' - {total_count} 个平台"))
            
            # 使用线程池并行搜索所有平台
            progress_lock = Lock()
            completed_count = [0]
            
            with ThreadPoolExecutor(max_workers=min(total_count, 6)) as executor:
                futures = {
                    executor.submit(
                        self.search_single_platform,
                        source,
                        keyword,
                        search_size,
                        progress_lock,
                        completed_count,
                        total_count
                    ): source for source in selected_platforms
                }
                
                # 等待所有搜索完成
                for future in as_completed(futures):
                    future.result()
            
            self.search_queue.put(('complete', len(self.all_songs)))
            
        except Exception as e:
            self.search_queue.put(('error', str(e)))
        finally:
            self.searching = False
            self.search_queue.put(('done', None))
    
    def update_ui(self):
        """更新UI（主线程）"""
        try:
            while not self.search_queue.empty():
                msg = self.search_queue.get_nowait()
                msg_type = msg[0]
                
                if msg_type == 'status':
                    self.search_status_var.set(msg[1])
                    
                elif msg_type == 'platform_done':
                    # 单个平台搜索完成，过滤重复后显示
                    _, source_name, results, progress, completed, total = msg
                    
                    # 过滤已存在的歌曲
                    save_dir = self.save_path_var.get()
                    filtered_results, skipped, existing_count = self.filter_duplicate_songs(results, save_dir)
                    
                    self.search_progress_var.set(progress)
                    if skipped > 0:
                        self.search_status_var.set(f"[{completed}/{total}] {source_name} 完成 - {len(results)} 首 (跳过 {skipped} 首重复)")
                    else:
                        self.search_status_var.set(f"[{completed}/{total}] {source_name} 完成 - 找到 {len(results)} 首")
                    
                    self.add_platform_results(source_name, filtered_results)
                    
                elif msg_type == 'platform_error':
                    # 平台搜索失败
                    _, source_name, error, progress, completed, total = msg
                    self.search_progress_var.set(progress)
                    self.search_status_var.set(f"[{completed}/{total}] {source_name} 失败: {error[:30]}")
                    
                elif msg_type == 'complete':
                    _, total_songs = msg
                    self.search_status_var.set(f"✅ 搜索完成！共找到 {total_songs} 首歌曲")
                    messagebox.showinfo("搜索完成", f"共找到 {total_songs} 首歌曲")
                    
                elif msg_type == 'error':
                    _, error = msg
                    messagebox.showerror("错误", f"搜索失败: {error}")
                    
                elif msg_type == 'done':
                    self.search_btn.config(state='normal')
                    self.searching = False
                    
        except queue.Empty:
            pass
        
        # 检查下载队列
        try:
            while not self.download_queue.empty():
                msg = self.download_queue.get_nowait()
                msg_type = msg[0]
                
                if msg_type == 'progress':
                    _, current, total, filename = msg
                    progress = (current / total) * 100 if total > 0 else 0
                    self.download_progress_var.set(progress)
                    self.status_var.set(f"下载中 [{current}/{total}]: {filename[:40]}...")
                    
                elif msg_type == 'complete':
                    _, success_count, total = msg
                    self.download_progress_var.set(100)
                    self.status_var.set(f"✅ 下载完成！成功 {success_count}/{total}")
                    messagebox.showinfo("下载完成", f"成功下载 {success_count}/{total} 首歌曲")
                    self.download_btn.config(state='normal')
                    self.downloading = False
                    
                elif msg_type == 'error':
                    _, error = msg
                    messagebox.showerror("错误", error)
                    self.download_btn.config(state='normal')
                    self.downloading = False
                    
        except queue.Empty:
            pass
            
        self.root.after(100, self.update_ui)
    
    def add_platform_results(self, source_name, songs):
        """添加单个平台的结果到列表（实时显示）"""
        for song in songs:
            song._source_platform = source_name
            idx = len(self.all_songs)
            song._global_idx = idx
            
            # 获取详细信息
            quality = self.get_song_quality(song)
            size = self.get_song_size(song)
            
            # 插入到Treeview
            self.tree.insert('', tk.END, values=(
                idx,
                song.singers or '未知歌手',
                song.song_name or '未知歌曲',
                song.album or '未知专辑',
                song.duration or '未知时长',
                quality,
                size,
                (song.ext or 'mp3').upper(),
                source_name.replace('MusicClient', '')
            ))
            
            self.all_songs.append(song)
        
        # 更新计数
        self.count_label.config(text=f"找到 {len(self.all_songs)} 首歌曲")
        
        # 自动滚动到最新结果
        if songs:
            self.tree.see(self.tree.get_children()[-1])
    
    def start_download(self):
        """开始下载"""
        if self.downloading:
            return
            
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("警告", "请至少选择一首歌曲")
            return
            
        save_dir = self.save_path_var.get()
        if not os.path.exists(save_dir):
            try:
                os.makedirs(save_dir, exist_ok=True)
            except Exception as e:
                messagebox.showerror("错误", f"无法创建保存目录: {e}")
                return
        
        # 获取选中的歌曲
        selected_songs = []
        for item in selected_items:
            values = self.tree.item(item, 'values')
            idx = int(values[0])
            if 0 <= idx < len(self.all_songs):
                selected_songs.append(self.all_songs[idx])
        
        if not selected_songs:
            messagebox.showwarning("警告", "未找到选中的歌曲")
            return
        
        # 再次检查重复（以防搜索后有新文件）
        existing_songs = self.scan_existing_songs(save_dir)
        new_songs = []
        skipped = 0
        for song in selected_songs:
            if self.is_song_exists(song, existing_songs):
                skipped += 1
            else:
                new_songs.append(song)
        
        if skipped > 0:
            if not new_songs:
                messagebox.showinfo("提示", f"选中的 {skipped} 首歌曲都已存在，无需下载")
                return
            else:
                result = messagebox.askyesno(
                    "重复提示",
                    f"选中的歌曲中有 {skipped} 首已存在\n是否只下载剩余 {len(new_songs)} 首新歌曲？"
                )
                if not result:
                    return
                selected_songs = new_songs
                messagebox.showinfo("继续下载", f"将下载 {len(selected_songs)} 首新歌曲")
        
        # 设置下载状态
        self.downloading = True
        self.download_btn.config(state='disabled')
        self.download_progress_var.set(0)
        
        # 在新线程中执行下载
        Thread(target=self.download_thread, args=(selected_songs, save_dir), daemon=True).start()
    
    def download_thread(self, songs, save_dir):
        """下载线程 - 并行下载"""
        try:
            thread_count = int(self.thread_count_var.get())
            total = len(songs)
            completed = [0]
            success_count = [0]
            download_lock = Lock()
            
            def download_single(song):
                try:
                    # 设置保存路径
                    filename = self.format_filename(song)
                    song.work_dir = save_dir
                    song._save_path = os.path.join(save_dir, filename)
                    
                    # 通知UI开始下载
                    with download_lock:
                        completed[0] += 1
                        current = completed[0]
                    self.download_queue.put(('progress', current, total, filename))
                    
                    # 获取平台客户端
                    source = song.source
                    if source in self.all_sources:
                        from musicdl.modules.sources import BuildMusicClient
                        client = BuildMusicClient(module_cfg={'type': source, 'disable_print': True})
                        client.download(song_infos=[song], num_threadings=1)
                    
                    # 检查是否成功
                    if os.path.exists(song._save_path):
                        with download_lock:
                            success_count[0] += 1
                    
                    return True
                except Exception as e:
                    print(f"下载失败 {song.song_name}: {e}")
                    return False
            
            # 使用线程池并行下载
            with ThreadPoolExecutor(max_workers=thread_count) as executor:
                futures = [executor.submit(download_single, song) for song in songs]
                for future in as_completed(futures):
                    future.result()
            
            self.download_queue.put(('complete', success_count[0], total))
            
        except Exception as e:
            self.download_queue.put(('error', f"下载失败: {str(e)}"))


def main():
    root = tk.Tk()
    app = MusicDownloaderGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
