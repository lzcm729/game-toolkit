# Narrative & Indirect Control (Jesse Schell)

From "The Art of Game Design: A Book of Lenses" (3rd Edition)

## Core Concept

**Story and gameplay exist in duality.** Like wave-particle duality in physics, they are both manifestations of a singular phenomenon—the experience. Understanding how to merge them, and how to use indirect control to guide players while preserving their freedom, is essential to creating compelling interactive narratives.

---

## Story/Game Duality

Traditional stories: Single-threaded experiences, certain outcomes
Traditional games: Many possible outcomes, group experiences

Computer games challenge both paradigms—creating experiences with elements of both.

> "We don't care about creating either stories or games—we care about creating experiences."

---

## Two Real-World Methods

### Method 1: String of Pearls

```
[Story]——●——[Story]——●——[Story]——●——[Story]
         Pearl      Pearl      Pearl
         (Level)    (Level)    (Level)
```

**Structure:**
- Noninteractive story (string) delivered as cutscene
- Period of free movement and control (pearl/level)
- Fixed goal leads to next string

**Why It Works:**
- Player enjoys crafted story AND interactive challenge
- Reward for succeeding = more story + new challenges
- Games like *Ico*, *The Walking Dead*, *The Last of Us* show artful merging

### Method 2: Story Machine

**A good game generates stories when people play it.**

Games like *The Sims*, *Minecraft*, baseball, golf create sequences of events so interesting that players want to share them.

**Key Insight:** The more prescripting, the fewer stories the game generates.

### Lens #73: Story Machine

- When players have choices about achieving goals, how can I add more?
- How can I allow more types of conflict to arise?
- How can players personalize characters and setting?
- Do my rules lead to stories with good interest curves?
- Who can players tell the story to that will actually care?

---

## The Five Problems of Interactive Storytelling

### Problem #1: Good Stories Have Unity

Stories are crafted as wholes—beginning and ending are of a piece.

Interactive Cinderella: If she leaves home early, it's not Cinderella anymore. No alternate ending can compare to the crafted ending because the whole thing was designed as a unit.

### Problem #2: Combinatorial Explosion

10 choices deep × 3 options each = 88,573 outcomes
20 choices deep × 3 options each = 5,230,176,601 outcomes

**Usual Solution:** Fuse outcomes together—but then choices feel meaningless.

### Problem #3: Multiple Endings Disappoint

Players ask:
1. "Is this the real ending?" (They want the best/unified ending)
2. "Do I have to replay everything to see other endings?" (Tedious)

**Exception:** *Knights of the Old Republic*'s light side/dark side—two genuinely different complete stories.

### Problem #4: Not Enough Verbs

| Videogame Verbs | Movie Verbs |
|-----------------|-------------|
| run, shoot, jump, climb | talk, ask, negotiate, convince |
| throw, cast, punch, fly | argue, shout, plead, complain |

Games can't support conversation well—yet. When they can, it will be like the introduction of talkies.

### Problem #5: Time Travel Makes Tragedy Obsolete

Powerful tragic stories require **inevitability**—being carried toward certain doom.

Games give players time machines (save/load, checkpoints). Anything bad can be undone.

> "Freedom and destiny are polar opposites."

---

## The Story Stack

Design games **bottom-up** through this hierarchy:

```
        Story (Most Flexible)
           ↑
        World
           ↑
       Economy
           ↑
        Action
           ↑
       Fantasy (Least Flexible)
```

### 1. Fantasy (Start Here)
Either a fantasy appeals to a player or it doesn't—no middle ground.

### 2. Action
What player actions best fulfill the fantasy?
*Pixie Hollow* example: Girls wanted to **fly**, not just help animals.

### 3. Economy
System of progress that rewards fantasy-fulfilling actions.
*Pixie Hollow*: Barter system (pine needles, blueberries) fit fairy fantasy better than "fairybucks."

### 4. World
Place with rules where the economy makes sense.

### 5. Story
Explains why the world is the way it is, makes player actions meaningful.

**Critical Rule:** If you ever say "we can't do that—it goes against the story," story has taken over and trapped you.

---

## Story Tips for Game Designers

### Tip #1: Respect the Story Stack
Start with fantasy, not story. Story should serve the game, not enslave it.

### Tip #2: Put Your Story to Work
Story is the most flexible element. Use it to justify technical constraints, explain weird mechanics, solve design problems.

**Example:** Green fog (technical limitation) → "Evil aliens shrouded planet with toxic gas" (story solution)

