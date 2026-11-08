<!-- capability_id: cap.designing-games.skill-gap-interdependence | revision: 1 | status: active | units: u07-12, u07-13 -->

# 技能差与相互依赖：新手拖累、高手虐菜、一人失误全队受罚

> **怎么用这张卡**：它是方法和书中依据的来源之一，不是回答的模板。回答围绕用户的处境：先给你自己的专业判断和具体做法，书外的实操（算一个例子、查数据、估成本）照常给；再用这张卡补方法、校正判断。不要按卡的分段复述这本书；卡里没写的，不等于不能答。书名和页码只在用户要出处时给。

## R — 原文 (Reading)

> There are a number of ways to reduce the impact of skill differentials. The first few are all about shrinking the skill differential itself.
>
> 译：减轻技能差的影响有好几种办法。头几种都是去缩小技能差本身。
>
> — Tynan Sylvester, *Designing Games*, Ch7 Multiplayer / Skill Differentials, p.201

> Many people treat interdependency between players as an unalloyed good—but it’s not. Because while interdependency can create a feeling of shared victory, it also requires that we suffer because of the failures of others.
>
> 译：很多人把玩家之间的相互依赖当成纯粹的好事，其实不是。相互依赖能带来共同胜利的感觉，也意味着我们得为别人的失败受罪。
>
> — Tynan Sylvester, *Designing Games*, Ch7 Multiplayer / Skill Differentials, p.202

> The best result is a system that eliminates that shared failure while permitting shared victory.
>
> 译：最好的结果是一套去掉共同失败、又允许共同胜利的系统。
>
> — Tynan Sylvester, *Designing Games*, Ch7 Multiplayer / Skill Differentials, p.202

## I — 方法骨架 (Interpretation)

这张卡回答「新手和高手被绑在一起时，怎样不让双方互相毁掉体验」。作者把技能差（skill differential）算作一种特殊的分歧目标：新手想学会、别被逼太紧，高手想打一场有深度的胜仗，两种目标一冲突，新手挨骂，高手要么无聊、要么恼火（p.201）。只要玩家相互依赖、成败又靠技能，这个问题就会出现，所以极常见（p.201）。

作者给的顺序是先缩小技能差本身（分支 1），缩不了再降低相互依赖，让差距没那么要紧（分支 2）。这两个分支也是 `sylvester-divergent-goals-griefing.md` 分支 3 压力测试里「有人缺关键技能」一项的对策。

## A1 — 书中案例 (Past Application)

- **分支 1｜受技能差困扰的好游戏与四种手段（转述，p.201–202）**：作者说 Left 4 Dead、星际 2 团队战、Black Ops 僵尸模式都是好设计，也都受技能差困扰。WoW 前几个小时可以独自玩，学会基本后再选择组队，新人不必在任何队里担角色；很多游戏先有单人模式，玩家在那里练手，失败不影响别人。L4D 的自适应训练在 Hunter 扑倒队友时闪出提示叫新手去救，完成目标、帮队友、拿资源这些关键动作都有提示，新手枪法再差也不至于全无头绪。匹配按经验等级和胜率配对，作者说概念简单、做好极难。原书未说明各手段的实测效果。
- **分支 2｜Halo: Reach（转述，p.202）**：团队战里玩家大多各打各的，偶尔两三人临时结盟、打倒一个敌人再散开。作者称这是可选、短期的合作：有共同胜利，又不常强制共同失败。

## A2 — 触发场景 (Future Trigger) ★

**情境**

1. 合作或团队模式里新手常被骂、被踢。
2. 高手抱怨队友拖后腿，或混排对局一边倒。
3. 设计里有「一人倒下全队失败」「每人都必须到位」的机制。
4. 要定新手多久以后才进组队内容。
5. 讨论匹配、新手期、关键时刻提示。

**语言信号**

