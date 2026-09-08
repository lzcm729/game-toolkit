# 作者模型结构约定（author-model/1）

作者模型是围绕稳定实例身份的工作台：同时容纳已采纳内容、来源、发布观察与设计讨论。
它不是发布中间表示，也不因为写成 YAML 就成为项目的新真值源。本约定不预制领域字段、
技能/Buff 类型表、操作符或引擎路径；领域字段由项目根据既有契约提供。

## 四部分与字段分类

| 部分 | 内容 | 边界 |
|---|---|---|
| 实例 identity | 稳定 ID、名称、定位、读者与范围 | 同名不等于同身份；摘要不承担执行规则 |
| 已采纳定义 adopted | 参数及来源/单位/生效方式、关系、分支、条件、机制 ID 引用 | 只能填既有契约允许的实例条件；新增条件语义先归 Framework |
| 发布情况 release | 入库、可用集合、顺序约束、已实现/已构建/已发布的证据 | 这些阶段分开陈述；玩家已购买/已选择、当前会话状态不属于内容定义 |
| 讨论 discussion | 意见、问题、拟议描述、决定记录 | 绑定实例或其分支及针对版本；接受之前不进入正式数据 |

所有业务字段都使用同一种包装，不直接在实例/分支/讨论对象上增加任意键：

~~~yaml
id: item.parameter
classification: declarative
kind: value
value: 2.5
sources: [source.accepted]
effective: 单位秒；从接受版本读取基础参数，下一次加载内容快照生效。
~~~

以上数值只是格式示意，来源 ID 要在实际模型登记后才可通过检查。

- **declarative（声明性）**：具体值、成员关系、既有条件符号、来源定位等能定义机械检验规则。
  本检查器只检查其中的结构，不承诺范围、引擎相符性或执行正确性。
- **interpretive（解释性）**：定位解读、当前实现的行为解释、拟议描述、设计讨论等需语义校验。
  必填 owner，取 Framework / Interface / C（C 层绑定）。一个字段涉及多种责任时拆字段或留明确交接，
  不用混合 owner 字符串蒙混过关。这是语义审查归属，不是作者姓名或存储所有者。
- 每个字段的 sources 都引用来源登记；本格式对解释性也要求来源，可指原创讨论记录。
  每个字段的 effective 说明生效入口、阶段，或“未采纳/不生效”。数值需在此说明单位、选择哪个来源、
  覆盖/默认/派生及后续修饰；长的语义推导拆成解释性字段，勿只给没有来源的数字。
  元数据 ID、版本、kind、来源登记、引用与投影分区本身由 schema 固定为声明性，不递归包装。
  effective 的文字是可定位的声明，并不因此免除语义复核。
- value 仅允许非空值类型的标量（字符串/有限数/布尔）或扁平标量数组；不允许塞入未分类的嵌套业务字典。
  结构化参数组应拆为多个字段。未知、查不了、不适用用有来源的明确文字表达，不用 null 假装有效值。
- kind 为 value / relation / mechanism_refs / branch_refs。
  后三者的 value 是非空 ID 数组，分别引用实例或外部集合、机制索引、分支。
  条件只有在项目已有契约允许时，才把符号/参数作为声明性 value，并用机制 ID 引用其语义；
  检查器不解析条件表达式，也不提供新的规则 DSL。

## YAML 骨架及 ID 解析

根只含 schema_version、sources、catalogs、mechanisms、instances、publication_ir 六项；
schema_version 必须为字符串 author-model/1。数组允许为空，但至少一个实例。

| 对象 | 固定键 |
|---|---|
| 来源 | id、locator（相对项目位置或外部资源标识）、version（不可变修订/快照，不用无锚的“最新”） |
| 外部关系集合 | id、fields（用字段包装声明查询选择器/版本观测等；不复制成员清单） |
| 机制索引 | id、status（indexed / gap）、fields（解释性归属、来源指针） |
| 实例 | id、version、identity（字段数组）、adopted、release（字段数组）、discussion |
| adopted | fields（字段数组）、branches（分支数组） |
| 分支 | id、fields |
| 讨论 | id、target、target_version、fields |
| 候选发布映射 | id、instance_id、fields（目标映射数组）、excluded（作者字段 ID 数组） |
| 目标映射 | id、from（非空作者字段 ID 数组） |

