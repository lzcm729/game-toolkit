<!-- capability_id: cap.designing-games.suspense-and-insight | revision: 1 | status: active | units: u01-06, u01-10 -->

# 悬念与顿悟

> **怎么用这张卡**：它是方法和书中依据的来源之一，不是回答的模板。回答围绕用户的处境：先给你自己的专业判断和具体做法，书外的实操（算一个例子、查数据、估成本）照常给；再用这张卡补方法、校正判断。不要按卡的分段复述这本书；卡里没写的，不等于不能答。书名和页码只在用户要出处时给。

## R — 原文 (Reading)

> Emotions don’t just appear in response to a change. They also appear in anticipation of change.
>
> 译：情绪不只在变化发生时出现，也在预感到变化时出现。
>
> — Tynan Sylvester, *Designing Games*, Ch1 Engines of Experience / Emotion and Change, p.14

> The human value of [victory/defeat] is already locked at victory, so there is no way for it to shift.
>
> 译：[胜/负] 这个价值已经锁死在「胜」，再没有变动的余地。
>
> — Tynan Sylvester, *Designing Games*, Ch1 Engines of Experience / Emotion and Change, p.14–15

> They were preceded by clues that the player senses and fails to interpret properly, but manages to interpret afterward. … The greatest insights are revealed after an extended buildup of information that all falls into place at once.
>
> 译：这些时刻之前都有线索：玩家察觉到了，当时没读对，事后才读懂。……最强的顿悟，出现在长时间积累的信息一下子全部落位的时候。
>
> — Tynan Sylvester, *Designing Games*, Ch1 Engines of Experience / Emotion Through Learning, p.21

## I — 方法骨架 (Interpretation)

这张卡管两种靠「还没发生」「还没读懂」制造的情绪。

悬念：情绪也来自对变化的预期。无意识一直在核算各种后果，把注意力分给潜在价值迁移最大的那些（p.14–15）。关键的 human value（人在乎、能在几个状态之间迁移的东西，如胜负，见 `sylvester-experience-analysis.md`）一旦锁定，局部事件再也改变不了它，本该紧张的时刻就塌了。

顿悟（insight）：一条新信息让许多旧信息突然讲通（p.20）。它不是单纯的惊讶，前提是事先有玩家察觉到、却读不懂的线索；事后能回读，并觉得下次也许能预判（p.21）。

两个分支互相独立，按症状分流：局面「早定了、没悬念」走分支 1，只识别不修；要设计一个恍然大悟的揭示走分支 2。作者观点（参考单元）：一课越精细、越不显然，学会时越愉快（p.20）。

## A1 — 书中案例 (Past Application)

- **分支 1｜差一杀拿 AC-130（例题，p.14–15）**：比分胶着时，一次击杀或阵亡就可能决定整局，悬念极强；本队已大比分领先时，这一杀、这一死都改变不了结果，悬念消失。示范性质。
- **分支 2｜「我早该知道！」（例题，p.20–21）**：即时战略里，几分钟前看到敌方建造单位的地方后来出现了敌方基地；象棋里对手一串看似无意义的走法原来是陷阱。**G-man（转述，p.21）**：Half-Life 里玩家一路反复瞥见提公文包的西装男，总在追上前消失，最终战后他才自我介绍、说明真相。**谜题（例题，p.21）**：玩家先弄清所有部件怎么动、彼此什么关系，可能卡 20 分钟以上，解法一到，所有部件的用途同时清楚。各例的结果原书未说明。

## A2 — 触发场景 (Future Trigger) ★

**情境**

1. 竞技或多人对局里一方早早领先，剩下的时间在走过场。
2. 连杀、奖励、终局这类本该是高光的时刻，试玩里没人在意。
3. 设计推理、解谜或剧情揭示，想做出「原来如此」。
4. 揭示做出来像无根的惊吓，玩家觉得被耍。

**语言信号**

- 比赛早早定局 ／ 后半局没悬念 ／ 领先了还得打完 ／ 怎么做恍然大悟 ／ 线索怎么埋 ／ 反转太突兀
- no suspense ／ the game is decided too early ／ foregone conclusion ／ aha moment ／ plant clues ／ twist feels cheap ／ insight

**与相邻卡的区分（初稿）**