### Tip #3: Goals, Obstacles, Conflicts
- Character with a goal
- Obstacles preventing the goal
- Conflicts arising from pursuit

### Lens #74: The Obstacle
- What is the relationship between character and goal?
- What obstacles stand between them?
- Is there an antagonist behind the obstacles?
- Do obstacles gradually increase?
- How does the protagonist transform to overcome them?

### Tip #4: Make It Real
> "Know your world as God knows this one." —Robert McKee

If it's not real to you, it's not real to them.

### Tip #5: Simplicity and Transcendence

Successful game worlds combine:
- **Simplicity:** World is simpler than real world
- **Transcendence:** Player has more power than in real world

| Genre | Simplicity | Transcendence |
|-------|-----------|---------------|
| Medieval | Primitive tech | Magic |
| Futuristic | Post-apocalyptic | Advanced tech |
| War | No normal rules | Weapons as godlike power |
| Modern | Criminal life (no laws) | Crime gives power |
| Abstract | Simpler than other games | Creation/destruction power |

### Lens #75: Simplicity and Transcendence
- How is my world simpler than the real world?
- What transcendent power do I give players?
- Is my combination contrived, or does it fulfill a wish?

### Tip #6: Consider the Hero's Journey
Vogler's synopsis (12 steps):
1. Ordinary world
2. Call to adventure
3. Refusal of the call
4. Meeting with the mentor
5. Crossing the threshold
6. Tests, allies, enemies
7. Approaching the cave
8. The ordeal
9. The reward
10. The road back
11. Resurrection
12. Returning with the elixir

### Lens #76: Hero's Journey
- Does my story have heroic elements?
- How does it match the hero's journey structure?
- Would more archetypal elements improve it?
- Does it match so closely it feels hackneyed?

### Tip #7: Keep Your World Consistent
One small inconsistency breaks the world forever. "Jumping the shark" phenomenon.

### Tip #8: Make Your World Accessible
Facts aren't always your friends. What players will believe is more important than physical accuracy.

*Pirates of the Caribbean* example: Ship speed made unrealistically fast because realistic speed felt boring. Wind blowing in wrong direction for gameplay. Flags reversed to look "normal."

### Lens #77: The Weirdest Thing
- What's the weirdest thing in my story?
- How can I ensure it doesn't confuse/alienate players?
- If multiple weird things, should I consolidate them?
- If nothing is weird, is it still interesting?

### Tip #9: Use Clichés Judiciously
Clichés are familiar = understandable. Combine familiar with novel.
Don't exile clichés from your toolbox—just don't overuse them.

### Tip #10: Sometimes a Map Brings a Story to Life
*Treasure Island* began as a map, not a story.

### Tip #11: Surprise and Emotion
If your story is dull, check for lack of surprise or emotion.

### Lens #78: Story
- Does my game really need a story? Why?
- Why will players be interested?
- How does story support other elements? How can it do better?
- How can my story be better?

---

## Indirect Control

**The feeling of freedom is more important than actual freedom.**

### Lens #79: Freedom
- When do players have freedom? Do they feel free?
- When are they constrained? Do they feel constrained?
- Where can they feel freer?
- Where are they overwhelmed by too much freedom?

### Six Methods of Indirect Control

#### Method #1: Constraints
Two doors vs. infinite options. Constrained choices feel like freedom but are predictable.

#### Method #2: Goals
If one door clearly leads toward the goal, you know which door players will choose.

#### Method #3: Interface
Physical interface implies what's possible. Plastic guitar = only guitar playing. Ship's wheel = only steering.

#### Method #4: Visual Design
Walt Disney's "weinie"—visual elements that draw the eye guide where players go.

*Aladdin VR* red line example: Single red line on floor guided 90%+ of players to the Sultan. When asked, players said "What red line?"

#### Method #5: Characters
If players care about characters, they'll do what characters want.
*Animal Crossing* Happy Room Academy: Players work hard for imaginary judges' approval.

### Lens #80: Help
- Who is the player helping?
- Can I make the player feel more connected to those who need help?
- How can helped characters show appreciation?

#### Method #6: Music
- Fast music → players eat/act faster
- Slow music → players linger

Use music to guide player actions without their awareness.

---

## Key Mantras

> "We don't always have to give true freedom—only the feeling of freedom."

> "Story should be a willing servant, not the master."

> "If it's not real to you, it's not real to them."

---

## Source

Schell, Jesse. *The Art of Game Design: A Book of Lenses* (3rd Edition). CRC Press, 2020. Chapters 17-18.
