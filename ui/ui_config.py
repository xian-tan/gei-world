"""
UI常量配置
"""
import pygame

# 屏幕设置
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
FPS = 60
OFFSET_X = 300
OFFSET_Y = 205

# 颜色定义
COLORS = {
    'WHITE': (255, 255, 255),
    'BLACK': (0, 0, 0),
    'GRAY': (128, 128, 128),
    'DARK_GRAY': (64, 64, 64),
    'LIGHT_GRAY': (192, 192, 192),
    'RED': (255, 0, 0),
    'GREEN': (0, 255, 0),
    'BLUE': (0, 0, 255),
    'YELLOW': (255, 255, 0),
    'ORANGE': (255, 165, 0),
    'PURPLE': (128, 0, 128),
    'CYAN': (0, 255, 255),
    'BROWN': (139, 69, 19),
    
    # 游戏特定颜色
    'MAP_BACKGROUND': (22, 28, 38), # 地图外背景
    'MINIMAP_BACKGROUND': (18, 18, 24),
    'MINIMAP_BORDER': (220, 220, 220),
    'MINIMAP_VIEWPORT': (255, 255, 255),
    'OCEAN': (65, 105, 225),      # 海洋蓝
    'LAND': (34, 139, 34),        # 陆地绿
    'LAND_SELECTED': (50, 205, 50), # 选中的陆地
    'FOG_OF_WAR': (50, 50, 50),   # 战争迷雾
    'EXPLORED': (100, 100, 100),   # 已探索但不可见
    
    # 玩家颜色
    'PLAYER_1': (220, 80, 80),   # 红色系
    'PLAYER_2': (80, 120, 230),   # 蓝色系
    'PLAYER_3': (40, 170, 150),   # 青绿色系，避免亮黄色
    'PLAYER_4': (165, 95, 210),   # 紫色系
}

# 六边形设置
HEX_RADIUS = 20
HEX_WIDTH = HEX_RADIUS * 2
HEX_HEIGHT = int(HEX_RADIUS * 1.732)  # sqrt(3) * radius

# UI面板设置
PANEL_WIDTH = 300
INFO_PANEL_HEIGHT = 150
MINIMAP_WIDTH = 220
MINIMAP_HEIGHT = 160
MINIMAP_MARGIN = 14

# 字体设置
FONT_SIZE_SMALL = 12
FONT_SIZE_MEDIUM = 16
FONT_SIZE_LARGE = 24

# 中文字体路径
CHINESE_FONTS = [
    # macOS
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    
    # Windows
    "C:/Windows/Fonts/msyh.ttc",        # 微软雅黑
    "C:/Windows/Fonts/simsun.ttc",      # 宋体
    "C:/Windows/Fonts/simhei.ttf",      # 黑体
    "C:/Windows/Fonts/simkai.ttf",      # 楷体
    "C:/Windows/Fonts/simsun.ttf",      # 宋体(备选)
]

# 单位图标设置
UNIT_ICON_SIZE = 16

# 动画设置
ANIMATION_SPEED = 5
FADE_SPEED = 2
