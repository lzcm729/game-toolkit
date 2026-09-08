# ice 作者工作台（真实只读样板）

本文件由同目录 render_workbench.py 从 ice.content.yaml **生成**，勿独立手改。YAML 是人工核对源码后编排的作者快照，未实现自动从引擎提取或回流。

业务字段逐项标分类；声明性表示可交机械校验，不代表本检查器已核过引擎值。解释性需语义校验，C 表示 C 层绑定。固定结构元数据（ID、版本、字段类型、来源定位、生效说明、引用及投影分区）按 schema 归声明性，只校格式和关联；其中自然语言的真伪仍须人工复核。

证据路径相对奶茶项目根；src.sample 相对插件根。有效值只指固定版本加载配置时的基础值，未运行 Godot，不涵盖运行时实验覆写、等级、天气或已有 buff 合并后的结果。

publication_ir 是**候选字段映射声明**，不是已生成的运行资源；结构通过不代表机制契约完备或允许发布。此样板未改变任何项目文件。

## 实例身份与定位

- ID（声明性）：ice
- 针对版本（声明性）：3f93fff80432653f12e28076c4493f62252d3836

**ice.name** — 声明性

冰块

- 生效方式：_META[ice].name_cn 的已登记名称。
- 来源 src.library：scripts/data/ingredient_library.gd:8-22 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.position** — 解释性 · Framework

单体硬控；冻结目标使其停驻。

- 生效方式：作者定位摘要；需核对 Framework 语义，不定义执行规则。
- 来源 src.recipe：data/recipes/ice.tres:12-18; scripts/data/recipe_data.gd:5-18 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.card：docs/design/ingredient-menu.html:260-279 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.scope** — 解释性 · C

本样板只读已采纳分支与其直接参数/关系；不是全游戏平衡表，不代表现有项目已接入作者工作台。

- 生效方式：样板阅读范围；未发布到游戏。
- 来源 src.sample：skills/split-doc-layers/examples/content-model/README.md (本次人工核对及样板编排) @ ice-sample/1; upstream=3f93fff80432653f12e28076c4493f62252d3836

## 已采纳定义

定义身份及参数与代码解读分开标记；现行代码不自动升级为已采纳机制契约。

**ice.freeze_seconds** — 声明性

1.5

- 生效方式：有效值 = .tres 覆盖：core.tres:118；config.gd:370 默认同值。单位秒；加载 Config 后由 ice_freeze_effect.gd:28 读取，尚会经过 tier2 缩放。
- 来源 src.core：data/config/core.tres:1-176 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.config：scripts/data/config.gd:227,278-290,369-373 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.effect：scripts/data/effects/ice_freeze_effect.gd:24-62 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.tier2_per_level** — 声明性

0.4

- 生效方式：有效值 = 脚本默认：config.gd:227；core.tres 无此键。无量纲；effect:31 调 mastery:78-79，以运行时等级缩放基础时长。
- 来源 src.config：scripts/data/config.gd:227,278-290,369-373 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.core：data/config/core.tres:1-176 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.effect：scripts/data/effects/ice_freeze_effect.gd:24-62 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.mastery：scripts/systems/mastery_system.gd:76-109 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.hud_effect** — 声明性

冰冻1.5秒

- 生效方式：data/recipes/ice.tres:15 的字面字符串；recipe_data.gd:16 将 effect 定义为 HUD 短标签；字符串中的时长不参与结算，也不随 Config 自动更新。
- 来源 src.recipe：data/recipes/ice.tres:12-18; scripts/data/recipe_data.gd:5-18 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.display_coupling** — 解释性 · Interface

展示字段与数值耦合：HUD 标签手抄基础冻结秒数；即便此快照相等，调参、tier2 深化或 B 分摊后也不能据此推出实际持续时长。未在本任务验证当前 HUD 是否消费它。

- 生效方式：待 Interface 审核展示策略；不在样板改文案或补插值机制。
- 来源 src.recipe：data/recipes/ice.tres:12-18; scripts/data/recipe_data.gd:5-18 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.effect：scripts/data/effects/ice_freeze_effect.gd:24-62 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.recipes** — 声明性

