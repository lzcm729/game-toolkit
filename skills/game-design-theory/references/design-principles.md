# Design Principles

Core principles for maintaining focus, teaching players, and designing effective input/output systems.

## Focus

> "Developing a game for two years with a team of twenty people can sometimes more resemble a war than the creation of art."

During development conflicts, games become unfocused. Maintaining a clear vision throughout is essential to creating something coherent and compelling.

### Establishing Focus

Before development begins, define:
1. **Core experience**: What feeling/experience defines this game?
2. **Primary mechanics**: What does the player DO most of the time?
3. **Target audience**: Who is this for?

Everything should serve the focus. Features that don't—however cool—dilute the game.

### The Function of Focus

Focus acts as a filter:
- "Does this feature serve our core experience?" → Yes: Consider. No: Cut.
- "Does this mechanic support our primary gameplay?" → Yes: Develop. No: Simplify.

**Example decisions**:
- Action game focused on combat → Limit inventory management
- Puzzle game focused on logic → Reduce time pressure
- Exploration game focused on discovery → Add secrets, reduce combat

### Maintaining Focus Through Conflict

Team members will have different visions:
- Programmer wants technical showcase
- Artist wants visual fidelity
- Designer wants systemic depth
- Producer wants safe market bet

**Focus resolves conflicts**: When disagreements arise, return to established focus. Which approach better serves the core experience?

### Changing Focus

Sometimes mid-development discoveries require focus adjustment:
- Playtest reveals unexpected fun in secondary system
- Technical limitations prevent core vision
- Market conditions shift

**Rules for changing focus**:
1. Change deliberately, not by drift
2. Communicate change to entire team
3. Re-evaluate all existing work against new focus
4. Accept some rework as necessary

### Sub-Focuses

Large games may have distinct sections with different focuses:
- Combat levels vs. puzzle levels
- Hub world vs. dungeons
- Story sequences vs. gameplay sequences

Each sub-section can have its own sub-focus that serves the game's overall focus.

---

## Teaching the Player

The first few minutes determine whether players continue or quit.

> "When a player tells a friend about your game, she will often remember those first few minutes and say, 'Well, it was a little weird to get used to' or, preferably, 'It was great. I jumped right into the game and found all this cool stuff.'"

### The Manual Is Dead

In the past, games relied on manuals to teach players. This worked when:
- Games were simpler
- Players were more dedicated
- There was no alternative

**Today's reality**:
- Manuals unread (or PDFs unopened)
- Players expect to learn by playing
- Friction in first minutes = uninstall

### Teaching Through Gameplay

Introduce complexity incrementally:

1. **Movement first**: Let player master basic navigation
2. **Then jumping/climbing**: Vertical gameplay after horizontal
3. **Then simple combat**: Enemies that test basics
4. **Then advanced mechanics**: Combinations, special moves

Each layer builds on mastery of previous layer.

### Safe Learning Environments

**Prince of Persia approach**:
- First breakaway floor: Non-lethal fall
- First spikes: Easy to notice and avoid
- Later encounters: Deadly, but player has learned

**Half-Life approach**:
- Opening sequence: Immersive but safe
- Time to experiment with controls
- Enemies introduced gradually

### The Forgiveness Window

Early mistakes should be forgiving:
- Don't punish experimentation
- Let players fail safely
- Teach consequences without severe penalty

Later, when players understand the rules, challenge them properly.

### Tutorial Levels: Handle With Care

**The problem**: Players skip tutorials to reach "real game."

**The solution**: 
- Make tutorials optional
- Make early "real game" easy enough to learn in
- Tutorial should supplement, not replace, good early design

**Half-Life did both**: Optional training level + forgiving opening sequence.

### Rewards During Learning

Players need positive reinforcement early:
- Celebrate small accomplishments
- Draw them in with success
- "This game is easy, I'm good at this!"
- Then gradually increase challenge

The goal: Player is invested before difficulty ramps up.

### Common Mistake: Too Hard at Start

Odyssey's opening was too punishing:
- Player shipwrecked, weaponless
- Monsters attack within seconds
- Cave hidden in woods (later moved to open)

**Lesson**: However obvious the solution seems to you, players are experiencing it fresh.

---

## Input: Controls

> "Nothing is more frustrating than knowing exactly what you want your game-world character to do but being unable to actually get him to do that because the controls will not let you."

### The Invisibility Goal

