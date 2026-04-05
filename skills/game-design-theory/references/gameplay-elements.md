# Gameplay Elements

The core mechanics and systems that make games compelling.

## Unique Solutions

One of the most exciting moments as a designer is hearing players describe successful tactics you never anticipated. Games should create situations where player creativity can flourish.

### Anticipatory vs. Complex Systems

**Anticipatory Design** (Limited):
- Designer predicts what players might try
- Hardcodes specific solutions to work
- Problem: Can't anticipate everything

**Complex Systems Design** (Preferred):
- Create consistent systems with properties
- Let systems interact naturally
- Solutions emerge from system rules, not case-by-case coding

**Example - Pressure Plate Puzzle**:

*Anticipatory approach*: "Puzzle solved if player uses rocks, weapons, or monsters"
- Fails when player tries snow from a Blizzard spell

*Systems approach*: "Every object has weight; puzzle solved when correct total weight placed"
- Works for any weighted object automatically
- Player discovers that their Blizzard spell creates enough snow to trigger the plate

### Emergence

When multiple consistent systems run in parallel, emergent strategies appear—solutions the designer never anticipated.

**Centipede "Blob Strategy" Example**:
Players discovered:
1. Flea drops problematic mushrooms
2. Flea doesn't appear on first wave
3. Flea triggered by few mushrooms in bottom screen half

**Emergent solution**: Clear all mushrooms on wave one, then only allow mushrooms in bottom-right quadrant. Flea never appears.

Ed Logg (the designer) didn't anticipate this. That's good design—players feel clever for discovering it.

**Design Principle**: The more complex systems working correctly in parallel, the more varied and interesting player solutions become. See Civilization as the gold standard.

---

## Non-Linearity

Non-linearity gives interactivity meaning. Without it, games might as well be movies.

### Types of Non-Linearity

#### 1. Storytelling
Story branches based on player choices. Most neglected form—many games have non-linear gameplay but completely linear stories.

#### 2. Multiple Solutions
Any challenge should have multiple ways to overcome it:
- Not every player thinks the same way
- Different solutions suit different playstyles
- Enables player creativity and ownership

#### 3. Order
Let players choose which challenges to attempt first:
- Put aside frustrating puzzles, work on others
- Return refreshed to difficult challenges
- Avoid "stuck on one thing, can't progress" syndrome

#### 4. Selection
Let players skip certain challenges entirely:
- Complete 2 of 3 available quests
- Choose challenges matching their strengths
- Optional side-quests for additional depth

### Implementation Example: Odyssey

A highly non-linear RPG design:
- Two quests available on first island (with multiple solutions each)
- Clever players can skip both quests entirely
- Next five islands freely navigable in any order
- Quests optional but make the game easier
- Multiple endings based on player goals

**Result**: No two players experience the game the same way.

### Why Non-Linearity Gets Cut

**Producer argument**: "If players only need to do X, why spend money on Y and Z?"

**Designer ego**: "I want players to experience everything I created."

**Response**: Non-linearity isn't waste—it's player agency. Players who feel trapped become frustrated. Replayability is a bonus, not the primary goal.

### The Purpose of Non-Linearity

> The true point of non-linearity is to surrender some degree of authorship to the player.

**Self-fulfilling prophecy**: "Players don't finish games anyway, so no need for non-linearity."

Reality: Players fail to finish *because* they get stuck at linear bottlenecks. Non-linear games let players route around obstacles.

### Balance: Not Too Much

Too much non-linearity = aimless wandering.

"In our game, players can do anything!" often ships as "solve puzzles on rails."

**Ideal**: Freedom + Guidance. Players feel free while designer maintains coherent experience.

---

## Modeling Reality

### The Reality Trap

More realistic ≠ more fun.

**What would more reality add to Tetris or Centipede?** Nothing.

**What would more realistic economics add to Civilization?** Tedium.

> "Films are life with the dull bits cut out." — Alfred Hitchcock

Games should be life with even more dull bits cut out.

**Example of too much reality**: Games requiring players to feed characters regularly. Eating scheduled meals isn't what people think of when imagining adventure.

### Benefits of Reality Modeling

Reality provides instant familiarity:
- Players know what's reasonable
- Implicit goals (SimCity: players know what a "good city" looks like)
- Intuitive expectations

### The Reality Expectations Problem

Once you model reality, players expect more reality:
- Early FPS games had no jumping → Players: "Why can't I jump over waist-high obstacles?"
- Added jumping → "Why can't I crouch?"
- Added crouching → "Why can't I lie flat on the ground?"

**Contrast with abstract games**: In Tetris, players never question their capabilities because boundaries were arbitrary from the start.

### Design Balance

Strike a balance between reality and abstraction:
- What does gameplay need?
- What does story/setting require?
- What can the engine handle?

**Critical insight**: More reality is not always better. Simulate only what serves fun.

---

## Rewards

Players need positive reinforcement, especially early on.

### Early Rewards Strategy

1. Start simple—basic actions only
2. Reward small accomplishments
3. Draw player in: "Ha ha, this game is easy!"
4. Gradually increase challenge
5. Player already invested, sees increased difficulty as surmountable

### Learning Through Rewards

**Prince of Persia approach**:
- First breakaway floor is non-lethal
- Spikes introduced in survivable situations
- Later encounters less forgiving, but player has learned

**Half-Life approach**:
- Safe, interesting introduction
- Time to learn controls without dying
- Tutorial level exists but isn't required—main game also teaches

### Tutorial Levels

Problems:
- Often not fun to play
- Players skip them to reach "real game"
- Can't replace making early game itself easy

**Solution**: Tutorial for players who want it, but design early game to be forgiving regardless.

---

## The Role of AI

Good AI serves gameplay, not realism.

### Goals of Game AI

1. **Challenge the player** - Appropriate difficulty
2. **Not do dumb things** - Avoid immersion-breaking stupidity
3. **Be unpredictable** - Fresh experience on replay
4. **Assist storytelling** - Behaviors that fit narrative
5. **Create a living world** - Ambient behaviors

### The Sloped Playing Field

AI doesn't need to play by the same rules as players:
- Rubber-banding in racing games
- AI with different (often worse) information than players
- Difficulty adjustment behind the scenes

**Key**: AI should *feel* fair even if it isn't technically equivalent.

### How Real is Too Real?

Sometimes realism improves AI (enemies can't see through walls), sometimes it hurts fun. Design for player experience, not simulation accuracy.
