"""
简单的命令行游戏演示
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.game_engine import GameEngine
from src.models import GameAction, ActionType, UnitType


def print_game_state(engine: GameEngine):
    """打印游戏状态"""
    state = engine.get_game_state()
    
    print(f"\n=== 回合 {state.turn} ===")
    print(f"当前玩家: {state.current_player_id}")
    
    # 打印玩家信息
    for player in state.players:
        print(f"\n玩家 {player.name} (ID: {player.id}):")
        print(f"  金币: {player.gold}")
        print(f"  城市数量: {len(player.cities)}")
        print(f"  单位数量: {len(player.units)}")
        
        # 打印单位
        for unit in player.units:
            print(f"    {unit.unit_type.value} 在 ({unit.position.q}, {unit.position.r})")
    
    print(f"\n游戏结束: {state.game_over}")
    if state.winner:
        print(f"获胜者: {state.winner.name}")


def main():
    """主函数"""
    print("六边形策略游戏演示")
    
    # 创建游戏引擎
    engine = GameEngine()
    
    # 初始化游戏
    player_names = ["玩家1", "玩家2"]
    if not engine.initialize_game(player_names, map_seed=12345):
        print("游戏初始化失败")
        return
    
    print("游戏初始化成功！")
    
    # 游戏主循环
    turn_count = 0
    max_turns = 5  # 限制演示回合数
    
    while not engine.game_over and turn_count < max_turns:
        print_game_state(engine)
        
        # 获取当前玩家
        current_player = engine.turn_system.get_current_player()
        if not current_player:
            break
        
        print(f"\n轮到 {current_player.name} 行动")
        
        # 简单的AI行为：尝试建城或结束回合
        actions_taken = False
        
        # 尝试用移民建城
        for unit in current_player.units:
            if unit.unit_type == UnitType.SETTLER:
                action = GameAction(
                    player_id=current_player.id,
                    action_type=ActionType.BUILD_CITY,
                    params={"unit_id": unit.id}
                )
                
                if engine.execute_action(action):
                    print(f"  {current_player.name} 建立了城市")
                    actions_taken = True
                    break
        
        # 如果有城市，尝试建造单位
        if not actions_taken and current_player.cities:
            for city in current_player.cities:
                if city.owner.gold >= 30:  # 士兵成本
                    action = GameAction(
                        player_id=current_player.id,
                        action_type=ActionType.BUILD_UNIT,
                        params={
                            "city_id": city.id,
                            "unit_type": UnitType.SOLDIER.value
                        }
                    )
                    
                    if engine.execute_action(action):
                        print(f"  {current_player.name} 建造了士兵")
                        actions_taken = True
                        break
        
        # 结束回合
        end_turn_action = GameAction(
            player_id=current_player.id,
            action_type=ActionType.END_TURN,
            params={}
        )
        engine.execute_action(end_turn_action)
        
        if engine.turn_system.current_player_index == 0:
            turn_count += 1
    
    print_game_state(engine)
    print("\n演示结束!")


if __name__ == "__main__":
    main()
