"""
交互式游戏控制器
提供更好的命令行界面
"""
from typing import List, Optional
from src.game_engine import GameEngine
from src.models import GameAction, ActionType, UnitType, HexCoord
from src.utils import get_player_statistics, format_coordinates


class InteractiveController:
    """交互式游戏控制器"""
    
    def __init__(self):
        self.engine = GameEngine()
        self.running = False
    
    def start_game(self):
        """启动交互式游戏"""
        print("=== 六边形策略游戏 ===")
        print()
        
        # 获取玩家信息
        player_names = self._get_player_names()
        if not player_names:
            return
        
        # 获取地图设置
        map_settings = self._get_map_settings()
        
        # 初始化游戏
        success = self.engine.initialize_game(
            player_names, 
            map_seed=map_settings.get('seed')
        )
        
        if not success:
            print("游戏初始化失败！")
            return
        
        print("游戏初始化成功！")
        self.running = True
        
        # 主游戏循环
        self._game_loop()
    
    def _get_player_names(self) -> List[str]:
        """获取玩家名称"""
        print("请输入玩家信息：")
        
        player_count = 0
        while player_count < 2 or player_count > 4:
            try:
                player_count = int(input("玩家数量 (2-4): "))
                if player_count < 2 or player_count > 4:
                    print("玩家数量必须在2-4之间")
            except ValueError:
                print("请输入有效数字")
        
        player_names = []
        for i in range(player_count):
            while True:
                name = input(f"玩家 {i+1} 名称: ").strip()
                if name and name not in player_names:
                    player_names.append(name)
                    break
                elif name in player_names:
                    print("玩家名称重复，请重新输入")
                else:
                    print("玩家名称不能为空")
        
        return player_names
    
    def _get_map_settings(self) -> dict:
        """获取地图设置"""
        print("\n地图设置：")
        
        # 地图类型
        print("1. 标准地图")
        print("2. 岛屿地图")
        print("3. 随机地图")
        
        map_type = "perlin"  # 默认
        while True:
            try:
                choice = input("选择地图类型 (1-3, 默认1): ").strip()
                if choice == "" or choice == "1":
                    map_type = "perlin"
                    break
                elif choice == "2":
                    map_type = "island"
                    break
                elif choice == "3":
                    map_type = "random"
                    break
                else:
                    print("请输入1-3")
            except:
                break
        
        # 随机种子
        seed_input = input("随机种子 (留空为随机): ").strip()
        seed = None
        if seed_input:
            try:
                seed = int(seed_input)
            except ValueError:
                seed = None
        
        # 更新引擎地图系统
        self.engine.map_system.generator_type = map_type
        
        return {"seed": seed, "type": map_type}
    
    def _game_loop(self):
        """主游戏循环"""
        while self.running and not self.engine.game_over:
            self._display_game_state()
            
            current_player = self.engine.turn_system.get_current_player()
            if not current_player:
                break
            
            print(f"\n轮到 {current_player.name} 行动")
            self._show_player_options(current_player)
            
            action = self._get_player_action(current_player)
            if action:
                success = self.engine.execute_action(action)
                if success:
                    print("✓ 行动执行成功")
                else:
                    print("✗ 行动执行失败")
            
            input("\n按回车继续...")
        
        # 游戏结束
        if self.engine.game_over:
            print(f"\n🎉 游戏结束！获胜者：{self.engine.winner.name if self.engine.winner else '无'}")
        else:
            print("\n游戏已退出")
    
    def _display_game_state(self):
        """显示游戏状态"""
        print("\n" + "="*50)
        print(f"回合 {self.engine.turn_system.current_turn}")
        print("="*50)
        
        # 显示所有玩家状态
        for player in self.engine.player_system.players:
            stats = get_player_statistics(player)
            current_marker = "👑 " if player == self.engine.turn_system.get_current_player() else "   "
            
            print(f"{current_marker}{stats['name']}:")
            print(f"    💰 金币: {stats['gold']}")
            print(f"    🏙️  城市: {stats['cities']}")
            print(f"    🗺️  领土: {stats['territory']}")
            print(f"    👥 单位: {stats['units']}")
    
    def _show_player_options(self, player):
        """显示玩家可选行动"""
        print("\n可用行动:")
        print("1. 查看单位")
        print("2. 移动单位") 
        print("3. 建立城市")
        print("4. 城市生产")
        print("5. 查看地图信息")
        print("6. 结束回合")
        print("0. 退出游戏")
    
    def _get_player_action(self, player) -> Optional[GameAction]:
        """获取玩家行动"""
        while True:
            try:
                choice = input("\n选择行动 (0-6): ").strip()
                
                if choice == "0":
                    self.running = False
                    return None
                elif choice == "1":
                    self._show_units(player)
                elif choice == "2":
                    return self._create_move_action(player)
                elif choice == "3":
                    return self._create_build_city_action(player)
                elif choice == "4":
                    return self._create_build_unit_action(player)
                elif choice == "5":
                    self._show_map_info(player)
                elif choice == "6":
                    return GameAction(
                        player_id=player.id,
                        action_type=ActionType.END_TURN,
                        params={}
                    )
                else:
                    print("无效选择，请重试")
            except KeyboardInterrupt:
                self.running = False
                return None
    
    def _show_units(self, player):
        """显示玩家单位"""
        print(f"\n{player.name} 的单位:")
        if not player.units:
            print("  无单位")
            return
        
        for i, unit in enumerate(player.units):
            coord_str = format_coordinates(unit.position)
            print(f"  {i+1}. {unit.unit_type.value} 在 {coord_str} (移动力: {unit.movement_points}/{unit.max_movement_points})")
    
    def _create_move_action(self, player) -> Optional[GameAction]:
        """创建移动行动"""
        if not player.units:
            print("没有可移动的单位")
            return None
        
        self._show_units(player)
        
        try:
            unit_idx = int(input("选择单位编号: ")) - 1
            if unit_idx < 0 or unit_idx >= len(player.units):
                print("无效单位编号")
                return None
            
            unit = player.units[unit_idx]
            
            print("输入目标坐标:")
            q = int(input("  q: "))
            r = int(input("  r: "))
            
            return GameAction(
                player_id=player.id,
                action_type=ActionType.MOVE_UNIT,
                params={
                    "unit_id": unit.id,
                    "target": [q, r]
                }
            )
        except (ValueError, IndexError):
            print("输入无效")
            return None
    
    def _create_build_city_action(self, player) -> Optional[GameAction]:
        """创建建城行动"""
        settlers = [unit for unit in player.units if unit.unit_type == UnitType.SETTLER]
        
        if not settlers:
            print("没有可用的移民")
            return None
        
        print("可用移民:")
        for i, settler in enumerate(settlers):
            coord_str = format_coordinates(settler.position)
            print(f"  {i+1}. 移民 在 {coord_str}")
        
        try:
            settler_idx = int(input("选择移民编号: ")) - 1
            if settler_idx < 0 or settler_idx >= len(settlers):
                print("无效移民编号")
                return None
            
            settler = settlers[settler_idx]
            
            return GameAction(
                player_id=player.id,
                action_type=ActionType.BUILD_CITY,
                params={"unit_id": settler.id}
            )
        except (ValueError, IndexError):
            print("输入无效")
            return None
    
    def _create_build_unit_action(self, player) -> Optional[GameAction]:
        """创建建造单位行动"""
        if not player.cities:
            print("没有城市")
            return None
        
        print("可用城市:")
        for i, city in enumerate(player.cities):
            coord_str = format_coordinates(city.center_tile)
            print(f"  {i+1}. 城市 在 {coord_str}")
        
        try:
            city_idx = int(input("选择城市编号: ")) - 1
            if city_idx < 0 or city_idx >= len(player.cities):
                print("无效城市编号")
                return None
            
            city = player.cities[city_idx]
            
            print("建造单位:")
            print("1. 移民 (50金)")
            print("2. 士兵 (30金)")
            
            unit_choice = input("选择单位类型 (1-2): ")
            
            if unit_choice == "1":
                unit_type = UnitType.SETTLER
            elif unit_choice == "2":
                unit_type = UnitType.SOLDIER
            else:
                print("无效选择")
                return None
            
            return GameAction(
                player_id=player.id,
                action_type=ActionType.BUILD_UNIT,
                params={
                    "city_id": city.id,
                    "unit_type": unit_type.value
                }
            )
        except (ValueError, IndexError):
            print("输入无效")
            return None
    
    def _show_map_info(self, player):
        """显示地图信息"""
        state = self.engine.get_visible_state(player.id)
        
        land_count = sum(1 for tile in state.map_tiles.values() 
                        if tile.terrain_type.value == "land")
        ocean_count = len(state.map_tiles) - land_count
        
        print(f"\n地图信息:")
        print(f"  总地块: {len(state.map_tiles)}")
        print(f"  陆地: {land_count}")
        print(f"  海洋: {ocean_count}")
        print(f"  可见地块: {len(player.vision_tiles)}")


def main():
    """主函数"""
    controller = InteractiveController()
    controller.start_game()


if __name__ == "__main__":
    main()
