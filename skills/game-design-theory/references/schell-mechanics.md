# Game Mechanics (Jesse Schell)

From "The Art of Game Design: A Book of Lenses" (3rd Edition)

## Core Concept

**Game mechanics are the core of what a game truly is.** They are the interactions and relationships that remain when all aesthetics, technology, and story are stripped away. Seven fundamental mechanics define how games work.

---

## The Seven Game Mechanics

### Mechanic 1: Space

Every game takes place in some kind of space—the "magic circle" of gameplay.

**Key Properties:**
- **Discrete vs. Continuous:** Tic-tac-toe has 9 discrete cells; a pool table is continuous
- **Dimensions:** 0D (points), 1D (line), 2D (board), 3D (physical space)
- **Bounded Areas:** May or may not be connected
- **Nested Spaces:** "Spaces within spaces" (e.g., towns on a world map)

**Example - Monopoly:**
Looks like 2D but is really 1D—a single line of 40 discrete points connected in a loop.

**Lens #26: Functional Space**
- Is the space discrete or continuous?
- How many dimensions does it have?
- What are the boundaries?
- Are there subspaces? How connected?

### Mechanic 2: Time

**Discrete vs. Continuous Time:**
- **Discrete:** Turn-based (Scrabble, Chess)
- **Continuous:** Real-time (most action games, sports)
- **Mixed:** Tournament chess (turn-based with continuous clock)

**Time Controls:**
- **Clocks:** Absolute time limits (shot clock, level timer)
- **Races:** Relative pressure (be faster than opponents)
- **Nested Time:** Multiple time hierarchies (quarters, halves, overtime)

**Controlling Time:**
- **Pause:** Time-outs, pause button
- **Speed up:** Civilization years passing in seconds
- **Rewind:** Checkpoints, save/load, Braid mechanics

**Lens #27: Time**
- What determines activity length?
- Are players frustrated by early endings?
- Bored by games going too long?
- Would clocks or races add excitement?

### Mechanic 3: Objects

Objects are the "nouns" of game mechanics. They populate the space and have **attributes** with **states**.

**Attributes:**
- **Static:** Never change (checker color)
- **Dynamic:** Change during play (checker becoming king)

**State Diagrams:**
Track attribute states and transitions. Example: Pac-Man ghost states:
- In Cage → Chasing Pac-Man
- Chasing → Blue (when power pellet eaten)
- Blue → In Cage (when eaten)

**Lens #28: State Machine**
- What are the objects in my game?
- What are their attributes?
- What are possible states for each?
- What triggers state changes?

### Secrets

Who knows what information is crucial:

| Info Type | Description |
|-----------|-------------|
| **Public** | Known to all (chess piece positions) |
| **Private** | Known to one player (poker hand) |
| **Game-only** | Known only to the system |
| **Random** | Not yet generated |

**Lens #29: Secrets**
- What is known by the game only?
- What is known by all players?
- What is known by some or one player?
- Would changing who knows what improve the game?

### Mechanic 4: Actions

Actions are the "verbs" of game mechanics.

**Two Types:**
1. **Basic Actions:** What players can physically do (move, jump, shoot)
2. **Strategic Actions:** Meaningful combinations (sacrifice a piece, set a trap)

**Emergent Gameplay Formula:**
```
Strategic Actions / Basic Actions = Emergence Ratio
```

High ratio = elegant, emergent game.

**Five Tips for Emergence:**

1. **Add more verbs:** More basic actions = more interaction potential
2. **Verbs that act on many objects:** One "shoot" acting on locks, windows, enemies
3. **Goals achievable multiple ways:** Avoid dominant strategies
4. **Many subjects:** Multiple pieces to coordinate
5. **Side effects that change constraints:** Every move alters the game state

**Lens #30: Emergence**
- How many verbs do players have?
- How many objects can each verb act on?
- How many ways to achieve goals?
- How do side effects change constraints?

**Lens #31: Action**
- What are the basic and strategic actions?
- Am I happy with the ratio?
- What actions do players wish they could do?

### Mechanic 5: Rules

Rules define everything: space, timing, objects, actions, consequences, constraints, and goals.

**Parlett's Rule Types:**

| Type | Description |
|------|-------------|
| **Operational** | What players do to play |
| **Foundational** | Abstract mathematical structure |
| **Behavioral** | Unwritten "good sportsmanship" |
| **Written** | Documented rules |
| **Laws** | Tournament/official clarifications |
| **House** | Player modifications |
| **Advisory** | Strategy tips (not real rules) |

**The Most Important Rule: The Goal**

Good goals are:
1. **Concrete:** Players can clearly state them
2. **Achievable:** Players believe they have a chance
3. **Rewarding:** Worth pursuing

**Lens #32: Goals**
- What is the ultimate goal?
- Is it clear to players?
- Are there meaningful subgoals?
- Are goals concrete, achievable, and rewarding?

**Lens #33: Rules**
- What are foundational vs. operational rules?
- Are there emerging "laws" or "house rules"?
- Are rules easy to understand?

### Mechanic 6: Skill

Skills shift focus from game to player.

**Three Skill Categories:**

1. **Physical Skills:** Strength, dexterity, coordination, endurance
2. **Mental Skills:** Memory, observation, puzzle solving, decision making
3. **Social Skills:** Reading opponents, deception, team coordination

**Real vs. Virtual Skills:**
- **Real:** What the player actually does (button timing)
- **Virtual:** What the character gains (sword fighting +2)

Virtual skills give feelings of power but can feel hollow if overemphasized.

**Lens #34: Skill**
- What skills does my game require?
- Are categories missing?
- Which skills are dominant?
- Can players improve with practice?
- Does game demand the right skill level?

### Mechanic 7: Chance

Chance = uncertainty = surprises = fun.

**Why Chance Matters:**
- Creates uncertainty
- Produces surprises
- Levels the playing field
- Creates tension

**Expected Value:**
```
Expected Value = Probability × Reward
```

Use this to balance risky vs. safe options.

**Skill vs. Chance Spectrum:**

| Pure Skill | Mixed | Pure Chance |
|------------|-------|-------------|
| Chess | Poker | Roulette |
| Sports | Backgammon | Lottery |

**Common Pattern:** Alternate chance and skill
- Deal cards (chance) → Play cards (skill)
- Roll dice (chance) → Choose where to move (skill)

---

## Key Mantras

> "A game is not just defined by its rules; a game IS its rules."

> "Interesting emergent actions are the hallmark of a good game."

> "You can never take chance for granted, for it is very tricky."

---

## Source

Schell, Jesse. *The Art of Game Design: A Book of Lenses* (3rd Edition). CRC Press, 2020. Chapter 12.
