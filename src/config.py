"""
游戏配置文件
所有规则参数集中在此定义，UI 文案和 AI 决策均从这里读取。
"""

# 地图配置
MAP_CONFIG = {
    "radius": 10,           # 地图半径
    "ocean_ratio": 0.3,     # 海洋比例
    "seed": None,           # 随机种子，None为随机
}

# 玩家配置
PLAYER_CONFIG = {
    "initial_gold": 20,     # 初始金币
    "max_players": 4,       # 最大玩家数
}

# 单位配置
UNIT_CONFIG = {
    "settler_movement": 1,  # 移民移动力
    "soldier_movement": 2,  # 士兵移动力
    "soldier_vision": 2,    # 士兵视野
    "settler_vision": 1,    # 移民视野
    "settler_cost": 30,     # 移民建造成本
    "soldier_cost": 5,      # 士兵建造成本（每名）
}

# 经济配置
ECONOMY_CONFIG = {
    "territory_income": 1,      # 经济范围内每块己方陆地收入
    "city_center_income": 3,    # 每座城市中心额外收入
}

# 城市配置
CITY_CONFIG = {
    "initial_territory_radius": 1,  # 建城后自动获得的初始领土半径
    "economic_radius": 2,           # 城市可提供收入的经济范围半径
    "base_defense": 3,              # 新建城市防御
    "defense_growth": 1,            # 每整轮防御增长
    "max_defense": 8,               # 防御上限
    "captured_defense": 0,          # 被攻占后防御重置值
    "productions_per_turn": 1,      # 每城每回合生产次数
}

# 对局配置
GAME_CONFIG = {
    "max_turns": 100,               # 回合上限，达到后按分数判胜
    "score_per_city": 10,
    "score_per_territory": 1,
    "score_per_soldier": 1,
}
