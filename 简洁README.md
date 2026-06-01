# 六边形策略游戏 🎮

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-✓%20Passing-green)](tests/)
[![Status](https://img.shields.io/badge/Status-完整框架-brightgreen)](PROJECT_STATUS.md)

一个基于Python的**六边形蜂窝地图多人回合制策略游戏**，完整实现模块化架构，支持AI对战、保存功能等。

## 🚀 立即体验

```bash
# 方式1: 基础演示（2分钟了解游戏）
python demo.py

# 方式2: 交互式游戏（完整体验，推荐）
python interactive_game.py

# 方式3: 增强演示（AI对战+保存功能）
python enhanced_demo.py
```

## ✨ 主要特性

- 🔶 **六边形地图** - 轴向坐标系，多种地形生成算法
- 🤖 **AI对手系统** - 简单/激进策略，智能决策
- 🏛️ **城市建设** - 建城、生产单位、资源管理  
- ⚔️ **战斗系统** - 回合制、数量制战斗，领土占领
- 👁️ **战争迷雾** - 视野限制系统，增加战略深度
- 💾 **游戏保存** - 完整的保存/加载功能
- 🎯 **完整框架** - 8大核心系统，模块化设计

## 📚 文档导航

- 📖 **[详细使用说明](使用说明.md)** - 完整游戏指南和开发文档
- 📋 **[项目介绍](项目介绍.md)** - 项目概览和特性介绍
- 📊 **[项目状态报告](PROJECT_STATUS.md)** - 功能清单和开发进度
- 📝 **[原始需求文档](需求文档.md)** - 设计规格说明

## 🏗️ 系统架构

```text
GameEngine (主引擎)
├── MapSystem      # 六边形地图 + 地形生成器
├── PlayerSystem   # 玩家管理 + 经济系统  
├── UnitSystem     # 移民/士兵单位管理
├── CitySystem     # 城市建设 + 单位生产
├── CombatSystem   # 战斗机制 + 领土占领
├── VisionSystem   # 战争迷雾 + 视野计算
├── TurnSystem     # 回合制流程控制
├── AISystem      ✨ # 多种AI策略
└── SaveSystem    ✨ # 游戏保存/加载
```

## 🎮 游戏演示

```text
=== 回合 3 ===
👑 玩家1 [人类]:
    💰 金币: 85    🏙️ 城市: 1
    🗺️ 领土: 7     👥 单位: {'soldier': 2}

   AI玩家2 [AI]:  
    💰 金币: 120   🏙️ 城市: 1
    🗺️ 领土: 7     👥 单位: {'settler': 1, 'soldier': 1}

可用行动:
1. 查看单位状态    4. 结束回合  
2. 尝试建城
3. 尝试建造单位
```

## 🧪 测试验证

```bash
# 运行所有测试
python -m pytest tests/ -v

# 验证增强功能  
python -m pytest tests/test_enhanced_features.py
```

## 🎯 项目成就

- ✅ **完全实现第一阶段需求** - 纯逻辑引擎，无UI依赖
- ✅ **超额完成功能** - AI系统、保存系统、多种地图生成器
- ✅ **高质量代码** - 模块化设计、完整测试、详细文档
- ✅ **多种体验方式** - 从基础演示到交互式游戏
- ✅ **为UI开发准备** - 架构支持第二阶段可视化

## 🚀 下一步

### 第二阶段: UI系统
- [ ] Pygame可视化界面
- [ ] 六边形地图渲染
- [ ] 鼠标交互操作

### 功能扩展
- [ ] 完整加载系统
- [ ] 网络多人游戏
- [ ] 科技树系统

---

**🎉 功能完整的策略游戏框架！立即开始：`python interactive_game.py`**