- 新手拖累队友 ／ 高手虐新手 ／ 猪队友 ／ 一人失误全队受罚 ／ 要不要强制组队 ／ 新手什么时候进多人
- skill gap ／ skill differential ／ matchmaking ／ onboarding ／ carry ／ shared failure ／ interdependence ／ forced co-op

**与相邻卡的区分（初稿）**

- 有人故意捣乱、刷数据、掉线 → `sylvester-divergent-goals-griefing.md`
- 平衡该照顾高手还是新手 → `sylvester-balance-target.md`
- 技能门槛、天花板与区间宽窄 → `sylvester-skill-range.md`

## E — 执行 (Execution)

### 先选分支

| 你的问题像…… | 走 |
|---|---|
| 新手和高手常被分到一起，想缩小差距 | 分支 1 |
| 一人失误全队受罚；差距缩不了 | 分支 2 |

### 分支 1：技能差缓解（u07-12）

- **输入**：模式描述；哪里相互依赖、哪里成败靠技能；观察到的症状。缺了先问。
- **步骤**：
  1. 确认问题：玩家相互依赖、成败取决于技能，且技能差大（p.201）。完成标准：三条逐一写是否成立；不全成立就不是本卡的问题。
  2. 先缩小技能差，逐项写是否适用、怎么落地：
     - 简单、优雅的设计是基础手段：越容易上手，玩家越快越过技能门槛，越少惹恼高手、被踢出局（p.201）。
     - 匹配：系统记录每人的经验等级和胜率，把记录相近的人配到一起；作者说概念简单、做好极难，没讲做法（p.201）。
     - 结构：前几小时可以独自玩、之后再选择组队，或先单人模式再多人，新人不必在任何队里担角色（p.201–202）。
     - 自适应训练：在每个关键时刻告诉新手该做什么（p.202）。

     完成标准：四项各有一行结论。
  3. 缩不了就转分支 2（p.202）。
- **判停 / 转向**：手段之间没有选择判据，原文只给顺序，取舍由设计者判断。匹配算法怎么做不在本卡。
- **输出**（约定）：表「手段 / 是否适用 / 怎么落地 / 页码」，末行写是否转分支 2。

### 分支 2：相互依赖结构审查（u07-13）

- **输入**：模式里所有要多人配合的机制或规则。
- **步骤**：
  1. 找出一个人失败就让队友一起失败的设计点（p.202）。完成标准：共同失败点清单。
  2. 不把相互依赖当纯粹的好事：每个点写它带来什么共同胜利、强加了什么共同失败（p.202）。
  3. 改向可选、短期的合作，保留共同胜利，少强制共同失败（临时结盟，p.202）。完成标准：每个共同失败点给一个替代结构，或写明保留的理由。
- **判停 / 转向**：保留多少依赖原文没说，由设计者判断。作者把降依赖放在缩差之后（p.202）。以强制合作为核心的游戏（L4D 四人互助求生），降依赖等于改核心，要和核心体验权衡，原文没讨论。
- **输出**（约定）：表「共同失败点 / 共同胜利 / 共同失败 / 替代结构」。

## B — 边界 (Boundary)

**不要用这张卡**

- 有人故意坑人、为自己好玩捣乱 → `sylvester-divergent-goals-griefing.md`。
- 定平衡给哪个技能段 → `sylvester-balance-target.md`。

**作者警告的失败模式**

- 高手和新手被绑在一起：新手挨骂，高手无聊或恼火（p.201）。
- 把相互依赖当纯粹的好事，默认玩家会合作；真正合作、技能匹配的队伍在野外很少，假设它们存在的游戏会崩（p.202）。

**作者盲点与时代局限**

- 匹配只讲到 2012 年前后的概念，作者自认做好极难；之后的技能匹配算法、持久账号不在视野里（批判节）。
- 降依赖只有 Halo: Reach 一例，来自竞技射击。
- 可及性只讲技能和知识门槛，不涉及身体或感官障碍（批判节）。
- 作者自称全书是模型和假设（p.375）。