catalog.recipes.with-ice

- 生效方式：关系引用到外部配方集合；成员由项目查询解析，不复制十二条清单。
- 来源 src.recipes：data/recipes/*ice*.tres (read-only glob + each toppings field) @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.branches** — 声明性

ice.A、ice.B

- 生效方式：已采纳的分支身份；某盘是否选择它属于运行时状态。
- 来源 src.card：docs/design/ingredient-menu.html:260-279 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.decision：git:437e02f commit message + docs/design/ingredient-menu.html diff @ 437e02f2423d5cad4c528146c4fd22e0d018eae4

**ice.tier2_current_vs_card** — 解释性 · Framework

卡片称 tier2 纯时长深化，但当前代码在冻结自然衰减结束且 tier2 已购时仍生成冰区。这里只报告当前实现，不把残留实现反推为新采纳规则。

- 生效方式：语义分歧，交 Framework 核实 de-smear 意图与残留路径。
- 来源 src.card：docs/design/ingredient-menu.html:260-279 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.zone：scripts/systems/combat_customer_helper.gd:306-317; scripts/systems/combat_system.gd:869-876 @ 3f93fff80432653f12e28076c4493f62252d3836

### 分支 ice.A

**ice.A.name** — 声明性

脆冻

- 生效方式：卡片:272 与已采纳决策的分支名。
- 来源 src.card：docs/design/ingredient-menu.html:260-279 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.decision：git:437e02f commit message + docs/design/ingredient-menu.html diff @ 437e02f2423d5cad4c528146c4fd22e0d018eae4

**ice.A.mechanism** — 声明性

mechanism.ice-brittle

- 生效方式：引用本样板机制索引 ID；status=gap，未伪造完整契约。
- 来源 src.decision：git:437e02f commit message + docs/design/ingredient-menu.html diff @ 437e02f2423d5cad4c528146c4fd22e0d018eae4
- 来源 src.gdd：docs/GDD/mastery-and-inspiration.md:37,96,126 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.A.damage_mult** — 声明性

1.5

- 生效方式：有效值 = 脚本默认：config.gd:288；core.tres 无此键。无量纲；brittle:837 乘调用方传入的 a.damage，不是主命中 dmg 修改链后的值。
- 来源 src.config：scripts/data/config.gd:227,278-290,369-373 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.core：data/config/core.tres:1-176 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.hit：scripts/systems/combat_ammo_helper.gd:435-458 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.brittle：scripts/systems/combat_system.gd:832-841 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.A.current_implementation** — 解释性 · Framework

当前实现：先主命中伤害，再 snapshot was_frozen_pre，再派发 effects。碎裂独立判断 c.alive、配方 toppings 含 ice、was_frozen_pre、mastery 非空且 is_tier3_a(ice)。effects 非空不是碎裂的直接门槛；额外伤后目标仍活着才 clear freeze。

- 生效方式：这是固定 HEAD 的代码解读，需 Framework 语义复核；不扩大为任何攻击均触发。
- 来源 src.hit：scripts/systems/combat_ammo_helper.gd:435-458 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.brittle：scripts/systems/combat_system.gd:832-841 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.A.binding** — 解释性 · C

resolve_hits → _apply_ice_brittle(c, a.damage, a.recipe)；机制引用记录契约缺口，源码位置仅为 C 层绑定。

- 生效方式：只读实现定位；不作为可执行作者 DSL。
- 来源 src.hit：scripts/systems/combat_ammo_helper.gd:435-458 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.brittle：scripts/systems/combat_system.gd:832-841 @ 3f93fff80432653f12e28076c4493f62252d3836

### 分支 ice.B

**ice.B.name** — 声明性

寒潮

- 生效方式：卡片:277 与已采纳决策的分支名；不是同名天气的身份。
- 来源 src.card：docs/design/ingredient-menu.html:260-279 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.decision：git:437e02f commit message + docs/design/ingredient-menu.html diff @ 437e02f2423d5cad4c528146c4fd22e0d018eae4

**ice.B.mechanism** — 声明性

mechanism.ice-hanchao

- 生效方式：引用本样板机制索引 ID；status=gap。
- 来源 src.decision：git:437e02f commit message + docs/design/ingredient-menu.html diff @ 437e02f2423d5cad4c528146c4fd22e0d018eae4
- 来源 src.gdd：docs/GDD/mastery-and-inspiration.md:37,96,126 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.B.radius** — 声明性

80

- 生效方式：有效值 = 脚本默认：config.gd:289；core.tres 无 hanchao_radius。单位为当前项目位置坐标长度；effect:47,52-53 用距离平方筛选。不要错用 core.tres:72 同值的旧 shatter_radius。
- 来源 src.config：scripts/data/config.gd:227,278-290,369-373 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.core：data/config/core.tres:1-176 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.effect：scripts/data/effects/ice_freeze_effect.gd:24-62 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.B.max_targets** — 声明性

4

- 生效方式：有效值 = 脚本默认：config.gd:290；core.tres 无 hanchao_max_targets。单位个，含命中目标；effect:56-60 按实际接收者数平分。脚本注释建议降到 3 尚待裁决，未采用。
- 来源 src.config：scripts/data/config.gd:227,278-290,369-373 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.core：data/config/core.tres:1-176 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.effect：scripts/data/effects/ice_freeze_effect.gd:24-62 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.B.current_implementation** — 解释性 · Framework

当前实现：运行时选 B 且 customers 非空时，在命中目标与半径内最近的存活邻居之间平分本次冻结预算；先做 tier2 缩放，人数上限包含原目标。分摊事件后还经过通用 buff 合并与天气冰冻条，事件预算守恒不等于最终 buff 剩余总时长严格守恒。

- 生效方式：源码解读，归 Framework 复核；未将代码整理成新契约。
- 来源 src.effect：scripts/data/effects/ice_freeze_effect.gd:24-62 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.mastery：scripts/systems/mastery_system.gd:76-109 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.buff：scripts/systems/combat_system.gd:423-439 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.B.binding** — 解释性 · C

IceFreezeEffect.on_hit → _emit_hanchao_split → buff_apply_requested；当前实现按距离排序取邻居。

- 生效方式：仅 C 层来源绑定，不是新增通用操作符。
- 来源 src.effect：scripts/data/effects/ice_freeze_effect.gd:24-62 @ 3f93fff80432653f12e28076c4493f62252d3836

### 机制引用登记（不补规则）

**mechanism.ice-brittle** — 状态 gap（声明性登记）

**mechanism.ice-brittle.home** — 解释性 · Framework

归属缺口：docs/GDD 尚无足够实施的现行 A 契约。mastery-and-inspiration.md:37 已有脆冻勘误（不是完全没出现），正文:96,126 仍用旧 B 冰晶爆例子。现行详细设计文字主要落在卡片:273 与 commit 437e02f，不能以代码替代机制契约。

- 生效方式：本地索引 ID 只给缺口一个可引用身份，不声称项目已有此 ID 的正式契约。
- 来源 src.gdd：docs/GDD/mastery-and-inspiration.md:37,96,126 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.card：docs/design/ingredient-menu.html:260-279 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.decision：git:437e02f commit message + docs/design/ingredient-menu.html diff @ 437e02f2423d5cad4c528146c4fd22e0d018eae4

**mechanism.ice-hanchao** — 状态 gap（声明性登记）

**mechanism.ice-hanchao.home** — 解释性 · Framework

归属缺口：docs/GDD 的现行 B 只有勘误式说明，未找到完整触发、接收者、并发/合并、事件顺序契约。现行详细设计文字主要在卡片:278 与 commit 437e02f；GDD:96,126 仍残留冰晶爆。天气文档中的同名寒潮不能充当此分支的家。

- 生效方式：标归属缺口交 Framework，不在内容样板补造规则。
- 来源 src.gdd：docs/GDD/mastery-and-inspiration.md:37,96,126 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.card：docs/design/ingredient-menu.html:260-279 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.decision：git:437e02f commit message + docs/design/ingredient-menu.html diff @ 437e02f2423d5cad4c528146c4fd22e0d018eae4
- 来源 src.effect：scripts/data/effects/ice_freeze_effect.gd:24-62 @ 3f93fff80432653f12e28076c4493f62252d3836

### 关系集合（不手抄成员清单）

集合 ID（声明性）：catalog.recipes.with-ice

**catalog.recipes.selector** — 声明性

data/recipes/*ice*.tres

- 生效方式：在固定上游版本只读 glob；逐份核对 toppings 包含 ice。当前查询返回集合，未手抄成员表。
- 来源 src.recipes：data/recipes/*ice*.tres (read-only glob + each toppings field) @ 3f93fff80432653f12e28076c4493f62252d3836

**catalog.recipes.count** — 声明性

12

- 生效方式：该版本 glob 命中数且逐份 toppings 含 ice；快照观测值，不作为未来数量硬约束。检查器只解析集合 ID，不执行 glob 或核对数量。
- 来源 src.recipes：data/recipes/*ice*.tres (read-only glob + each toppings field) @ 3f93fff80432653f12e28076c4493f62252d3836

## 发布情况

**ice.library_present** — 声明性

True

- 生效方式：_ALL_IDS 与 _META 已收录；静态入库事实。
- 来源 src.library：scripts/data/ingredient_library.gd:8-22 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.library_index** — 声明性

4

- 生效方式：_ALL_IDS:10 中从零计的位置（第五项）；加载库的顺序约束，不能在原位置前插入/重排。
- 来源 src.library：scripts/data/ingredient_library.gd:8-22 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.rng_constraint** — 解释性 · Framework

_ALL_IDS 前段位置锁定，新增 ID 追加末尾；源注释将索引绑定到 trace RNG 映射。这是集合发布约束，不能按名称排序发布。

- 生效方式：发布/导出时保序；具体确定性要求由 Framework 复核。
- 来源 src.library：scripts/data/ingredient_library.gd:8-22 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.default_active** — 声明性

True

- 生效方式：DEFAULT_ACTIVE:13 包含 ice；仅默认出战集合，不保证任一当前盘实际出战。
- 来源 src.library：scripts/data/ingredient_library.gd:8-22 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.runtime_boundary** — 解释性 · Framework

purchased_tier3 与 tier3_path 由 MasterySystem 持有；is_tier3_a/b 查询购买状态和路径。A/B 定义是内容，玩家已买/已选何支是状态，作者模型与发布 IR 不存某个玩家的选择。当前出战列表应查询 RunLoadout。

- 生效方式：运行时按 Framework 查询；不把两个分支的已实现状态当成同时启用。
- 来源 src.mastery：scripts/systems/mastery_system.gd:76-109 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.library：scripts/data/ingredient_library.gd:8-22 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.delivery_observation** — 解释性 · C

当前源码含 A/B 实现；卡片:265 仍写“设计·待实装”。仅确认仓库实现存在，未运行引擎、未确认发行包、没有在本次发布游戏。

- 生效方式：源码快照与卡片状态分开；运行/发行验证未知。
- 来源 src.card：docs/design/ingredient-menu.html:260-279 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.effect：scripts/data/effects/ice_freeze_effect.gd:24-62 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.brittle：scripts/systems/combat_system.gd:832-841 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.deprecated_boundary** — 解释性 · C

以下七项为序列化兼容残留，资源加载值仍存在，但现行 A/B 不消费。不能作为现行平衡参数，也不能据值相等映射到新字段。

- 生效方式：core.tres:69-75 对应 config.gd:281-287 DEPRECATED；只记录残留，不删除工程字段。
- 来源 src.core：data/config/core.tres:1-176 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.config：scripts/data/config.gd:227,278-290,369-373 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.hit：scripts/systems/combat_ammo_helper.gd:435-458 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.effect：scripts/data/effects/ice_freeze_effect.gd:24-62 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.brittle：scripts/systems/combat_system.gd:832-841 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.legacy.tier3_ice_a_freeze_duration_mult** — 声明性

2.3

- 生效方式：资源值 = .tres 覆盖（core.tres:69；config.gd:281 默认同值且 DEPRECATED）。现行 A/B 无生效消费；兼容残留，排除发布 IR。
- 来源 src.core：data/config/core.tres:1-176 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.config：scripts/data/config.gd:227,278-290,369-373 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.legacy.tier3_ice_a_shatter_gold_mult** — 声明性

2

- 生效方式：资源值 = .tres 覆盖（core.tres:70；config.gd:282 默认同值且 DEPRECATED）。现行 A/B 无生效消费；兼容残留，排除发布 IR。
- 来源 src.core：data/config/core.tres:1-176 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.config：scripts/data/config.gd:227,278-290,369-373 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.legacy.tier3_ice_b_shatter_count** — 声明性

4

- 生效方式：资源值 = .tres 覆盖（core.tres:71；config.gd:283 默认同值且 DEPRECATED）。现行 A/B 无生效消费；兼容残留，排除发布 IR。
- 来源 src.core：data/config/core.tres:1-176 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.config：scripts/data/config.gd:227,278-290,369-373 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.legacy.tier3_ice_b_shatter_radius** — 声明性

80

- 生效方式：资源值 = .tres 覆盖（core.tres:72；config.gd:284 默认同值且 DEPRECATED）。现行 A/B 无生效消费；兼容残留，排除发布 IR。
- 来源 src.core：data/config/core.tres:1-176 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.config：scripts/data/config.gd:227,278-290,369-373 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.legacy.tier3_ice_b_shatter_damage_mult** — 声明性

0.4

- 生效方式：资源值 = .tres 覆盖（core.tres:73；config.gd:285 默认同值且 DEPRECATED）。现行 A/B 无生效消费；兼容残留，排除发布 IR。
- 来源 src.core：data/config/core.tres:1-176 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.config：scripts/data/config.gd:227,278-290,369-373 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.legacy.tier3_ice_b_shatter_slow_duration** — 声明性

0.8

- 生效方式：资源值 = .tres 覆盖（core.tres:74；config.gd:286 默认同值且 DEPRECATED）。现行 A/B 无生效消费；兼容残留，排除发布 IR。
- 来源 src.core：data/config/core.tres:1-176 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.config：scripts/data/config.gd:227,278-290,369-373 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.legacy.tier3_ice_b_shatter_slow_factor** — 声明性

0.5

- 生效方式：资源值 = .tres 覆盖（core.tres:75；config.gd:287 默认同值且 DEPRECATED）。现行 A/B 无生效消费；兼容残留，排除发布 IR。
- 来源 src.core：data/config/core.tres:1-176 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.config：scripts/data/config.gd:227,278-290,369-373 @ 3f93fff80432653f12e28076c4493f62252d3836

### 作者字段与候选发布字段的边界

同一个实例身份；下列目标仅为字段集合草案，不是已接入的导出器。解释、讨论及兼容残留均被本映射排除。

声明性映射 projection.ice.preview → 实例 ice

| 目标字段 ID | 作者字段来源 |
|---|---|
| ir.ice.name | ice.name |
| ir.ice.freeze_seconds | ice.freeze_seconds |
| ir.ice.tier2_per_level | ice.tier2_per_level |
| ir.ice.hud_effect | ice.hud_effect |
| ir.ice.recipes | ice.recipes |
| ir.ice.branches | ice.branches |
| ir.ice.A.name | ice.A.name |
| ir.ice.A.mechanism | ice.A.mechanism |
| ir.ice.A.damage_mult | ice.A.damage_mult |
| ir.ice.B.name | ice.B.name |
| ir.ice.B.mechanism | ice.B.mechanism |
| ir.ice.B.radius | ice.B.radius |
| ir.ice.B.max_targets | ice.B.max_targets |
| ir.ice.library_present | ice.library_present |
| ir.ice.library_index | ice.library_index |
| ir.ice.default_active | ice.default_active |

声明性排除集（其余作者字段必须逐项列入，检查器验证分区）：

- ice.position
- ice.scope
- ice.display_coupling
- ice.tier2_current_vs_card
- ice.A.current_implementation
- ice.A.binding
- ice.B.current_implementation
- ice.B.binding
- ice.rng_constraint
- ice.runtime_boundary
- ice.delivery_observation
- ice.deprecated_boundary
- ice.legacy.tier3_ice_a_freeze_duration_mult
- ice.legacy.tier3_ice_a_shatter_gold_mult
- ice.legacy.tier3_ice_b_shatter_count
- ice.legacy.tier3_ice_b_shatter_radius
- ice.legacy.tier3_ice_b_shatter_damage_mult
- ice.legacy.tier3_ice_b_shatter_slow_duration
- ice.legacy.tier3_ice_b_shatter_slow_factor
- ice.discussion.A.title
- ice.discussion.A.proposed_description
- ice.discussion.A.question
- ice.discussion.general.title
- ice.discussion.general.question

## 设计讨论

以下内容未进入正式定义或发布输入；空白“我的意见”不冒充用户观点。

### discussion.ice.A.wording

- 绑定对象（声明性）：ice.A
- 针对版本（声明性）：3f93fff80432653f12e28076c4493f62252d3836

**ice.discussion.A.title** — 声明性

📝 我的意见

- 生效方式：卡片:274 原栏为空，本样板未代填用户观点。
- 来源 src.card：docs/design/ingredient-menu.html:260-279 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.discussion.A.proposed_description** — 解释性 · Framework

拟议描述/待对齐：冻结中的敌人受到攻击 → 碎裂、立刻解冻，对被冰封的敌人造成一次额外伤害。

- 生效方式：引用卡片:273；该宽泛描述已有历史采纳背景，但不视为当前代码完全实现或本次批准扩展触发范围。
- 来源 src.card：docs/design/ingredient-menu.html:260-279 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.discussion.A.question** — 解释性 · Framework

样板讨论问题（由 Codex 编写，非用户意见）：应收窄卡片为含冰主命中触发，还是修改实现让其他攻击也能打碎？需 Framework 裁决；两边暂不改。

- 生效方式：仅讨论，针对本快照；接受后另更新所属契约与正式定义，禁止直接发布本条。
- 来源 src.sample：skills/split-doc-layers/examples/content-model/README.md (本次人工核对及样板编排) @ ice-sample/1; upstream=3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.hit：scripts/systems/combat_ammo_helper.gd:435-458 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.card：docs/design/ingredient-menu.html:260-279 @ 3f93fff80432653f12e28076c4493f62252d3836

### discussion.ice.general

- 绑定对象（声明性）：ice
- 针对版本（声明性）：3f93fff80432653f12e28076c4493f62252d3836

**ice.discussion.general.title** — 声明性

📝 我的意见

- 生效方式：借用卡片讨论入口；未写入正式数据。
- 来源 src.card：docs/design/ingredient-menu.html:260-279 @ 3f93fff80432653f12e28076c4493f62252d3836

**ice.discussion.general.question** — 解释性 · Framework

样板讨论问题（非用户意见）：完整 A/B 契约放回哪一处既有 Framework 文档？如何消除 HUD 字符串与时长的耦合？先确认所有者与针对版本。

- 生效方式：待讨论/未采纳；Framework 决定契约归属，展示问题另交 Interface。
- 来源 src.sample：skills/split-doc-layers/examples/content-model/README.md (本次人工核对及样板编排) @ ice-sample/1; upstream=3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.gdd：docs/GDD/mastery-and-inspiration.md:37,96,126 @ 3f93fff80432653f12e28076c4493f62252d3836
- 来源 src.recipe：data/recipes/ice.tres:12-18; scripts/data/recipe_data.gd:5-18 @ 3f93fff80432653f12e28076c4493f62252d3836
