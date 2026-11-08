---
name: game-design-theory
description: >
  Game design knowledge from four books, by design task: Rouse, Sylvester (Designing Games), Schell (lenses), Meadows (Thinking in Systems). Use when judging whether a design is fun, deep or elegant; player psychology, experience, emotion, immersion, interest curves and pacing; decision quality and information balance; skill depth, difficulty, onboarding and failure; balance, fairness and degenerate or dominant strategies; multiplayer counters, yomi, griefing and skill gaps; rewards, reinforcement schedules and motivation; story vs mechanics, emergent, branching and non-linear narrative, characters; interface metaphor, signals and control feel; market positioning against competitors; development process: planning, iteration, prototypes and greyboxes, playtesting, metrics, what to build first, who decides; diagnosing system problems (economy inflation, balance escalation, retention spirals) via stocks, flows and feedback loops, and finding leverage points. NOT for writing code or engine-specific implementation.
---

# Game Design Theory Skill

A design consulting framework based on four foundational books:
- **Richard Rouse III** - "Game Design: Theory & Practice"
- **Tynan Sylvester** - "Designing Games: A Guide to Engineering Experiences"
- **Jesse Schell** - "The Art of Game Design: A Book of Lenses" (3rd Edition)
- **Donella H. Meadows** - "Thinking in Systems: A Primer" *(systems thinking — not a game design book; bridged to game systems by this skill's maintainers)*

## When to Use This Skill

- Evaluating game concepts for player appeal
- Designing gameplay mechanics and systems
- Analyzing why a game is or isn't fun
- Balancing difficulty and challenge
- Creating non-linear experiences
- Integrating story with gameplay
- Balance, multiplayer interaction, interface signals, market positioning, team and process decisions (Sylvester cards)
- Planning and conducting playtesting
- Making design trade-off decisions
- Diagnosing economy inflation, power creep, player retention spirals (Meadows)
- Choosing **what to change** for maximum leverage in a game system (Meadows)
- Identifying which of the 8 system traps a broken game mechanic falls into

## Core Philosophy

Games are about **player experience**, not designer intention. The goal is to merge the "designer's story" with the "player's story"—allowing players to feel authorship over their experience while guided by thoughtful design.

> "Not to make something sell, something very popular, but to love something, and make something that we creators can love. It's the very core feeling we should have in making games." — Shigeru Miyamoto

## Quick Reference

### Why Players Play
1. **Challenge** - Engaging the mind, learning through problem-solving
2. **Socialization** - Shared experiences, connection with others
3. **Dynamic Solitary Experience** - Interactive engagement without social demands
4. **Bragging Rights** - Achievement, mastery, self-satisfaction
5. **Emotional Experience** - Tension, catharsis, meaningful feelings
6. **Fantasy** - Escapism, becoming someone else, safe experimentation

### What Players Expect
- A **consistent world** with predictable cause-and-effect
- Clear **understanding of boundaries** and possible actions
- **Reasonable solutions** to work (multiple paths to success)
- **Direction** without hand-holding
- **Incremental progress** toward goals
- **Immersion** maintained throughout
- A **fair chance** at success
- To **do**, not to watch
- To **not get hopelessly stuck**

### Elements of Good Gameplay
- **Emergence**: Systems interacting to create unplanned, player-discovered solutions
- **Non-linearity**: Multiple paths, solutions, orderings, and optional content
- **Appropriate Reality Modeling**: Only simulate what serves fun
- **Teaching Through Play**: First minutes make or break engagement
- **Transparent Controls**: Input that disappears into instinct

## Quick Reference: Sylvester

### The Experience Engine
```
Mechanics → Events → Emotions → Experience
```
Designers design mechanics; mechanics and players generate events; an event's emotional force comes from the human values it changes.

### 核心原则（各条的做法和出处在选卡表的卡里）
1. 设计师只能设计生成体验的机制，不能直接设计体验；事件的情绪力量来自它改变的、玩家在乎的东西。
2. 每个机制都有成本，最贵的是玩家的注意力；好设计让机制相乘而不是相加。
3. 系统驱动的决定要求结果部分可预测：系统一致、可理解，信息既不饥饿也不过剩；预定义的剧情选择不套这条，另行评估。
4. 平衡的对象是情境中的策略；退化策略让决策消失；平衡要先选目标技能段。
5. 外在奖励会挤掉内在满足：只奖励玩家本来就想做、游戏检测得到的事；没被传达出去的事件等于没发生。
6. 体验无法事先算准：按不确定性选规划视距，用灰盒和测试从现实学习，先做依赖栈底的核心，决定交给拥有相关知识的人。
7. 书里的一切都是需要经验校准的模型；原书没给的阈值和判据由设计者判断，不要编。决策时长分级、试玩场次这类数字是作者的经验估计。

## Quick Reference: Schell

### The Elemental Tetrad
```
    Aesthetics
       /\
      /  \
Story --- Technology
      \  /
       \/
   Mechanics
```
All four elements are essential and equally important. Each supports the others.

### Core Design Lenses
| Lens | Question |
|------|----------|
| #1 Emotion | What emotions should the player feel? |
| #2 Essential Experience | What experience do I want the player to have? |
| #4 Surprise | What will surprise players? |
| #5 Fun | What makes my game fun? |
| #6 Curiosity | What questions does my game put in players' minds? |
| #11 Unification | Does every element work toward a common theme? |

### Interest Curve Pattern
```
Interest
    |     (G) Grand Finale
    |    /
    |   / (E)
    |  /  /\
    | /  /  \ (F)
    |/  / (C) \
(B)/  /         \
  /  /            \ (H)
 / (D)
(A)_________________ Time
```
**Key points:** A=Entry, B=Hook, C/E=Rising peaks, D/F=Rest, G=Climax, H=Resolution

### Seven Game Mechanics
1. **Space** - Where the game takes place
2. **Time** - Turns, real-time, clocks, races
3. **Objects** - Nouns of the game with attributes and states
4. **Actions** - Verbs players can perform
5. **Rules** - Define space, objects, actions, consequences
6. **Skill** - Physical, mental, social
7. **Chance** - Uncertainty, probability, risk

### Rule of the Loop
> "The more times you test and improve your design, the better your game will be."

**Formal Loop:** State problem → Brainstorm → Choose → List risks → Build prototypes → Test → Repeat

### Key Mantras (Schell)
- "Experience is the ultimate goal of game design."
- "The more times you test and improve, the better your game will be."
- "WUBALEW: When Useful, But At Least Every Week." (playtesting)
- "Quick and dirty, not slow and beautiful." (prototyping)
- "The player is always right about their experience. They're often wrong about why."

## Quick Reference: Meadows

> **Note**: Meadows' *Thinking in Systems* is not a game design book — examples are about banks, populations, oil, fisheries. The `meadows-*` references below layer a **"Game Design Application"** section onto each concept, clearly marked as non-original bridging content.

### The Three-Part System
```
Elements → Interconnections → Function / Purpose
(visible)   (critical)          (most hidden, most powerful)
```
Changing elements = weakest lever. Changing purpose = strongest. The purpose is inferred from behavior, not stated aims.

### Stocks & Flows (Bathtub Law)
- **Stock** = cumulative quantity (HP, gold, XP, inventory, reputation)
- **Flow** = rate of change (damage, drops, consumption, growth)
- **Inflows > outflows** → stock rises; reversed → falls; equal → dynamic equilibrium
- Most "resource inflation" is actually a **missing sink** (outflow), not excess tap

### The Two Feedback Loop Types
| Loop | Role | Game Example |
|---|---|---|
| **Balancing (B)** | Goal-seeking, stabilizing | HP regen, price equilibrium, rubber-banding |
| **Reinforcing (R)** | Self-amplifying, exponential | Snowball kills, compound interest, network effects |

### The 12 Leverage Points (weak → strong)
```
12. Numbers (parameters)        ← 90% of designers spend time here
11. Buffers (pool sizes)
10. Stock-and-flow structure
 9. Delays (cooldowns, queues)
 8. Balancing loops
 7. Reinforcing loops           ← slowing growth > strengthening brakes
 6. Information flows           ← Dutch electric-meter lesson
 5. Rules (mechanics, laws)
 4. Self-organization (UGC, emergent play)
 3. Goals (what the system tries to do)
 2. Paradigm (team's "what is a good game")
 1. Transcending paradigms
```
**Counter-intuitive rule**: change happens faster at higher levels but resistance is stronger.

### The 8 System Traps
| # | Trap | Recognizer | Antidote |
|---|---|---|---|
| 1 | Policy Resistance | Every fix triggers counter-pull | Find a shared larger goal |
| 2 | Tragedy of the Commons | Shared resource depleted | Privatize or regulate |
| 3 | Drift to Low Performance | Standards quietly slip ("比上次不差") | Anchor to best historical performance |
| 4 | Escalation | Exponential one-upmanship | Unilateral disarm or negotiate |
| 5 | Success to the Successful | Winner takes all | Reset periodically (seasons, leagues) |
| 6 | Shifting the Burden (Addiction) | Intervention erodes self-healing | Restore intrinsic capacity |
| 7 | Rule Beating | Letter vs spirit gamed | Read as feedback, redesign rules |
| 8 | Seeking the Wrong Goal | System faithful to wrong metric | Redefine what to measure |

### 3 System Characteristics (what makes systems work)
- **Resilience** — absorbs shocks; lost for short-term optimization
- **Self-organization** — evolves new structure; crushed by over-control
- **Hierarchy** — modular nesting; fails via sub-optimization or over-centralization

### Key Mantras (Meadows)
- "Before you disturb the system in any way, watch how it behaves."
- "**System structure is the source of system behavior. System behavior reveals itself as a series of events over time.**"
- "Slowing the reinforcing loop is a more powerful lever than strengthening the balancing one."
- "Missing information is the single most common cause of system malfunction."
- "Systems can't be controlled, but they can be designed and redesigned."
- "We can't surge forward with certainty into a world of no surprises, but we can expect surprises and learn from them and even profit from them."
- "**Dance with the system.**"

## Detailed References

### Richard Rouse III (Player-Centric Design)

- **Player Psychology**: See [references/player-psychology.md](references/player-psychology.md) for why players play and what they expect
- **Gameplay Elements**: See [references/gameplay-elements.md](references/gameplay-elements.md) for emergence, non-linearity, and system design
- **Storytelling**: See [references/storytelling.md](references/storytelling.md) for in-game narrative techniques
- **Playtesting**: See [references/playtesting.md](references/playtesting.md) for testing practices and balancing
- **Design Principles**: See [references/design-principles.md](references/design-principles.md) for focus, teaching, and I/O design

### Tynan Sylvester（Designing Games）：选卡表

47 张能力卡，一张卡管一类任务，每个分支写清输入、步骤、输出、原书页码和边界。按下表「用户在问」找对口的卡；两张都像时看「和近邻怎么分」，两条路线都能完成任务就都可以用。
**怎么用卡**：回答围绕用户的处境，先给你自己的专业判断和具体做法，书外的实操（算一个例子、查数据、估成本、排期）照常给；卡用来补方法、校正判断、提供依据，不是回答的模板。不要按卡的分段复述这本书，卡里没写的不等于不能答。书名、作者和页码只在用户问出处或需要核对时给。
术语和只作参考的作者观点（原书讲了、但没给出可照做步骤的）在 [sylvester-notes.md](references/sylvester-notes.md)。卡里标「原书未说明」的地方可以给你自己的建议，但要说明不出自本书。

**体验与情绪**

| 用户在问 | 读这张卡 | 和近邻怎么分 |
|---|---|---|
| 这段游玩为什么没感觉；情绪不够强，怎么找原因；怎么拆一段体验、复盘一个模式 | [sylvester-experience-analysis.md](references/sylvester-experience-analysis.md) | 关键价值已锁定、比赛早早定局；顿悟揭示 → `sylvester-suspense-and-insight.md` |
| 比赛早早定局，后半段没悬念；本该紧张的高光时刻没人在意；怎么设计恍然大悟的揭示 | [sylvester-suspense-and-insight.md](references/sylvester-suspense-and-insight.md) | 落后方长时间必败、失败惩罚、怎么修已锁定的局面 → `sylvester-difficulty-and-failure.md` |
| 要不要靠奇观、特效、精美美术提情绪；新技术当卖点行不行；这种情绪该靠玩法还是靠剧情 | [sylvester-emotional-triggers-and-fiction.md](references/sylvester-emotional-triggers-and-fiction.md) | 美术让玩家看不懂机制、视觉线索前后不一 → `sylvester-mechanic-metaphor.md` |
| 体验太平、没有高潮；一整局都是同一种情绪；怎么让机制自己生成节奏曲线 | [sylvester-intensity-and-immersion.md](references/sylvester-intensity-and-immersion.md) | 秒级的决策节奏：等待、冷却、被淹没 → `sylvester-pacing-problems.md`；逐秒测绘 → `sylvester-decision-rhythm-mapping.md` |

**优雅与机制成本**

| 用户在问 | 读这张卡 | 和近邻怎么分 |
|---|---|---|
| 这个机制要不要加、值不值；原型手感很好的机制能不能写进正式设计；两个功能差不多的方案留哪个 | [sylvester-mechanic-cost-elegance.md](references/sylvester-mechanic-cost-elegance.md) | 已有机制强弱怎么改，或加更多选项能否加深度（第 6 章：有两个可行策略后再加没有内在价值，p.161–162）→ `sylvester-balance-change-review.md` |

**技能、难度与新手**

| 用户在问 | 读这张卡 | 和近邻怎么分 |
|---|---|---|
| 新手进不来，到底卡在哪；这个游戏深度够不够，高手还有没有提升空间；我们需不需要做成易学难精 | [sylvester-skill-range.md](references/sylvester-skill-range.md) | 学会一层后没有下一层、玩具型游戏的自定目标 → `sylvester-skill-depth-layers.md` |
| 玩家学会以后就腻了，深度断在哪；高手玩法没有新层次怎么办；单人游戏想做到能玩上百小时现实吗 | [sylvester-skill-depth-layers.md](references/sylvester-skill-depth-layers.md) | 天花板在哪、区间要不要宽 → `sylvester-skill-range.md` |
| 教程怎么做才不烦人；玩家第一关、前十分钟就走；开局教学弹窗太多、手把手太细 | [sylvester-onboarding-and-opening.md](references/sylvester-onboarding-and-opening.md) | 先弄清新手要会什么 → `sylvester-skill-range.md` 分支 1 |
| 游戏太难或太简单，问题出在哪段；难度怎么调，要不要做难度选择或动态难度；一个挑战新手过不了、高手没挑战 | [sylvester-difficulty-and-failure.md](references/sylvester-difficulty-and-failure.md) | 区间要不要宽、该用哪类手段 → `sylvester-skill-range.md`；教程 → `sylvester-onboarding-and-opening.md` |

**叙事**

| 用户在问 | 读这张卡 | 和近邻怎么分 |
|---|---|---|
| 这段剧情用过场还是实机表现；玩家会不会打断或错过剧情事件，怎么预案；过场太多、节奏走走停停，能改成什么 | [sylvester-narrative-tool-allocation.md](references/sylvester-narrative-tool-allocation.md) | 世界叙事具体怎么布置、线索怎么分层 → `sylvester-world-narrative.md` |
| 怎么用环境和物件讲一个地方的过去；玩家不按顺序看到线索，故事还拼不拼得出；世界观自不自洽，核心能力在世界里怎么解释 | [sylvester-world-narrative.md](references/sylvester-world-narrative.md) | 某块故事该用世界叙事还是脚本 → `sylvester-narrative-tool-allocation.md` |
| 怎么让玩家自己讲出故事；沙盒或模拟游戏没有故事感；要不要给单位起名、加性格标签 | [sylvester-emergent-story.md](references/sylvester-emergent-story.md) | 某块故事该交给涌现还是脚本、世界叙事；拆一段游玩逐段归因 → `sylvester-narrative-tool-allocation.md` |
| 剧情或任务的先后顺序怎么保证；线性、轴辐还是开放世界，结构怎么排；分支剧情太多写不过来 | [sylvester-story-structure.md](references/sylvester-story-structure.md) | 某块故事用什么手段讲 → `sylvester-narrative-tool-allocation.md` |
| 玩家做了角色绝不会做的事，怎么办；剧情时刻玩家朝 NPC 开枪、跳桌子、捣乱；角色是好人，机制却奖励乱杀乱抢 | [sylvester-desk-jumping-and-characters.md](references/sylvester-desk-jumping-and-characters.md) | 多人里有人追自己的目标、弄坏别人的局 → `sylvester-divergent-goals-griefing.md` |

**决策与节奏**

| 用户在问 | 读这张卡 | 和近邻怎么分 |
|---|---|---|
| 这个选择有没有意思，玩家其实有没有得选；这段关卡是不是太线性，只有一条路；结果太随机或太必然，要不要加随机 | [sylvester-decision-quality-audit.md](references/sylvester-decision-quality-audit.md) | 系统一致、可理解，选择仍难懂或太明显，原因在信息多少 → `sylvester-information-balance.md` |
| 玩家乱试乱选、要看攻略才会玩，怎么办；试玩很顺、没人卡关，但没有张力；开局要选职业或天赋，玩家什么都还不知道 | [sylvester-information-balance.md](references/sylvester-information-balance.md) | 结果难预测是因为规则不一致或太复杂 → `sylvester-decision-quality-audit.md` |
| 谜题玩家想不到解法、只能乱试；玩家去试游戏里没有的交互；道德选择影响数值后要不要给明确信息 | [sylvester-fiction-and-metagame-info.md](references/sylvester-fiction-and-metagame-info.md) | 机制内部的信息量问题（视野、明牌、数值显示）→ `sylvester-information-balance.md` |
| 等待、冷却、过场、被控时玩家没事做；试玩者手忙脚乱、压力太大；回合制太慢、每回合操作太碎、有人长考 | [sylvester-pacing-problems.md](references/sylvester-pacing-problems.md) | 要整段测绘节奏、逐秒拆解、实现前推演 → `sylvester-decision-rhythm-mapping.md` |
| 这段玩法的节奏和手感怎么评估；还没做出来，怎么预判节奏和空档；拆一段对局或标杆游戏，看它为什么耐玩 | [sylvester-decision-rhythm-mapping.md](references/sylvester-decision-rhythm-mapping.md) | 症状已知（等待、溢出、微操、单调），要修 → `sylvester-pacing-problems.md` |

**平衡**

| 用户在问 | 读这张卡 | 和近邻怎么分 |
|---|---|---|
| 这个单位、武器或卡牌太强，怎么削；该不该削弱或加强某样东西；加一个新单位或新选项能不能加深度 | [sylvester-balance-change-review.md](references/sylvester-balance-change-review.md) | 还不知道哪里不平衡，要找一招鲜、看收益地形 → `sylvester-degenerate-strategy-hunt.md` |
| 有没有一招鲜、无脑最优解；高手都用同一个套路，是不是不平衡；新加的强力单位或卡牌会不会让决策消失 | [sylvester-degenerate-strategy-hunt.md](references/sylvester-degenerate-strategy-hunt.md) | 已经知道哪里强，要定怎么改、动哪个属性、要不要砍 → `sylvester-balance-change-review.md` |
| 要不要做成对称；非对称游戏要平衡到什么程度，能不能刻意不公平；聚会模式和排位模式的公平要求一样吗 | [sylvester-balance-target.md](references/sylvester-balance-target.md) | 找出某个技能段的退化策略、按段列表 → `sylvester-degenerate-strategy-hunt.md`（它的分支 2 是这里分支 2 的输入） |

**多人**

| 用户在问 | 读这张卡 | 和近邻怎么分 |
|---|---|---|
| 对抗里某个交锋有没有固定最优解；兵种、技能、招式的克制关系怎么设计；石头剪刀布式克制够不够，要不要再加兵种或姿态 | [sylvester-strategic-interaction-equilibrium.md](references/sylvester-strategic-interaction-equilibrium.md) | 有没有心理博弈、虚张声势、信息战 → `sylvester-yomi-depth.md` |
| 对抗打起来像抛硬币，没有心理博弈；怎么做虚张声势、侦察与反侦察、信息战；多人混战太乱，玩家猜不过来 | [sylvester-yomi-depth.md](references/sylvester-yomi-depth.md) | 交锋有没有固定最优解、克制环怎么搭 → `sylvester-strategic-interaction-equilibrium.md` |
| 玩家刷个人数据，不推团队目标；有人捣乱、坑队友，怎么处理；有人中途掉线或退出，剩下的人玩不下去 | [sylvester-divergent-goals-griefing.md](references/sylvester-divergent-goals-griefing.md) | 新手拖累、高手虐新手、一人失误全队受罚 → `sylvester-skill-gap-interdependence.md` |
| 新手拖累队友、被骂被踢；高手和新手混排体验都差；一人倒下或失误就全队失败，要不要改 | [sylvester-skill-gap-interdependence.md](references/sylvester-skill-gap-interdependence.md) | 有人故意捣乱、刷数据、掉线 → `sylvester-divergent-goals-griefing.md` |

**动机与奖励**

| 用户在问 | 读这张卡 | 和近邻怎么分 |
|---|---|---|
| 玩家在领奖、升级或通关后流失，想找原因；刷到某个阶段就没劲了，想看奖励节奏；几条奖励线会不会同时断档 | [sylvester-reward-schedule-diagnosis.md](references/sylvester-reward-schedule-diagnosis.md) | 某个行为该不该奖励、奖励让玩法变味、玩家为奖励去刷无聊内容 → `sylvester-reward-alignment.md` |
| 要不要给这个行为加成就、积分或奖励；加奖励会不会让玩法变味；玩家为了奖励去刷无聊的事，怎么改 | [sylvester-reward-alignment.md](references/sylvester-reward-alignment.md) | 奖励何时给、玩家在哪个节点流失 → `sylvester-reward-schedule-diagnosis.md` |

**界面与手感**

| 用户在问 | 读这张卡 | 和近邻怎么分 |
|---|---|---|
| 这个机制该做成什么样子玩家才看得懂；玩家分不清哪些东西能交互、哪些是布景；同一种可交互物在不同关卡长得不一样 | [sylvester-mechanic-metaphor.md](references/sylvester-mechanic-metaphor.md) | 谜题解法依赖玩家想到某个虚构推理，或要不要打破类型惯例 → `sylvester-fiction-and-metagame-info.md` |
| 试玩者没看到这个提示，要不要做得更显眼；HUD 太乱，新手说看不过来、老手说信息不够；这条信息（血量、弹药）该放多显眼，要不要随数值变化 | [sylvester-signal-visibility.md](references/sylvester-signal-visibility.md) | 换上美术后看不清敌人、路线 → `sylvester-mechanic-metaphor.md` 分支 3 |
| 想让玩家走这条路，但不想弹提示、不想强制；一路战斗过来，玩家见到该交谈的 NPC 就开枪；不用教程文字怎么教会玩家某个做法 | [sylvester-non-directive-guidance.md](references/sylvester-non-directive-guidance.md) | 可以明说，只是怕玩家漏看 → `sylvester-signal-visibility.md` 分支 4 |
| 按键怎么布局，玩家换工具得停下怎么办；操作不跟手、手感发软、按了没反应；要不要做辅助瞄准或其他输入辅助，怎么做才不被察觉 | [sylvester-controls-feel.md](references/sylvester-controls-feel.md) | 某个武器或单位太强、整体怎么削（辅助只是其中一根杠杆）→ `sylvester-balance-change-review.md` |

**市场与定位**

| 用户在问 | 读这张卡 | 和近邻怎么分 |
|---|---|---|
| 和竞品比我们到底有什么；该做哪几个特色、砍哪几个；这个立项是不是什么都想要 | [sylvester-market-value-focus.md](references/sylvester-market-value-focus.md) | 商业模式或游戏目的给设计什么约束、宣传会给玩家什么预期 → `sylvester-purpose-and-expectations.md` |
| 商业模式或游戏目的对设计有什么约束；非商业项目（展项、教育、艺术）该怎么推设计约束；这个标题会让玩家以为是什么游戏 | [sylvester-purpose-and-expectations.md](references/sylvester-purpose-and-expectations.md) | 和竞品比卖点在哪、该押哪几项 → `sylvester-market-value-focus.md` |

**开发过程**

| 用户在问 | 读这张卡 | 和近邻怎么分 |
|---|---|---|
| 试玩时该观察什么、问什么；自测没新发现了，换人测时我要不要说话；测后访谈怎么问才不诱导，回答怎么读 | [sylvester-playtest-observation.md](references/sylvester-playtest-observation.md) | 写测试协议、找谁测、测几场够、何时停测 → `sylvester-playtest-protocol.md` |
| 我们该用什么开发流程；计划要做多远、迭代周期该多长；我们是规划不够还是规划过度 | [sylvester-process-and-planning-horizon.md](references/sylvester-process-and-planning-horizon.md) | 计划为什么总是过度自信、团队估计总偏乐观 → `sylvester-overplanning-bias.md` |
| 这份计划是不是太自信；团队估计为什么总偏乐观；会上最笃定的人总能定方向，这正常吗 | [sylvester-overplanning-bias.md](references/sylvester-overplanning-bias.md) | 判断项目整体偏欠规划还是偏过度规划、该把视距定多长 → `sylvester-process-and-planning-horizon.md` |
| 一轮迭代怎么定、做到哪、什么时候停；我们的开发流程是不是先做完再测；一场战斗或一个关卡段落怎么一轮轮做出来 | [sylvester-iteration-loop.md](references/sylvester-iteration-loop.md) | 环该多长、计划做多远 → `sylvester-process-and-planning-horizon.md`；计划是否过度自信 → `sylvester-overplanning-bias.md` |
| 原型里哪些部分用灰盒、用什么占位；现在要不要给灰盒加美术、特效、音效；关卡美术什么时候介入，上美术后要测什么 | [sylvester-graybox-and-art-timing.md](references/sylvester-graybox-and-art-timing.md) | 迭代环本身怎么定、战斗场景怎么分阶段 → `sylvester-iteration-loop.md` |
| 一次试玩要定哪些规则、协议怎么写；找谁来测：新人、老玩家还是高手；测几场才够，什么时候能停 | [sylvester-playtest-protocol.md](references/sylvester-playtest-protocol.md) | 试玩现场怎么观察、自测何时切旁观、怎么主持、测后怎么问、建议怎么用 → `sylvester-playtest-observation.md` |
| 这个问题该靠讨论、找资料、做原型、写分析还是测试来弄清楚；要不要开一场辩论会找方案的漏洞，开之前要注意什么；老板想亲自和下属辩方案，合不合适 | [sylvester-knowledge-creation-method.md](references/sylvester-knowledge-creation-method.md) | 试玩怎么组织、找谁、测几场 → `sylvester-playtest-protocol.md`；试玩现场怎么看、怎么问 → `sylvester-playtest-observation.md` |
| 怎么用数据调难度和节奏；要埋哪些点；玩家死在哪、补给放哪，怎么看出来 | [sylvester-metrics-and-telemetry.md](references/sylvester-metrics-and-telemetry.md) | 该靠数据、试玩还是分析来弄清 → `sylvester-knowledge-creation-method.md` |
| 先做哪个系统；动画、美术、关卡现在能不能开做；这些后期系统现在要不要写细 | [sylvester-dependency-stack.md](references/sylvester-dependency-stack.md) | 核心玩法是什么、设计文档怎么组织、营销要提前定 → `sylvester-core-and-backlog.md` |
| 这个游戏的核心玩法到底是什么；原型做出来不好玩，继续改还是推倒重来；有几个可能的核心，先做哪个 | [sylvester-core-and-backlog.md](references/sylvester-core-and-backlog.md) | 先做哪个系统、算上层存活概率、何时加下一个 → `sylvester-dependency-stack.md` |

**团队与决策权**

| 用户在问 | 读这张卡 | 和近邻怎么分 |
|---|---|---|
| 这个设计决定该谁拍板；评审会或决策会该请哪些人；看完一次评审能不能直接给具体改法 | [sylvester-natural-authority.md](references/sylvester-natural-authority.md) | 团队奖金、氛围、士气 → `sylvester-team-motivation.md` |
| 要不要给团队发绩效奖金、按指标奖励或评最佳创意；团队不敢提意见，评审总是一致通过；有人老是弄坏版本、忘了解锁文件，怎么处理 | [sylvester-team-motivation.md](references/sylvester-team-motivation.md) | 给玩家的奖励、成就、积分 → `sylvester-reward-alignment.md`（第 8 章，同一组词的另一种用法） |
| 这个影响面大的设计决定怎么定；哪些决定要开会讨论、哪些当场定；临近内容锁定发现问题，改还是不改 | [sylvester-complex-decisions.md](references/sylvester-complex-decisions.md) | 谁来拍板、会请谁 → `sylvester-natural-authority.md` |

### Jesse Schell (Lens-Based Design)

- **Core Lenses**: See [references/schell-lenses-core.md](references/schell-lenses-core.md) for the Lens approach, 113+ design lenses categorized by topic, how to use lenses for design analysis
- **Experience Design**: See [references/schell-experience-design.md](references/schell-experience-design.md) for experience as ultimate goal, Elemental Tetrad, theme unification, resonance
- **Game Elements**: See [references/schell-game-elements.md](references/schell-game-elements.md) for holographic design, elements interaction, four basic elements
- **Balance**: See [references/schell-balance.md](references/schell-balance.md) for 12 types of balance, fairness, challenge, meaningful choices, punishment
- **Mechanics**: See [references/schell-mechanics.md](references/schell-mechanics.md) for 7 mechanics (Space, Time, Objects, Actions, Rules, Skill, Chance), emergence, secrets
- **Interface**: See [references/schell-interface.md](references/schell-interface.md) for feedback loops, juiciness, primality, channels/dimensions, modes
- **Interest Curves**: See [references/schell-interest-curve.md](references/schell-interest-curve.md) for pacing, hooks, climax design, fractal structure, three factors (inherent interest, poetry, projection)
- **Narrative**: See [references/schell-narrative.md](references/schell-narrative.md) for Story/Game duality, String of Pearls vs Story Machine, Story Stack, indirect control methods
- **Characters**: See [references/schell-characters.md](references/schell-characters.md) for avatar types (ideal form, blank slate), character tips, interpersonal circumplex, status
- **Iteration & Prototyping**: See [references/schell-iteration.md](references/schell-iteration.md) for Rule of the Loop, 10 prototyping tips, risk mitigation, 50% Rule
- **Playtesting**: See [references/schell-playtesting.md](references/schell-playtesting.md) for 6 key questions (Why, Who, When, Where, What, How), WUBALEW, observation/interview methods

### Donella H. Meadows (Systems Thinking)

> Each file preserves the original book's framework, then adds a clearly-marked **"游戏设计应用（非原书内容，后加）"** section bridging Meadows' concepts to game systems. The bridge is the maintainers' contribution, not original Meadows material.

- **Fundamentals**: See [references/meadows-fundamentals.md](references/meadows-fundamentals.md) for stocks & flows, balancing/reinforcing loops, bathtub law, 5 basic system structures (thermostat, population/economy, inventory delays, nonrenewable resource limits, renewable resource dynamics)
- **3 Characteristics**: See [references/meadows-characteristics.md](references/meadows-characteristics.md) for resilience, self-organization, hierarchy — and the common failure modes: over-optimization kills resilience, over-control kills self-organization, sub-optimization kills hierarchy
- **6 Obstacles**: See [references/meadows-obstacles.md](references/meadows-obstacles.md) for the 6 reasons systems surprise us: event-layer thinking, linear bias in nonlinear world, boundary errors, limiting factor blindness, pervasive time delays, bounded rationality
- **8 Traps & Antidotes**: See [references/meadows-traps.md](references/meadows-traps.md) for policy resistance, tragedy of the commons, drift to low performance, escalation, success-to-the-successful, shifting the burden (addiction), rule beating, seeking the wrong goal — each mapped to common game design disasters
- **12 Leverage Points**: See [references/meadows-leverage.md](references/meadows-leverage.md) for the ranked list of where to intervene in a system, from parameters (weakest) to paradigms (strongest) — includes the "where designers spend 90% of time vs where leverage actually is" gap
- **15 Dancing Principles**: See [references/meadows-dancing.md](references/meadows-dancing.md) for the systems-designer's mindset: observe first, expose mental models, respect information, use language carefully, value what's important over what's measurable, embrace complexity, extend time horizon, "don't erode the good"

## Design Evaluation Framework

When evaluating a game design, ask:

1. **Player Motivation**: Which core motivations does this serve? (Challenge, Social, Solitary, Bragging, Emotional, Fantasy)
2. **Expectation Alignment**: Does the design honor what players expect?
3. **Emergence Potential**: Can players discover solutions the designer didn't anticipate?
4. **Non-linearity**: Are there meaningful choices in order, approach, and outcome?
5. **Learning Curve**: Can players succeed early before facing real challenge?
6. **Immersion Maintenance**: What might break suspension of disbelief?
7. **Balance Reality**: Is the simulation serving fun, or drowning in tedium?
8. **Interest Curve**: Does the experience have a hook, rising action, climax, and satisfying resolution?
9. **Elemental Tetrad**: Do Mechanics, Story, Aesthetics, and Technology support each other?
10. **Essential Experience**: What single experience do you want the player to have? Does every element serve it?
11. **System Structure (Meadows)**: What are the stocks, flows, and feedback loops? Are reinforcing loops bounded by balancing loops with appropriate strength and timing?
12. **Leverage Point Selection (Meadows)**: Am I changing parameters (low leverage) when I should change rules, information flows, or goals (high leverage)?
13. **Trap Recognition (Meadows)**: Does this problem fit one of the 8 system traps? If so, apply the corresponding antidote.

## Common Design Pitfalls

| Pitfall | Symptom | Solution |
|---------|---------|----------|
| Overly Linear | Player feels "on rails" | Add order/approach choices |
| Anticipatory-Only Design | Only hardcoded solutions work | Build systems, not cases |
| Reality Obsession | Tedious simulation of mundane details | Model only what's fun |
| Inconsistent Rules | Same action gives different results randomly | Ensure predictable cause-effect |
| Tutorial Overload | Players skip to "real game" | Teach through safe early gameplay |
| Hidden Information | Players fail without knowing why | Provide clear feedback |
| Designer's Ego | "Players will adjust" | Playtest with fresh eyes |
| Difficulty Blindness | "It's not that hard" | Your game is too hard. Always. |
| Parameter Tweaking (Meadows #12) | Keep adjusting numbers, problem persists | Look for higher leverage (rules, information, goals) |
| Unchecked Reinforcing Loop (Meadows) | Snowball / power creep / winner-takes-all | Slow the loop, don't just strengthen its brake |
| Missing Sink (Meadows) | Economy inflation despite tweaking drops | Design new drain mechanics, not reduce source |
| KPI-Driven Hollowing (Meadows #8) | Metrics up, players unhappy | Question whether the metric captures actual value |
| Eroding Standards (Meadows #3) | "Just as good as last version" | Anchor to best historical baseline, not recent past |

## Key Mantras

- **"Your game is too hard."** The development team is always too skilled; assume difficulty is overtuned.
- **"Show, don't tell."** In-game storytelling > cut-scenes > manuals.
- **"Less is more."** Every control added must justify its complexity cost.
- **"Players want to do, not watch."** Minimize non-interactive sequences.
- **"The player's story matters most."** Let their choices shape the experience.
- **"Watch the system first."** (Meadows) Before any intervention, study its historical behavior.
- **"Structure drives behavior."** (Meadows) Don't fix events — fix the structure that produces them.
- **"Dance with the system."** (Meadows) You cannot control complex systems, but you can design, redesign, and learn from them.
