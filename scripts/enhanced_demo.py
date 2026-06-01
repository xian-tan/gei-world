"""
增强版演示程序 - 支持AI玩家和保存功能
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.game_engine import GameEngine
from src.models import GameAction, ActionType, UnitType
from src.systems.ai_system import AIManager
from src.systems.save_system import GameSaveSystem
from src.utils import get_player_statistics


class EnhancedDemo:
    """增强版演示"""
    
    def __init__(self):
        self.engine = GameEngine()
        self.ai_manager = AIManager()
        self.save_system = GameSaveSystem()
    
    def run_demo(self):
        """运行演示"""
        print("=== 六边形策略游戏增强版演示 ===\n")
        
        # 演示菜单
        while True:
            print("选择演示模式:")
            print("1. 人机对战")
            print("2. AI自动对战")
            print("3. 载入保存的游戏")
            print("4. 查看保存列表")
            print("0. 退出")
            
            choice = input("\n请选择 (0-4): ").strip()
            
            if choice == "0":
                print("退出演示")
                break
            elif choice == "1":
                self.demo_human_vs_ai()
            elif choice == "2":
                self.demo_ai_vs_ai()
            elif choice == "3":
                self.demo_load_game()
            elif choice == "4":
                self.demo_list_saves()
            else:
                print("无效选择，请重试\n")
    
    def demo_human_vs_ai(self):
        """人机对战演示"""
        print("\n=== 人机对战模式 ===")
        
        # 初始化游戏
        player_names = ["人类玩家", "AI玩家"]
        if not self.engine.initialize_game(player_names, map_seed=12345):
            print("游戏初始化失败")
            return
        
        # 设置AI
        ai_player = self.engine.player_system.players[1]
        self.ai_manager.add_ai_player(ai_player, "simple", "easy")
        
        print("游戏初始化成功！")
        print("你是玩家1，AI是玩家2")
        
        # 游戏循环
        turn_limit = 10  # 限制回合数
        current_turn = 0
        
        while not self.engine.game_over and current_turn < turn_limit:
            self.print_game_state()
            
            current_player = self.engine.turn_system.get_current_player()
            if not current_player:
                break
            
            print(f"\n轮到 {current_player.name} 行动")
            
            if self.ai_manager.is_ai_player(current_player.id):
                # AI行动
                print("AI正在思考...")
                action = self.ai_manager.get_ai_action(current_player.id, self.engine)
                
                if action:
                    success = self.engine.execute_action(action)
                    if success:
                        print(f"AI执行了行动: {action.action_type.value}")
                    else:
                        print("AI行动失败")
                
                input("按回车继续...")
            else:
                # 人类玩家行动
                self.handle_human_turn(current_player)
            
            if self.engine.turn_system.current_player_index == 0:
                current_turn += 1
        
        # 游戏结束
        self.print_game_state()
        if self.engine.game_over:
            print(f"\n🎉 游戏结束！获胜者：{self.engine.winner.name}")
        else:
            print(f"\n⏰ 演示结束（{turn_limit}回合限制）")
        
        # 询问是否保存
        save_choice = input("\n是否保存游戏？(y/n): ").strip().lower()
        if save_choice == 'y':
            save_name = input("输入保存名称: ").strip()
            if save_name:
                self.save_system.save_game(self.engine, save_name)
    
    def demo_ai_vs_ai(self):
        """AI对战演示"""
        print("\n=== AI自动对战模式 ===")
        
        # 初始化游戏
        player_names = ["AI战士", "AI征服者"]
        if not self.engine.initialize_game(player_names, map_seed=54321):
            print("游戏初始化失败")
            return
        
        # 设置不同类型的AI
        ai_player1 = self.engine.player_system.players[0]
        ai_player2 = self.engine.player_system.players[1]
        
        self.ai_manager.add_ai_player(ai_player1, "simple", "easy")
        self.ai_manager.add_ai_player(ai_player2, "aggressive", "medium")
        
        print("游戏初始化成功！")
        print("观看AI自动对战...")
        
        # 快速游戏循环
        turn_limit = 15
        current_turn = 0
        
        while not self.engine.game_over and current_turn < turn_limit:
            current_player = self.engine.turn_system.get_current_player()
            if not current_player:
                break
            
            # 显示简化的游戏状态
            if self.engine.turn_system.current_player_index == 0:
                print(f"\n--- 回合 {self.engine.turn_system.current_turn} ---")
                for player in self.engine.player_system.players:
                    stats = get_player_statistics(player)
                    print(f"{stats['name']}: 💰{stats['gold']} 🏙️{stats['cities']} 👥{len(player.units)}")
            
            print(f"{current_player.name} 行动中...")
            
            # AI行动
            action = self.ai_manager.get_ai_action(current_player.id, self.engine)
            if action:
                success = self.engine.execute_action(action)
                if success and action.action_type != ActionType.END_TURN:
                    print(f"  -> {action.action_type.value}")
            
            if self.engine.turn_system.current_player_index == 0:
                current_turn += 1
                input("  按回车继续下一回合...")
        
        # 最终结果
        print(f"\n=== 最终结果 ===")
        self.print_game_state()
        if self.engine.game_over:
            print(f"🏆 获胜者：{self.engine.winner.name}")
    
    def demo_load_game(self):
        """载入游戏演示"""
        print("\n=== 载入游戏 ===")
        
        saves = self.save_system.list_saves()
        if not saves:
            print("没有找到保存的游戏")
            return
        
        print("可用的保存:")
        for i, save in enumerate(saves):
            print(f"{i+1}. {save['name']} (回合{save['turn']}, {save['timestamp'][:19]})")
        
        try:
            choice = int(input("选择保存编号: ")) - 1
            if 0 <= choice < len(saves):
                save_name = saves[choice]['name']
                loaded_engine = self.save_system.load_game(save_name)
                
                if loaded_engine:
                    self.engine = loaded_engine
                    print("游戏载入成功！可继续当前存档。")
                    self.print_game_state()
                else:
                    print("载入失败，请检查保存文件是否完整")
            else:
                print("无效选择")
        except ValueError:
            print("输入无效")
    
    def demo_list_saves(self):
        """列出保存文件"""
        print("\n=== 保存文件列表 ===")
        
        saves = self.save_system.list_saves()
        if not saves:
            print("没有保存文件")
            return
        
        for save in saves:
            print(f"名称: {save['name']}")
            print(f"  时间: {save['timestamp'][:19]}")
            print(f"  回合: {save['turn']}")
            print(f"  玩家: {', '.join(save['players'])}")
            print()
    
    def handle_human_turn(self, player):
        """处理人类玩家回合"""
        while True:
            print("\n可用行动:")
            print("1. 查看单位状态")
            print("2. 尝试建城")
            print("3. 尝试建造单位")
            print("4. 结束回合")
            
            choice = input("选择行动 (1-4): ").strip()
            
            if choice == "1":
                self.show_player_units(player)
            elif choice == "2":
                if self.try_auto_build_city(player):
                    break
            elif choice == "3":
                if self.try_auto_build_unit(player):
                    break
            elif choice == "4":
                action = GameAction(
                    player_id=player.id,
                    action_type=ActionType.END_TURN,
                    params={}
                )
                self.engine.execute_action(action)
                break
            else:
                print("无效选择")
    
    def try_auto_build_city(self, player) -> bool:
        """尝试自动建城"""
        settlers = [unit for unit in player.units if unit.unit_type == UnitType.SETTLER]
        
        if not settlers:
            print("没有可用的移民")
            return False
        
        for settler in settlers:
            if self.engine.city_system.can_build_city(settler.position, self.engine.map_tiles, settler.owner):
                action = GameAction(
                    player_id=player.id,
                    action_type=ActionType.BUILD_CITY,
                    params={"unit_id": settler.id}
                )
                
                if self.engine.execute_action(action):
                    print("✓ 建城成功！")
                    return True
        
        print("✗ 当前位置无法建城")
        return False
    
    def try_auto_build_unit(self, player) -> bool:
        """尝试自动建造单位"""
        if not player.cities:
            print("没有城市")
            return False
        
        city = player.cities[0]  # 使用第一个城市
        
        if player.gold >= 30:
            action = GameAction(
                player_id=player.id,
                action_type=ActionType.BUILD_UNIT,
                params={
                    "city_id": city.id,
                    "unit_type": UnitType.SOLDIER.value
                }
            )
            
            if self.engine.execute_action(action):
                print("✓ 建造士兵成功！")
                return True
        
        print("✗ 金币不足或建造失败")
        return False
    
    def show_player_units(self, player):
        """显示玩家单位"""
        print(f"\n{player.name} 的单位:")
        if not player.units:
            print("  无单位")
            return
        
        for unit in player.units:
            print(f"  {unit.unit_type.value} 在 ({unit.position.q}, {unit.position.r})")
    
    def print_game_state(self):
        """打印游戏状态"""
        print(f"\n=== 回合 {self.engine.turn_system.current_turn} ===")
        
        for player in self.engine.player_system.players:
            stats = get_player_statistics(player)
            marker = "👑" if player == self.engine.turn_system.get_current_player() else "  "
            ai_marker = "[AI]" if self.ai_manager.is_ai_player(player.id) else "[人类]"
            
            print(f"{marker} {stats['name']} {ai_marker}:")
            print(f"    💰 金币: {stats['gold']}")
            print(f"    🏙️ 城市: {stats['cities']}")
            print(f"    🗺️ 领土: {stats['territory']}")
            print(f"    👥 单位: {stats['units']}")


def main():
    """主函数"""
    demo = EnhancedDemo()
    demo.run_demo()


if __name__ == "__main__":
    main()