Perfect controls disappear—player thinks "jump" and character jumps without conscious thought of which button.

Every moment spent thinking about controls = moment pulled out of game experience.

### Simplicity Over Complexity

The keyboard has 100+ keys. Games have used nearly all of them.

**The problem**: Complex controls favor expert players, alienate novices.

**Console advantage**: Limited buttons force designers to refine, combine actions, focus on essentials.

**Result**: Easier to learn, more players can enjoy.

### Mouse-Only Success

Games like Diablo, StarCraft, and The Sims use mouse as primary input.

**Advantages**:
- Non-gamers already know the mouse
- Minimal learning curve
- Intuitive point-and-click

### Multiple Input Methods

Provide multiple ways to do the same thing:
- StarCraft: Right-click OR button bar OR hotkeys
- Console games: D-pad OR analog stick

Different players prefer different methods. Let them choose.

### Standard Conventions

Don't reinvent controls unnecessarily.

**Gettysburg! example**: Used click-and-drag instead of click-and-click for ordering troops. Marginally better, but confusion from non-standard approach outweighed benefit.

**Principle**: Use established conventions unless your innovation is significantly better—and playtested to prove it.

### Configurable Controls

**PC games**: Must allow key remapping. Many players will use defaults, so make defaults good, but power users need customization.

**Console games**: Controller layouts often standardized by genre. Deviation is jarring.

### The Complexity Creep of 3D

3D games require: forward, backward, left, right, up, down, turn left, turn right, pitch up, pitch down...

And that's before any gameplay actions.

**Successful 3D games**: Often restrict to ground plane (Mario 64, Quake, Tomb Raider), reducing control complexity.

### Controller Burnout

Over development, team adapts to poor controls.

**What seems natural to team**: May be impossible for newcomers.

**Solution**: First-impression testing specifically for controls. Watch new players struggle. Fix what they can't figure out.

---

## Output: Communicating Game State

Players need to understand what's happening in the game-world.

### Game-World View as Primary Output

Most information should come through the game itself:
- Character animation shows health
- Enemy behavior shows awareness state
- Environment shows progress/danger

The less that requires HUD, the more immersive the experience.

### HUD Design

When HUD is necessary:
- **Visual over numerical**: Health bar > health percentage
- **Minimal footprint**: Every pixel of HUD blocks game view
- **Glanceable**: Player should understand at a glance
- **Consistent location**: Don't move elements around

**Trend**: HUDs getting smaller or disappearing. Oddworld: Abe's Oddysee has no HUD—health shown through animation.

### Feedback Loops

Player does action → Game responds → Player learns

**Critical failures**:
- Action with no visible feedback
- Delayed feedback
- Ambiguous feedback

**Example**: If shooting enemy in weak spot, enemy should visibly react (recoil, scream) so player knows they're on the right track.

### Information Players Must Have

- Current health/resources
- Objective/goal status
- Threat awareness (enemies approaching)
- Progress indicators

If game tracks it and player needs it, player must be able to access it.

### Hidden Information

Some information intentionally hidden (enemy exact health, loot tables) for mystery/discovery.

**Rule**: Hide for design reasons, not because you forgot to display it.

---

## The Input/Output Loop

Controls (input) and feedback (output) form a loop:
1. Player wants action
2. Player performs input
3. Game processes action
4. Game provides output
5. Player perceives result
6. Player decides next action

### Latency Kills

Any delay in this loop breaks flow:
- Input lag: Character responds slowly
- Visual lag: Screen doesn't update
- Audio lag: Sound mismatched with action

Tight loop = immersive. Loose loop = frustrating.

### Proprioception in Games

In real life, you know where your body is without looking (proprioception).

In games, players develop similar sense for their character—but only with consistent controls and feedback.

> "When your controls are perfect, the wall separating the player from the game-world comes down."

---

## Design Principle Summary

| Principle | Application |
|-----------|-------------|
| Maintain Focus | Filter all decisions through core experience |
| Teach by Doing | Early game IS the tutorial |
| Forgive Early | Severe punishment comes after mastery |
| Reward Learning | Positive reinforcement builds engagement |
| Simplify Input | Fewer controls = broader audience |
| Use Conventions | Innovate mechanics, not controls |
| Show, Don't Number | Visual feedback over data displays |
| Complete the Loop | Tight input → output → input cycle |
| Watch Newcomers | Fresh eyes reveal what you've normalized |
