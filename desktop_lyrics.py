import sys
import json
import websocket
import os
from PyQt6.QtGui import QPainter, QFont, QColor, QLinearGradient, QFontMetrics, QAction, QIcon
from PyQt6.QtWidgets import QApplication, QLabel, QWidget, QHBoxLayout, QGraphicsOpacityEffect, QSystemTrayIcon, QMenu, QStyle
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRect, QTimer, QPropertyAnimation, QEasingCurve, QPoint, pyqtProperty
import ctypes

# ================= 配置区域 =================
WS_URL = "ws://127.0.0.1:25885" 
CONFIG_FILE = "lyric_config.json"
DEFAULT_CONFIG = {
    "main_font_size": 24,
    "trans_font_size": 13,
    "bg_font_size": 14,
    "main_size_no_bg": 24,
    "main_size_with_bg": 17,
    "font_family": "Microsoft YaHei UI",
    "window_width": 1200
} 
# ===========================================

class WebSocketWorker(QThread):
    signal_lyric_data = pyqtSignal(list, bool)  # (歌词数据, 是否为逐字模式)
    signal_progress = pyqtSignal(int)
    signal_song_info = pyqtSignal(str)
    signal_status = pyqtSignal(bool)  # 播放状态 (True=播放, False=暂停)

    def run(self):
        websocket.enableTrace(False)
        self.ws = websocket.WebSocketApp(
            WS_URL,
            on_message=self.on_message,
            on_error=self.on_error,
            on_open=self.on_open
        )
        self.ws.run_forever()

    def on_open(self, ws):
        print(">> WebSocket 连接成功")

    def on_open(self, ws):
        print(">> WebSocket 连接成功")

    def stop(self):
        if hasattr(self, 'ws') and self.ws:
            self.ws.close()
        self.quit()
        self.wait(1000)

    def on_error(self, ws, error):
        # 忽略网络断开导致的错误
        pass

    def on_message(self, ws, message):
        try:
            payload = json.loads(message)
            msg_type = payload.get("type")
            data = payload.get("data", {})

            if msg_type == "lyric-change":
                # 优先使用 yrcData（逐字数据），否则回退到 lrcData
                yrc_data = data.get("yrcData", [])
                lrc_data = data.get("lrcData", [])
                if yrc_data:
                    self.signal_lyric_data.emit(yrc_data, True)  # 逐字模式
                else:
                    self.signal_lyric_data.emit(lrc_data, False)  # 普通模式
            elif msg_type == "progress-change":
                self.signal_progress.emit(data.get("currentTime", 0))
            elif msg_type == "song-change":
                self.signal_song_info.emit(data.get("title", "未知歌曲"))
            elif msg_type == "status-change":
                self.signal_status.emit(data.get("status", True))
        except Exception as e:
            print(f"解析错误: {e}")