文档内所有定义 ID 全局唯一，建议命名空间区分实例、分支、字段、集合、机制与输出字段。
实例在发布侧通过 instance_id 保持相同身份；这是引用，不是重复定义 ID。
当前格式的机制/外部集合登记都是本文件的解析端点，不自动打开别的文件或拉取远程目录。
集合 ID 可解析只证明“有集合登记”，不证明实际成员存在；要发布必须由项目适配解析该集合。
机制 status=gap 表示找到缺口，仍可被分支引用；indexed 仅表示已有定位，也不证明契约完整。
本地分配的机制 ID 需标明是样板索引，不能假称项目已有契约编号。

讨论 target 必须是所在实例或其分支；target_version 必须非空。允许针对历史版本讨论，
不强迫它等于当前实例版本。版本是否存在、讨论是否过时需后续语义/来源核验。
接受讨论要另产决定并更新相应正式定义/所属契约，保留原讨论的版本锚，不直接把整条讨论喂给引擎。

## 作者模型 ≠ 发布中间表示

**同身份，不同字段集合。** 作者模型还包含解释、来源记录、讨论、发布观察；运行数据应只取
发布所需且经接受的声明字段。字段名/形状可以在项目适配中变化，不要求两个对象相同，
也不把一次 YAML/JSON 序列化称为往返能力。

publication_ir 在这里是候选输出的**字段映射声明**，不是 IR 实例值，更不是现成导出器。
每个输出字段通过 from 追溯到同一实例的作者字段，允许重命名、多字段合成及一字段拆出多个目标。
任何生成字段也必须登记作者侧的输入来源；不允许无来源的输出常量或暗加引擎绑定。
如有绑定字段，先在作者侧声明并指出其所有者/来源，再进入映射。

令 A 为某实例四部分内全部字段（含分支、讨论），I 为该映射所有 from 的并集，E 为 excluded：

- I 和 E 不相交，且 I ∪ E = A；未输出字段必须显式排除，不能静默丢失。
- I 只能包含 identity / adopted（含分支）/ release 内的声明性字段。
  解释性字段和任何 discussion 字段一律不能作为发布输入，即便讨论标题是声明性字符串。
- from 必须属于同一 instance_id；外部集合/机制通过实例里的引用字段进入投影，
  不能直接取另一个实例、登记表或讨论的字段。每个实例至少声明一个候选投影，可以全排除。
- excluded 可以排除声明性字段（例如兼容残留或不需要发布的观察）。本脚本不理解“过时”含义，
  正确选择排除项、机制缺口是否阻塞生成，属于发布语义门槛。

检查器没有读取实际 IR 文件，没有验证转换函数或字段值，没有验证单位、数据范围、跨字段约束、
引擎数据一致性、热加载、构建产物、往返保真或合并能力。status=ok 只表示此映射声明在结构上合法。

## 来源与发布声明：按集合/字段组分配权属

不要使用单值 content_truth；同一实例的平衡字段、资源绑定、展示文案可以由不同来源拥有。
下面是项目侧需要记录的声明格式，**不是本检查器的输入 schema**，本次也没有给现有项目配置增加键。
字段组需要显式且可展开的选择器；每个可发布字段恰好归一个组。组间重叠/无人拥有必须先解决；
读取优先级只在同组内声明，不能用“最后写入优先”绕过所有权。

~~~yaml
collection: project.collection-id
field_groups:
  - id: group.parameters
    fields: [project-defined.field-id]   # 或项目定义的可展开选择器
    owner: content-maintainer
    reads:
      - source: accepted-content
        locator: relative-path-or-resource-id
        version: immutable-revision
    resolution: 从该接受快照读取；多来源时逐字段写清优先级及缺值策略
    proposal_entries: [author-workbench, editor]
    acceptance: 所有者审核字段提案、通过约束复验，形成新的不可变接受版本
    generates: [runtime-projection, human-view]
    effective: 接受且生成验证成功后，下一次内容快照加载；不推定支持热更新
~~~

奶茶示例（Git 内所有权；基础有效值已核对，提案/接受/生成流程是建议声明，尚未接入）：

~~~yaml
collection: milk-tea.ingredients
field_groups:
  - id: balance
    fields: 本集合的现役平衡参数（项目映射展开，兼容残留单独排除）
    owner: 奶茶项目 Git 内的内容维护者
    reads:
      - source: serialized-overrides
        locator: data/config/core.tres
        version: 3f93fff80432653f12e28076c4493f62252d3836
      - source: script-defaults
        locator: scripts/data/config.gd
        version: 3f93fff80432653f12e28076c4493f62252d3836
    resolution: 同名已序列化键覆盖脚本默认；缺键回退脚本默认；旧字段不按名字或数值猜成新字段
    proposal_entries: [git-patch, author-workbench, godot-editor-field-proposal]
    acceptance: 内容维护者接受差异并固定新 Git 版本，逐字段记录来源选择，通过领域约束复验
    generates: [effective-value-snapshot, candidate-runtime-projection, author-workbench]
    effective: 游戏入口加载该 Config 资源时得到基础值；运行时等级/选择/实验覆写是另一个阶段
