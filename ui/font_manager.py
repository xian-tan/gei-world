"""
字体管理器 - 处理中文字体加载
"""
import pygame
import os
from typing import Dict, Optional

from ui.ui_config import CHINESE_FONTS, FONT_SIZE_SMALL, FONT_SIZE_MEDIUM, FONT_SIZE_LARGE


class FontManager:
    """字体管理器"""
    
    def __init__(self):
        if not pygame.font.get_init():
            pygame.font.init()
        self.fonts = {}
        self.chinese_font_path = self._find_chinese_font()
        self._init_fonts()
    
    def _find_chinese_font(self) -> Optional[str]:
        """查找可用的中文字体"""
        for font_path in CHINESE_FONTS:
            if os.path.exists(font_path):
                print(f"找到中文字体: {font_path}")
                return font_path
        
        font_names = [
            "PingFang SC",
            "STHeiti",
            "Hiragino Sans GB",
            "Songti SC",
            "Microsoft YaHei",
            "SimHei",
            "Noto Sans CJK SC",
            "WenQuanYi Zen Hei",
        ]
        for font_name in font_names:
            matched_path = pygame.font.match_font(font_name)
            if matched_path and os.path.exists(matched_path):
                print(f"找到系统中文字体: {font_name} -> {matched_path}")
                return matched_path
        
        print("警告: 未找到中文字体，将使用默认字体")
        return None
    
    def _init_fonts(self):
        """初始化字体"""
        sizes = {
            'small': FONT_SIZE_SMALL,
            'medium': FONT_SIZE_MEDIUM,
            'large': FONT_SIZE_LARGE
        }
        
        for size_name, size_value in sizes.items():
            if self.chinese_font_path:
                try:
                    # 尝试加载中文字体
                    font = pygame.font.Font(self.chinese_font_path, size_value)
                    self.fonts[size_name] = font
                    print(f"已加载中文字体 {size_name}: {size_value}px")
                except Exception as e:
                    print(f"加载中文字体失败: {e}")
                    # 回退到默认字体
                    self.fonts[size_name] = pygame.font.Font(None, size_value)
            else:
                # 使用默认字体
                self.fonts[size_name] = pygame.font.Font(None, size_value)
    
    def get_font(self, size: str) -> pygame.font.Font:
        """获取指定大小的字体"""
        return self.fonts.get(size, self.fonts['medium'])
    
    def render_text(self, text: str, size: str = 'medium', 
                   color: tuple = (255, 255, 255)) -> pygame.Surface:
        """渲染文本"""
        font = self.get_font(size)
        return font.render(text, True, color)
    
    def get_text_size(self, text: str, size: str = 'medium') -> tuple:
        """获取文本尺寸"""
        font = self.get_font(size)
        return font.size(text)


# 全局字体管理器实例
_font_manager = None

def get_font_manager() -> FontManager:
    """获取全局字体管理器实例"""
    global _font_manager
    if _font_manager is None or not pygame.font.get_init():
        _font_manager = FontManager()
    return _font_manager