- 落后方长时间必败、失败惩罚、怎么修已锁定的局面 → `sylvester-difficulty-and-failure.md`
- 信息该藏还是该给 → `sylvester-information-balance.md`
- 谜题玩家想不到解法（虚构含糊）→ `sylvester-fiction-and-metagame-info.md`
- 剧情揭示的排序与分支 → `sylvester-story-structure.md`
- 事件本身为何没情绪 → `sylvester-experience-analysis.md`

## E — 执行 (Execution)

### 先选分支

| 你的问题像…… | 走 |
|---|---|
| 本该紧张的局面没悬念、结果早定 | 分支 1 |
| 要设计一个揭示、谜题解法或反转 | 分支 2 |

### 分支 1：悬念失效点排查

- **输入**：局面描述（比分、剩余时间或资源、各方处境）；从哪一方的视角看。视角缺了先问：同一局面对领先方和追赶方不同。
- **步骤**：
  1. 写出此刻悬而未决的关键 human value，如 [victory/defeat]（p.14）。完成标准：每个视角一个价值。
  2. 问接下来的局部事件（下一杀、下一次阵亡）还能不能改变这个价值；不能就标为悬念失效点（p.14–15）。完成标准：每个失效点写明为什么改变不了。
  3. 对照「无意识把注意力分给潜在迁移最大的后果」（p.15），确认失效是因为账面已经一边倒。
- **判停 / 转向**：领先多少算锁定，原书未说明，只有「way ahead」的定性描述；确定性游戏能直接算出的照算，概率上「近乎锁定」的列出来交设计者判断。本卡不修：落后方被锁在必败局面里的修法在第 3 章 Failure Traps（p.79–80），「别惩罚玩家本人，另找办法制造悬念」在 p.78，都去 `sylvester-difficulty-and-failure.md`。
- **输出**（约定）：表，列为「局面 / 视角 / 关键价值 / 为何已锁定」。

### 分支 2：顿悟设计：线索链与拼合点

- **输入**：要揭示的真相或谜题解法；揭示前玩家会接触到的信息。
- **步骤**：
  1. 定最后揭示的那条信息：它一出现，之前的许多信息同时讲通（p.20）。完成标准：写出它串起哪几条旧信息。
  2. 埋下玩家会注意到、当时读不懂的线索（p.21）。完成标准：每条线索写出位置和单看时的无害解释。
  3. 让信息积累一段时间，再安排一个让它们一起落位的揭示点（p.21）。预定义故事能精确控制玩家每一步知道什么，适合长线铺垫（p.21）。
  4. 检查揭示后玩家能回头读懂每条线索，并觉得下次有机会预判（p.20–21）。
  5. 谜题型：让玩家在想通之前，先弄清各部件怎么运动、彼此什么关系（p.21）。
- **判停 / 转向**：线索多明显、几条、隔多久，原书未说明，交设计者，靠试玩校准。
- **输出**（约定）：线索链表，列为「线索 / 位置 / 单看的解释 / 揭示后的解释」，附四项结构检查：能被注意到吗？单看读不懂吗？揭示后能回读吗？揭示点同时串起多条吗？

## B — 边界 (Boundary)

**不要用这张卡**

- 想排一份「分段释放信息制造悬念」的计划。作者说信息揭示在情绪上等同于变化，难以持续制造价值变化的段落可以扣住信息、有结构地配给（p.15）；但这个单元复核未通过（依据不足）：揭示几次、隔多久、按什么顺序，第 1 章没有展开。不要拿分支 2 的线索链当释放结构，原文没有这样接。
- 想修复已锁定的局面 → `sylvester-difficulty-and-failure.md`。

**作者警告的失败模式**

- 价值已锁死，玩家还得打完：局末已定输赢，连杀之类的高光时刻没人在意（p.14–15）。
- 把顿悟做成单纯的惊吓：没有事先的线索，玩家无从「早该知道」（p.21）。

**作者盲点与时代局限**

- 悬念原文只有 Modern Warfare 一个例子；锁定是玩家无意识的感知，不一定等于数学上已定。
- 顿悟的例子偏预设剧情（G-man）和谜题，涌现型顿悟只有即时战略、象棋的描述。
- 作者自称全书是模型和假设（p.375）。

**各分支的已知缺口**

- 分支 1：锁定阈值和修法都不在本卡。
- 分支 2：「越精细越不显然、学会时越愉快」（p.20）和「线索要能被注意到」之间怎么取舍，没有判据。
