# Game Balance (Jesse Schell)

From "The Art of Game Design: A Book of Lenses" (3rd Edition)

## Core Concept

**Game balancing is the process of adjusting game elements to create meaningful choices, fair competition, appropriate challenge, and satisfying experiences.** There are twelve major types of balance every designer must master.

---

## The Twelve Types of Balance

### Type 1: Fairness

**Symmetrical Games:** All players have identical resources/abilities.
- Easier to balance
- Pure skill comparison
- Examples: Chess, Go

**Asymmetrical Games:** Players have different resources/abilities.
- More interesting variety
- Harder to balance
- Examples: StarCraft races

**Balancing Asymmetry:**
Create a mathematical model, assign values to attributes, ensure totals are equal:

| Plane | Speed | Maneuver | Firepower | Total |
|-------|-------|----------|-----------|-------|
| Piranha | 2 | 2 | 4 | 8 |
| Revenger | 3 | 3 | 2 | 8 |
| Sopwith | 1 | 1 | 6 | 8 |

**Rock, Paper, Scissors Balance:**
- Rock beats scissors
- Scissors beats paper
- Paper beats rock
- No element is supreme

### Type 2: Challenge vs. Success

Keep players in the **flow channel** between boredom and frustration.

**Techniques:**
- Increase difficulty with each success
- Let skilled players get through easy parts fast
- Create "layers of challenge" (star ratings, grades)
- Let players choose difficulty level
- Playtest with variety of skill levels
- Give losers a break (Mario Kart power-ups)

**Key Question:** What percentage of players do I want to complete this game?

### Type 3: Meaningful Choices

> "A good game gives the player meaningful choices."

**Signs of meaningful choices:**
- Impact on what happens next
- Impact on game outcome
- Real tradeoffs

**Dominant Strategy = No Choice:**
If one option is clearly best, it's like having no choice at all.

**Mateas Formula:**
- If choices > desires → overwhelmed
- If choices < desires → frustrated
- If choices = desires → freedom and fulfillment

### Type 4: Triangularity

**The most exciting choice:** Play it safe for small reward OR take a risk for big reward.

```
        Player
         / \
        /   \
       /     \
   Safe/Low   Risky/High
   Reward     Reward
```

**Example - Space Invaders:**
- Regular aliens: Easy targets, 10-30 points
- Flying saucer: Hard to hit, dangerous, 100-300 points

**Balance test:** Use Expected Value
```
Expected Value = Probability × Reward
```
Both options should have similar expected value.

### Type 5: Skill vs. Chance

| Skill-Heavy | Chance-Heavy |
|-------------|--------------|
| Athletic contests | Casual, relaxed |
| Measure who's best | Fate decides |
| Serious tone | Anyone can win |

**Common pattern:** Alternate chance and skill
- Deal cards (chance) → Play cards (skill)
- Roll dice (chance) → Choose where to move (skill)

### Type 6: Head vs. Hands

Balance mental and physical challenges.

> "Baseball is 90% mental. The other half is physical." —Yogi Berra

**Questions:**
- Are players seeking mindless action or intellectual challenge?
- Can players succeed through dexterity OR clever strategy?
- On a scale of 1-10 (all physical to all mental), where is your game?

### Type 7: Competition vs. Cooperation

**Competition benefits:**
- Satisfies urge to prove skill
- Establishes status
- Creates drama

**Cooperation benefits:**
- Social bonding
- Team accomplishment
- More powerful than individuals

**Best of both:** Team competition

**Joust example:** Alternates between:
- "Team Wave" - Both survive = 3000 bonus each
- "Gladiator Wave" - First to defeat other = 3000 bonus

### Type 8: Short vs. Long

**Too short:** No time for meaningful strategies
**Too long:** Players grow bored, avoid time commitment

**Spy Hunter solution:** Unlimited lives for first 90 seconds, then limited.

**Minotaur solution:** "Armageddon" at 20 minutes forces confrontation.

### Type 9: Rewards

**Types of rewards:**
| Type | Description |
|------|-------------|
| Praise | "Great job!" sounds, animations |
| Points | Measure of success |
| Prolonged play | Extra lives, more time |
| Gateway | Access to new areas |
| Spectacle | Special animations, music |
| Expression | Customization options |
| Powers | Become more capable |
| Resources | In-game materials |
| Status | Leaderboards, achievements |
| Completion | Sense of closure |