class KaraokeLyricWidget(QWidget):
    """自定义歌词绘制组件，支持逐字填充动画和多行显示"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 歌词数据 - 支持多行
        self.lines = []  # [{"words": [...], "trans": "", "isBG": False}, ...]
        self.current_time = 0
        self.is_karaoke_mode = False
        
        # 兼容旧接口
        self.words = []
        self.trans = ""
        
        # 字体设置
        self.main_font_size = 24
        self.trans_font_size = 13
        self.bg_font_size = 14  # 背景歌词字号
        self.main_size_no_bg = 24  # 无背景歌词时的主歌词字号
        self.main_size_with_bg = 17  # 有背景歌词时的主歌词字号
        self.font_family = "Microsoft YaHei UI"
        
        # 颜色
        self.color_sung = QColor("#00BFFF")  # 已唱：蓝色
        self.color_singing = QColor("#00BFFF")  # 正在唱：蓝色
        self.color_unsung = QColor("white")  # 未唱：白色
        self.color_trans = QColor("#FFD700")  # 翻译：金色
        self.color_bg = QColor("#888888")  # 背景歌词：灰色
        
        # 淡入淡出动画
        # 动画状态
        self._anim_progress = 1.0
        self.old_lines = []
        self.old_karaoke_mode = False
        
        # 属性动画
        self.anim = QPropertyAnimation(self, b"anim_progress")
        self.anim.setDuration(300)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # 普通文本（非卡拉OK模式）
        self.plain_text = ""
        
        self.setMinimumHeight(80)  # 增加高度支持多行

    @pyqtProperty(float)
    def anim_progress(self):
        return self._anim_progress

    @anim_progress.setter
    def anim_progress(self, val):
        self._anim_progress = val
        self.update()

    

    
    def set_plain_text(self, text, animate=True):
        """设置普通文本（非卡拉OK模式）"""
        # 构造一个模拟的歌词行
        fake_line = {
            "words": [{"word": text, "startTime": 0, "endTime": 0}],
            "trans": "",
            "isBG": False
        }
        self.set_multi_lines([fake_line], is_karaoke=False, animate=animate)
    
    def set_time(self, current_time):
        """更新当前时间并重绘"""
        self.current_time = current_time
        self.update()
    
    def set_multi_lines(self, lines, is_karaoke, animate=True):
        """设置多行歌词（主歌词+背景歌词）"""
        if animate and (self.lines or self.words or self.plain_text):
            # 保存旧状态用于离场动画
            self.old_lines = self.lines
            self.old_karaoke_mode = self.is_karaoke_mode
            
            # 设置新状态
            self._apply_multi_lines(lines, is_karaoke)
            
            # 播放入场动画
            self.anim.stop()
            self.anim.setStartValue(0.0)
            self.anim.setEndValue(1.0)
            self.anim.start()
        else:
            self.old_lines = [] # 无动画时清除旧行
            self._apply_multi_lines(lines, is_karaoke)
            self._anim_progress = 1.0
    
    def _apply_multi_lines(self, lines, is_karaoke):
        """应用多行歌词"""
        self.lines = lines
        self.is_karaoke_mode = is_karaoke
        
        # 兼容旧接口：如果只有一行，同步到 words/trans
        if lines and len(lines) > 0:
            main_line = next((l for l in lines if not l.get("isBG", False)), lines[0])
            self.words = main_line.get("words", [])
            self.trans = main_line.get("trans", "")
            if self.words:
                self.plain_text = "".join([w.get("word", "") for w in self.words])
        
        self.update()

    def _draw_line_group(self, painter, lines, y_offset, opacity, is_karaoke):
        """绘制一组歌词（支持透明度和垂直偏移）"""
        if opacity <= 0: return
        painter.setOpacity(opacity)
        
        main_lines = [l for l in lines if not l.get("isBG", False)] if lines else []
        bg_lines = [l for l in lines if l.get("isBG", False)] if lines else []
        
        # 动态调整字体大小：有BG时变小，无BG时恢复
        if bg_lines:
            current_main_size = self.main_size_with_bg
            main_base_y = self.height() // 3 + current_main_size // 3
            bg_base_y = main_base_y + current_main_size + 4
        else:
            current_main_size = self.main_size_no_bg
            main_base_y = self.height() // 2 + current_main_size // 3
            bg_base_y = main_base_y + current_main_size + 8
            
        main_y = main_base_y + y_offset
        bg_y = bg_base_y + y_offset

        # 主字体
        main_font = QFont(self.font_family, current_main_size)
        main_font.setBold(True)
        # 背景歌词字体
        bg_font = QFont(self.font_family, self.bg_font_size)
        bg_font.setBold(False)

        # 绘制主歌词
        for line_data in main_lines:
            self._draw_single_line(painter, line_data, main_font, main_y, is_karaoke, self.color_sung, self.color_singing, self.color_unsung, self.main_font_size, True)

        # 绘制背景歌词
        for line_data in bg_lines:
            self._draw_single_line(painter, line_data, bg_font, bg_y, is_karaoke, self.color_sung, self.color_singing, self.color_bg, self.bg_font_size, False)

    def _draw_single_line(self, painter, line_data, font, y, is_karaoke, c_sung, c_singing, c_unsung, font_size, is_main):
        x = 0
        words = line_data.get("words", [])
        trans = line_data.get("trans", "")
        fm = QFontMetrics(font)
        
        if is_karaoke and words:
            for word_info in words:
                word = word_info.get("word", "")
                start = word_info.get("startTime", 0)
                end = word_info.get("endTime", 0)
                word_width = fm.horizontalAdvance(word)
                
                if self.current_time >= end:
                    painter.setFont(font)
                    painter.setPen(c_sung)
                    painter.drawText(x, y, word)
                elif self.current_time >= start:
                    progress = (self.current_time - start) / max(end - start, 1)
                    fill_width = int(word_width * progress)
                    
                    painter.setFont(font)
                    painter.setPen(c_singing)
                    painter.setClipRect(x, 0, fill_width, self.height())
                    painter.drawText(x, y, word)
                    
                    painter.setPen(c_unsung)
                    painter.setClipRect(x + fill_width, 0, word_width - fill_width, self.height())
                    painter.drawText(x, y, word)
                    
                    painter.setClipping(False)
                else:
                    painter.setFont(font)
                    painter.setPen(c_unsung)
                    painter.drawText(x, y, word)
                
                x += word_width
        else:
            text = "".join([w.get("word", "") for w in words]) if words else ""
            painter.setFont(font)
            painter.setPen(c_unsung)
            painter.drawText(x, y, text)
            x += fm.horizontalAdvance(text)
            
        # 绘制翻译
        if trans:
            # 翻译字号稍微小一点
            trans_size = self.trans_font_size if is_main else self.trans_font_size - 2
            trans_font = QFont(self.font_family, trans_size)
            painter.setFont(trans_font)
            painter.setPen(self.color_trans if is_main else self.color_bg)
            painter.drawText(x + 15, y, f"({trans})")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        slide_distance = 20
        progress = self._anim_progress
        
        # 绘制旧行（向上滑动 + 淡出）
        if self.old_lines and progress < 1.0:
            opacity = 1.0 - progress
            y_offset = -int(slide_distance * progress)
            self._draw_line_group(painter, self.old_lines, y_offset, opacity, self.old_karaoke_mode)
            
        # 绘制新行（向上入场 + 淡入）
        if self.lines:
            # 如果有旧行，则进行滑动入场；否则直接显示
            if self.old_lines:
                opacity = progress
                y_offset = int(slide_distance * (1.0 - progress))
            else:
                opacity = 1.0
                y_offset = 0
            self._draw_line_group(painter, self.lines, y_offset, opacity, self.is_karaoke_mode)
            
        painter.end()

class DesktopLyricWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.lyrics_db = []
        self.current_idx = -1
        self.is_karaoke_mode = False  # 是否为卡拉OK模式
        self.current_time = 0  # 当前播放时间
        self.last_server_time = 0  # 上次从服务器收到的时间
        self.is_playing = True  # 是否正在播放
        
        # 卡拉OK刷新定时器 (50ms = 20fps)
        self.karaoke_timer = QTimer()
        self.karaoke_timer.setInterval(50)
        self.karaoke_timer.timeout.connect(self._on_karaoke_tick)
        
        self.init_config()
        self.init_ui()
        
        self.worker = WebSocketWorker()
        self.worker.signal_lyric_data.connect(self.handle_lyrics_update)
        self.worker.signal_progress.connect(self.handle_progress_update)
        self.worker.signal_song_info.connect(self.handle_song_change)
        self.worker.signal_status.connect(self.handle_status_change)
        self.worker.start()

    def init_ui(self):
        # 1. 窗口属性
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 必须设置微量背景色，否则无法捕获鼠标点击
        self.setStyleSheet("background-color: rgba(0, 0, 0, 1);")
        
        # 允许窗口接收键盘焦点
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def init_config(self):
        """加载配置"""
        self.config = DEFAULT_CONFIG.copy()
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                self.config.update(saved)
        except:
            pass
            
        # 应用配置
        self.main_font_size = self.config.get("main_font_size", 24)
        self.trans_font_size = self.config.get("trans_font_size", 13)
        self.window_width = self.config.get("window_width", 1200)

    def save_config(self):
        """保存配置"""
        # 更新当前配置字典
        self.config["main_font_size"] = self.main_font_size
        self.config["trans_font_size"] = self.trans_font_size
        self.config["window_width"] = self.lyric_widget.width()
        self.config["font_family"] = self.lyric_widget.font_family
        self.config["bg_font_size"] = self.lyric_widget.bg_font_size
        self.config["main_size_no_bg"] = self.lyric_widget.main_size_no_bg
        self.config["main_size_with_bg"] = self.lyric_widget.main_size_with_bg
        
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置失败: {e}")

    def init_ui(self):
        # 1. 窗口属性
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 必须设置微量背景色，否则无法捕获鼠标点击
        self.setStyleSheet("background-color: rgba(0, 0, 0, 1);")
        
        # 允许窗口接收键盘焦点
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # 2. 布局
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 0, 10, 0)
        
        # 3. 使用自定义歌词组件（支持动画）
        self.lyric_widget = KaraokeLyricWidget()
        self.lyric_widget.main_font_size = self.main_font_size
        self.lyric_widget.trans_font_size = self.trans_font_size
        self.lyric_widget.setFixedWidth(self.window_width)
        
        # 应用配置中的额外属性
        self.lyric_widget.bg_font_size = self.config.get("bg_font_size", 14)
        self.lyric_widget.main_size_no_bg = self.config.get("main_size_no_bg", 24)
        self.lyric_widget.main_size_with_bg = self.config.get("main_size_with_bg", 17)
        self.lyric_widget.font_family = self.config.get("font_family", "Microsoft YaHei UI")
        
        layout.addWidget(self.lyric_widget)
        self.setLayout(layout)

        # 4. 窗口初始位置和大小
        screen = QApplication.primaryScreen().geometry()
        
        self.resize(self.window_width + 20, 50)
        
        # 默认放在屏幕中心
        center_x = (screen.width() - self.width()) // 2
        center_y = (screen.height() - self.height()) // 2
        self.move(center_x, center_y)
        self.show()
        self.activateWindow()

    def update_text_ui(self, line_data, current_time=None, animate=False):
        """更新歌词显示，支持卡拉OK模式"""
        if self.is_karaoke_mode and "words" in line_data:
            # 卡拉OK模式：设置逐字数据
            if animate:
                # 切换歌词行时播放动画
                self.lyric_widget.set_lyrics(
                    line_data["words"], 
                    line_data["trans"], 
                    True, 
                    animate=True
                )
            else:
                # 只更新时间（逐字填充动画）
                self.lyric_widget.words = line_data["words"]
                self.lyric_widget.trans = line_data["trans"]
                self.lyric_widget.is_karaoke_mode = True
                if current_time is not None:
                    self.lyric_widget.set_time(current_time)
        else:
            # 普通模式
            text = line_data["original"]
            if line_data["trans"]:
                text += f"  ({line_data['trans']})"
            self.lyric_widget.set_plain_text(text, animate=animate)

    def handle_lyrics_update(self, lrc_data, is_karaoke):
        """处理歌词数据更新"""
        self.is_karaoke_mode = is_karaoke
        parsed = []
        for line in lrc_data:
            words_list = line.get("words", [])
            orig = "".join([w.get("word", "") for w in words_list])
            trans = line.get("translatedLyric", "")
            # 简单清洗
            if orig.strip():
                entry = {
                    "start": line.get("startTime", 0),
                    "end": line.get("endTime", 0),
                    "original": orig,
                    "trans": trans,
                    "isBG": line.get("isBG", False),      # 是否为背景歌词
                    "isDuet": line.get("isDuet", False)   # 是否为对唱
                }
                # 如果是卡拉OK模式，保存逐字信息
                if is_karaoke:
                    entry["words"] = words_list
                parsed.append(entry)
        self.lyrics_db = parsed
        self.current_idx = -1  # 重置索引
        # 启动或停止卡拉OK定时器
        if is_karaoke and not self.karaoke_timer.isActive():
            self.karaoke_timer.start()
        elif not is_karaoke and self.karaoke_timer.isActive():
            self.karaoke_timer.stop()

    def handle_progress_update(self, current_time):
        if not self.lyrics_db:
            return
        
        # 同步服务器时间 (仅当偏差超过阈值时才强制同步，避免抖动)
        if abs(self.current_time - current_time) > 200:
            self.current_time = current_time

        # 查找并更新当前行索引
        self._update_current_line(self.current_time)
    
    def _on_karaoke_tick(self):
        """定时器回调：高频刷新卡拉OK歌词"""
        if not self.is_karaoke_mode or not self.lyrics_db:
            return
        
        # 如果暂停了，不进行时间插值
        if not self.is_playing:
            return
        
        # 本地插值：每次 tick 增加 50ms
        self.current_time += 50
        
        # 使用统一的多行更新逻辑
        self._update_current_line(self.current_time)
    
    def _update_current_line(self, current_time):
        """更新当前歌词行索引并刷新显示（限制一行主歌词+一行背景歌词）"""
        # 查找与当前时间重叠的歌词行（新歌词替换旧歌词）
        main_line = None
        bg_line = None
        main_idx = -1
        
        for i, line in enumerate(self.lyrics_db):
            is_bg = line.get("isBG", False)
            
            # 检查时间是否在范围内（后面的歌词会覆盖前面的）
            if line["start"] <= current_time <= line["end"]:
                if is_bg:
                    bg_line = line  # 新的背景歌词替换旧的
                else:
                    main_line = line  # 新的主歌词替换旧的
                    main_idx = i
            # 也检查间隙时间（显示上一行直到下一行开始）
            elif not is_bg and i + 1 < len(self.lyrics_db):
                if line["start"] <= current_time < self.lyrics_db[i+1]["start"]:
                    main_line = line
                    main_idx = i
        
        # 构建显示列表：最多1行主歌词 + 1行背景歌词
        active_lines = []
        if main_line:
            active_lines.append(main_line)
        if bg_line:
            active_lines.append(bg_line)
        
        # 更新显示
        if active_lines:
            if main_idx != self.current_idx:
                # 切换到新行，播放动画
                self.current_idx = main_idx
                self._update_multi_lines(active_lines, current_time, animate=True)
            else:
                # 同一行，只更新时间（用于逐字高亮）
                self._update_multi_lines(active_lines, current_time, animate=False)
    
    def _update_multi_lines(self, lines, current_time, animate=False):
        """更新多行歌词显示"""
        # 构建多行数据
        line_data = []
        for line in lines:
            entry = {
                "words": line.get("words", []),
                "trans": line.get("trans", ""),
                "isBG": line.get("isBG", False),
                "isDuet": line.get("isDuet", False)
            }
            # 如果没有 words，用 original 生成
            if not entry["words"]:
                entry["words"] = [{"word": line.get("original", ""), "startTime": line["start"], "endTime": line["end"]}]
            line_data.append(entry)
        
        if animate:
            self.lyric_widget.set_multi_lines(line_data, self.is_karaoke_mode, animate=True)
        else:
            # 只更新时间，不播放动画
            self.lyric_widget.lines = line_data
            
        # 始终更新时间，确保动画第一帧也是准确的
        self.lyric_widget.set_time(current_time)

    def handle_song_change(self, title):
        # 歌名显示
        self.lyric_widget.set_plain_text(f"♪ {title}", animate=True)
    
    def handle_status_change(self, is_playing):
        """处理播放/暂停状态变化"""
        self.is_playing = is_playing
        print(f">> 播放状态: {'播放' if is_playing else '暂停'}")

    # --- 鼠标拖拽逻辑 ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus() # 点击时获取焦点，以便接收键盘事件
            self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()
            
    # --- 滚轮缩放逻辑 ---
    def wheelEvent(self, event):
        # 检查是否按下了 Alt 键
        modifiers = event.modifiers()
        if modifiers & Qt.KeyboardModifier.AltModifier:
            # 获取滚轮滚动的角度 (通常是 120 或 -120)
            delta = event.angleDelta().y()
            
            # 步长：向上滚动(+120)字号变大，向下(-120)变小
            step = 2 if delta > 0 else -2
            
            self.main_font_size += step
            self.trans_font_size += step
            
            # 限制最小字号，防止太小看不见
            self.main_font_size = max(10, self.main_font_size)
            self.trans_font_size = max(8, self.trans_font_size)
            
            # 同步到歌词组件
            self.lyric_widget.main_font_size = self.main_font_size
            self.lyric_widget.trans_font_size = self.trans_font_size
            
            # 刷新 UI
            self.lyric_widget.update()
            
            event.accept()
        else:
            # 如果没按 Alt，就忽略（或者交给父类处理）
            super().wheelEvent(event)
            
    # --- 键盘移动逻辑 (WASD) ---
    def keyPressEvent(self, event):
        modifiers = event.modifiers()
        if modifiers & Qt.KeyboardModifier.AltModifier:
            step = 10 # 每次移动 10 像素
            pos = self.pos()
            key = event.key()
            
            if key == Qt.Key.Key_W:
                self.move(pos.x(), pos.y() - step)
                event.accept()
            elif key == Qt.Key.Key_S:
                self.move(pos.x(), pos.y() + step)
                event.accept()
            elif key == Qt.Key.Key_A:
                self.move(pos.x() - step, pos.y())
                event.accept()
            elif key == Qt.Key.Key_D:
                self.move(pos.x() + step, pos.y())
                event.accept()
            else:
                super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)

    # --- 鼠标悬停逻辑 (显示/隐藏背景) ---
    def enterEvent(self, event):
        # 鼠标移入：显示半透明深色背景，方便操作
        self.setStyleSheet("background-color: rgba(0, 0, 0, 150);")
        super().enterEvent(event)

    def leaveEvent(self, event):
        # 鼠标移出：恢复微量背景（几乎透明）
        self.setStyleSheet("background-color: rgba(0, 0, 0, 1);")
        super().leaveEvent(event)
        
    def refresh_ui(self):
        """强制刷新当前显示的歌词，用于应用新的字体设置"""
        # 同步字体大小到歌词组件
        self.lyric_widget.main_font_size = self.main_font_size
        self.lyric_widget.trans_font_size = self.trans_font_size
        self.lyric_widget.update()

from PyQt6.QtWidgets import QPushButton, QSpinBox, QVBoxLayout, QGroupBox, QFormLayout, QLineEdit

class ControlPanelWindow(QWidget):
    def __init__(self, lyric_window):
        super().__init__()
        self.lyric_win = lyric_window
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("歌词控制面板")
        self.resize(300, 420)
        
        layout = QVBoxLayout()
        
        # --- 分组1：字体设置 ---
        grp_font = QGroupBox("字体设置")
        form_layout = QFormLayout()
        
        self.edit_font_family = QLineEdit()
        self.edit_font_family.setText(self.lyric_win.lyric_widget.font_family)
        self.edit_font_family.setPlaceholderText("例: Lexend, vivo sans")
        self.edit_font_family.editingFinished.connect(self.on_font_family_change)
        
        self.spin_main = QSpinBox()
        self.spin_main.setRange(8, 100)
        self.spin_main.setValue(self.lyric_win.main_font_size)
        self.spin_main.valueChanged.connect(self.on_font_change)
        
        self.spin_trans = QSpinBox()
        self.spin_trans.setRange(8, 100)
        self.spin_trans.setValue(self.lyric_win.trans_font_size)
        self.spin_trans.valueChanged.connect(self.on_font_change)
        
        self.spin_size_no_bg = QSpinBox()
        self.spin_size_no_bg.setRange(8, 100)
        self.spin_size_no_bg.setValue(self.lyric_win.lyric_widget.main_size_no_bg)
        self.spin_size_no_bg.valueChanged.connect(self.on_dynamic_size_change)
        
        self.spin_size_with_bg = QSpinBox()
        self.spin_size_with_bg.setRange(8, 100)
        self.spin_size_with_bg.setValue(self.lyric_win.lyric_widget.main_size_with_bg)
        self.spin_size_with_bg.valueChanged.connect(self.on_dynamic_size_change)
        
        self.spin_bg_size = QSpinBox()
        self.spin_bg_size.setRange(8, 100)
        self.spin_bg_size.setValue(self.lyric_win.lyric_widget.bg_font_size)
        self.spin_bg_size.valueChanged.connect(self.on_dynamic_size_change)
        
        form_layout.addRow("字体:", self.edit_font_family)
        form_layout.addRow("原文大小:", self.spin_main)
        form_layout.addRow("翻译大小:", self.spin_trans)
        form_layout.addRow("无BG时字号:", self.spin_size_no_bg)
        form_layout.addRow("有BG时字号:", self.spin_size_with_bg)
        form_layout.addRow("背景歌词字号:", self.spin_bg_size)
        grp_font.setLayout(form_layout)
        
        # --- 分组2：窗口宽度设置 ---
        grp_width = QGroupBox("窗口宽度")
        form_width = QFormLayout()
        
        self.spin_width = QSpinBox()
        self.spin_width.setRange(200, 2000)
        self.spin_width.setSingleStep(50)
        self.spin_width.setValue(self.lyric_win.lyric_widget.width())
        self.spin_width.valueChanged.connect(self.on_width_change)
        
        form_width.addRow("最大宽度:", self.spin_width)
        grp_width.setLayout(form_width)
        
        # --- 分组3：位置设置 ---
        grp_pos = QGroupBox("快速位置")
        vbox_pos = QVBoxLayout()
        
        btn_top = QPushButton("置顶 (Top)")
        btn_top.clicked.connect(lambda: self.set_pos_preset("top"))
        
        btn_center = QPushButton("居中 (Center)")
        btn_center.clicked.connect(lambda: self.set_pos_preset("center"))
        
        btn_bottom = QPushButton("底部 (Bottom)")
        btn_bottom.clicked.connect(lambda: self.set_pos_preset("bottom"))
        
        vbox_pos.addWidget(btn_top)
        vbox_pos.addWidget(btn_center)
        vbox_pos.addWidget(btn_bottom)
        grp_pos.setLayout(vbox_pos)
        
        # --- 分组4：操作按钮 ---
        grp_action = QGroupBox("操作")
        vbox_action = QVBoxLayout()
        
        btn_refresh = QPushButton("强制刷新歌词")
        btn_refresh.clicked.connect(self.on_refresh_click)

        self.btn_exit = QPushButton("结束程序")
        self.btn_exit.clicked.connect(QApplication.instance().quit)
        
        vbox_action.addWidget(btn_refresh)
        vbox_action.addWidget(self.btn_exit)
        grp_action.setLayout(vbox_action)
        
        layout.addWidget(grp_font)
        layout.addWidget(grp_width)
        layout.addWidget(grp_pos)
        layout.addWidget(grp_action)
        self.setLayout(layout)
        self.show()
        
    def on_font_family_change(self):
        new_font = self.edit_font_family.text().strip()
        if new_font:
            self.lyric_win.lyric_widget.font_family = new_font
            self.lyric_win.refresh_ui()
            self.lyric_win.save_config()
    
    def on_font_change(self):
        self.lyric_win.main_font_size = self.spin_main.value()
        self.lyric_win.trans_font_size = self.spin_trans.value()
        self.lyric_win.refresh_ui()
        self.lyric_win.save_config()
    
    def on_dynamic_size_change(self):
        self.lyric_win.lyric_widget.main_size_no_bg = self.spin_size_no_bg.value()
        self.lyric_win.lyric_widget.main_size_with_bg = self.spin_size_with_bg.value()
        self.lyric_win.lyric_widget.bg_font_size = self.spin_bg_size.value()
        self.lyric_win.refresh_ui()
        self.lyric_win.save_config()
        
    def on_width_change(self):
        new_width = self.spin_width.value()
        self.lyric_win.lyric_widget.setFixedWidth(new_width)
        self.lyric_win.resize(new_width + 20, self.lyric_win.height())
        self.lyric_win.save_config()
        
    def on_refresh_click(self):
        self.lyric_win.refresh_ui()
        
    def set_pos_preset(self, position):
        screen = QApplication.primaryScreen().geometry()
        win_w = self.lyric_win.width()
        win_h = self.lyric_win.height()
        
        x = (screen.width() - win_w) // 2
        
        if position == "top":
            y = 100
        elif position == "center":
            y = (screen.height() - win_h) // 2
        elif position == "bottom":
            y = screen.height() - win_h - 100
            
        self.lyric_win.move(x, y)

    def closeEvent(self, event):
        # 拦截关闭事件，改为隐藏
        event.ignore()
        self.hide()

if __name__ == "__main__":
    # 隐藏控制台窗口
    try:
        ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
    except:
        pass

    app = QApplication(sys.argv)
    
    # 1. 创建歌词窗口
    lyric_win = DesktopLyricWindow()
    
    # 2. 创建控制面板，并传入歌词窗口实例
    panel_win = ControlPanelWindow(lyric_win)
    
    # 3. 系统托盘图标
    tray_icon = QSystemTrayIcon(app)
    # 使用系统标准图标
    tray_icon.setIcon(app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
    
    # 托盘菜单
    tray_menu = QMenu()
    
    action_show_panel = QAction("控制面板", app)
    action_show_panel.triggered.connect(panel_win.show)
    
    def clean_exit():
        try:
            lyric_win.worker.stop()
        except:
            pass
        app.quit()
        # 强制结束进程
        os._exit(0)
    
    action_exit = QAction("退出", app)
    action_exit.triggered.connect(clean_exit)
    
    tray_menu.addAction(action_show_panel)
    tray_menu.addSeparator()
    tray_menu.addAction(action_exit)
    
    # 绑定控制面板的退出按钮也走 clean_exit
    panel_win.btn_exit.clicked.disconnect()
    panel_win.btn_exit.clicked.connect(clean_exit)
    
    tray_icon.setContextMenu(tray_menu)
    
    # 双击托盘图标显示控制面板
    def on_tray_activated(reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            panel_win.show()
            panel_win.activateWindow()
            
    tray_icon.activated.connect(on_tray_activated)
    tray_icon.show()
    
    sys.exit(app.exec())