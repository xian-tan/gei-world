"""
游戏配置文件
所有规则参数可在此配置
"""

# 地图配置
MAP_CONFIG = {
    "radius": 10,           # 地图半径
    "ocean_ratio": 0.3,     # 海洋比例
    "seed": None,           # 随机种子，None为随机
}

# 玩家配置
PLAYER_CONFIG = {
    "initial_gold": 100,    # 初始金币
    "max_players": 4,       # 最大玩家数
}

# 单位配置
UNIT_CONFIG = {
    "soldier_movement": 2,  # 士兵移动力
    "soldier_vision": 2,    # 士兵视野
    "settler_vision": 1,    # 移民视野
    "settler_cost": 50,     # 移民建造成本
    "soldier_cost": 30,     # 士兵建造成本
}

# 经济配置
ECONOMY_CONFIG = {
    "territory_income": 1,  # 每块领土收入
}

# 城市配置
CITY_CONFIG = {
    "territory_radius": 1,  # 城市初始领土半径
    "defense_value": 2,     # 城市防御值
}