~~~

这个例子的本次证据：冻结基础值来自资源覆盖；现行分支参数来自脚本默认；资源中的旧分支参数
虽然存在却不驱动现行机制。数值恰好相等不意味着来源可互换。详见真实样板；
当前项目仍直接使用既有资源/脚本，本交付没有把 YAML 变成生产发布输入。

Catfishing 示例（用户给定“飞书拥有平衡字段、UE 拥有绑定字段”的情景；未读取或验证项目/飞书，
下面修订号与选择器是占位声明，实际启用前必须绑定真实不可变快照，不声称已配置）：

~~~yaml
collection: catfishing.content
field_groups:
  - id: balance
    fields: 项目声明的平衡字段 ID 集合
    owner: 飞书平衡表的内容维护者
    reads:
      - source: feishu-balance
        locator: 待绑定的表与字段标识
        version: 待绑定的接受快照修订
    resolution: 仅从接受的飞书字段快照读取；UE 中这些字段是生成投影
    proposal_entries: [feishu, author-workbench, ue-editor-field-proposal]
    acceptance: 飞书所有者接受字段提案并生成新快照；UE 导出不可自行覆盖该真值
    generates: [runtime-balance-projection, author-workbench]
    effective: 与对应绑定快照一起构建验证后，在下次内容包加载生效
  - id: bindings
    fields: 项目声明的引擎资源与对象绑定字段 ID 集合
    owner: UE 工程中的技术维护者
    reads:
      - source: ue-bindings
        locator: 待绑定的项目资产或导出记录标识
        version: 待绑定的工程修订及资产快照
    resolution: 从接受的 UE 绑定快照读取；飞书相同栏位只可作为引用或提案
    proposal_entries: [ue-editor, git-patch, author-workbench]
    acceptance: 技术维护者接受绑定提案、核对资源可解析性，固定对应工程版本
    generates: [runtime-binding-projection, author-workbench]
    effective: 与接受的平衡快照按同一实例 ID 组合构建；构建成功不等于已部署
~~~

编辑器回流至少需要以下链条，不能把整张编辑器导出表直接当发布输入：

1. 保存**基线**：导出时的实例 ID、各字段组来源版本、字段值及单位/映射版本。
2. 生成**字段级提案**：相对基线的增加/修改/删除，注明目标字段与所有者。缺失字段不得自动解释为删除；
   编辑器新增/绑定变化也要显式提案。
3. 对“基线 / 当前已接受源 / 编辑器提案”做**三方合并**：源未变可应用，双方相同变更可合并，
   双方不同修改或删除与修改竞争标冲突；不能后写覆盖先写。跨所有者的提案分送各自接受。
4. 对合并后的组合快照重新做**跨字段约束复验**：关系、条件与分支互斥、单位、范围、资源绑定、
   所需确定性顺序等；验证规则来自已有契约。固定接受版本向量，再生成目标并按声明时点生效。

没有可靠基线、可逆字段映射、三方合并或复验能力时，**禁止编辑器改动直接成为发布输入**；
可以保留只读编辑器投影或人工字段提案，回到拥有方接受。这个限制是流程约定，本次检查器不实现合并、
冲突裁决、接受流程、所有者鉴权或任何引擎往返。

## 最小示例与运行

[minimal.content.yaml](minimal.content.yaml) 是完整可校验的最小例子：
一个实例、一个声明字段、一条绑定版本的讨论，发布目标改名并显式排除讨论。
真实样板位于同目录 [ice/ice.content.yaml](ice/ice.content.yaml)，
人读投影在同目录 ice.workbench.md；那里允许项目字段，本通用 schema 不认识这些字段名。

~~~console
python skills/split-doc-layers/scripts/check_content_model.py skills/split-doc-layers/examples/content-model/minimal.content.yaml
python skills/split-doc-layers/scripts/check_content_model.py skills/split-doc-layers/examples/content-model/ice/ice.content.yaml
python -m pytest skills/split-doc-layers/tests -q
~~~

检查器输出 JSON，scope 固定为 structure-only；退出码 0=结构通过、1=结构错误、2=无法读取/解析。
拒绝重复 YAML 键、循环别名、非有限数、未加引号的日期等非 JSON 类型，避免静默丢数据或类型漂移。
不打开 locator、不访问工程或网络；无新依赖，只用已有 PyYAML。