**Reward Rules:**
1. Gradually increase reward value as player progresses
2. Variable rewards > Fixed rewards (unpredictability stays engaging)

### Type 10: Punishment

**Why punish?**
- Creates endogenous value (things can be lost)
- Makes risks exciting
- Increases challenge

**Types of punishment:**
| Type | Example |
|------|---------|
| Shaming | "Defeated!" message |
| Loss of points | Score decrease |
| Shortened play | Lose a life |
| Terminated play | Game over |
| Setback | Return to checkpoint |
| Removal of powers | Lose abilities |
| Resource depletion | Lose health, ammo |

**Key principle:**
> "Reward is always a better tool for reinforcement than punishment."

**Example:** Diablo food system changed from "must eat or suffer penalty" to "optional eating gives bonus." Same mechanic, different framing.

### Type 11: Freedom vs. Controlled Experience

How much player control?

**More freedom:**
- Player agency
- Emergent stories
- Replay value

**More control:**
- Better pacing
- Stronger narrative
- Guaranteed moments

**Aladdin's Magic Carpet solution:** In final scene, took away freedom because everyone wanted to do the same thing anyway. No one noticed.

### Type 12: Detail vs. Imagination

**Guidelines:**
- Only detail what you can do well
- Give details imagination can use
- Familiar worlds need less detail
- Use "binocular effect" (show close-up once, then small figures)
- Give details that inspire imagination

**Chess example:** Medieval court theme helps remember:
- Kings move slowly, must be protected
- Knights can jump (horses)
- Minimal detail, maximum imagination

---

## Elegance

> **Elegance** = Maximum output from minimum elements

**Test:** Count how many purposes each element serves.

**Pac-Man dots serve 5 purposes:**
1. Short-term goal ("eat nearby dots")
2. Long-term goal ("clear all dots")
3. Slow player down (triangularity)
4. Award points (measure success)
5. Points toward extra life

**Rule of thumb:** If an element serves only one purpose, consider combining it with another or removing it.

### Elegance vs. Character

Sometimes **quirks** make a game memorable:
- Monopoly tokens (hat, shoe, dog)
- Mario being a plumber
- Leaning Tower of Pisa's tilt

> "Elegance and character are opposites... must be kept in balance."

---

## Balancing Methodology

### The Process

1. **State the problem clearly** (Lens #14)
2. **Create a mathematical model** of relationships
3. **Playtest and observe**
4. **Adjust the model** based on results
5. **Repeat** until balanced

### Practical Tips

**Doubling and Halving:**
> "When changing values, start by doubling or halving."

If damage is 100 and seems too high, try 50, not 90.
Pushes limits to understand the range faster.

**Train Intuition by Guessing Exactly:**
Don't guess "about 15." Guess "13.8." Then check.
Over time, your intuition improves dramatically.

**Rule of Thumb:**
Half of development time should be spent balancing.
Six months minimum after having a working version.

---

## Key Lenses

### #37 Fairness
- Should my game be symmetrical? Why?
- How can players of different skill levels play together?

### #38 Challenge
- Are challenges too easy, too hard, or just right?
- How does challenge increase with success?

### #39 Meaningful Choices
- What choices am I asking players to make?
- Are they meaningful? How?
- Any dominant strategies?

### #40 Triangularity
- Do I have triangularity?
- Are rewards commensurate with risks?

### #46 Reward
- What rewards does my game give?
- Are they too regular? More variable?

### #47 Punishment
- What punishments exist?
- Do they seem fair?
- Could they be turned into rewards?

### #48 Simplicity/Complexity
- What innate complexity exists?
- Can it become emergent complexity?

### #49 Elegance
- What are my game's elements?
- How many purposes does each serve?

---

## Key Mantras

> "A prince should be quick to reward and slow to punish." —Ovid

> "Perfection is reached not when there is nothing left to add, but when there is nothing left to take away." —Saint-Exupery

> "You never know what is enough unless you know what is more than enough." —Blake

---

## Source

Schell, Jesse. *The Art of Game Design: A Book of Lenses* (3rd Edition). CRC Press, 2020. Chapter 13.
