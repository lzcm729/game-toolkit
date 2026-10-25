---
name: game-dev-lessons
description: >
  游戏开发的实战判据与清单：数值模拟与调参、机制准入、经济与奖惩、玩家感知、反馈与界面、玩法验收、评审与试玩节奏，以及讨论设计时的默认倾向。
  A supplement, not the entry point for open-ended design talk: design-discuss leads discussions,
  game-design-theory answers theory questions, game-ui-design covers UI principles, design-iterate runs multi-view reviews.
  Use when running or reading numeric simulations, tuning balance parameters, a tuning change shows no effect,
  simulation and in-game results disagree, checking whether a new mechanic, state, economy rule or threshold
  should be admitted, diagnosing playtest feedback such as "too weak", "didn't notice", "confusing",
  or writing acceptance criteria for a gameplay feature.
  触发：数值模拟、调参、改了没效果、模拟和实机对不上、新机制准入、经济与奖惩、阈值、试玩反馈、玩家没注意到、玩法验收。
---

# 游戏开发实战经验

在真实项目里跑模拟、调参、评审、试玩时踩出来的判据与清单，已去掉项目锚点，可直接用在别的游戏项目上。game-design-theory 给的是书本框架，这里给的是落到实操的判据。

**项目裁决优先。** 每一条都是默认倾向；和项目已经拍板的口径冲突时，以项目为准。

按场景找条目，只读对应的参考文件。

## 数值模拟与调参 → [references/sim-and-tuning.md](references/sim-and-tuning.md)

1. 模拟结论要能复现，样本要够
2. 模拟代理只会用它认识的东西，新机制要接进决策模型
3. 快慢两套工具结论相反时，分歧本身就是诊断信号
4. 调参：先用极值测杠杆动不动，再二分收敛
5. 数值是放大系数，结构才是放大器：加料前按杠杆从高到低排除

## 机制与经济 → [references/mechanics-and-economy.md](references/mechanics-and-economy.md)

6. 机制准入与健康检查：一句话说不清的机制是设计欠债
7. 经济、奖惩与阈值的设计清单
13. 多出口资源的量尺、需求环与漏斗、软边、商店靠升级还是靠欲望、共同终点后休憩、归属只留一个定义

## 玩家感知与反馈 → [references/player-facing.md](references/player-facing.md)

8. 玩家感知到了才算做完
9. 反馈与界面的判断标准

## 验收与评审 → [references/acceptance-and-review.md](references/acceptance-and-review.md)

10. 游戏侧的验收：验完整的消费链，按感知通道选测量方式
11. 设计评审与试玩的节奏；判定条件只用玩家看得见的信息

## 讨论设计的默认方式 → [references/discussing-design.md](references/discussing-design.md)

12. 先结构后内容；规格只写客观动作；要重做的系统先按现状认；关系词先问清、先框架后细节、推理链回查起点、结论跟证据、讲规则带例子（design-discuss 讨论时会指到这一条）

## 来源

作者在一个 Godot 塔防项目（2026-04 至 07，约 450 条经验）和一个 UE 多人项目里积累的经验，2026-09 去掉项目锚点后收入；第 13 条与第 12 条的后五点来自 2026-10-25 那个 UE 项目的一次资源结构讨论。
