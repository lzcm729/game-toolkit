# Iteration & Prototyping (Jesse Schell)

From "The Art of Game Design: A Book of Lenses" (3rd Edition)

## Core Concept

**The game improves through iteration.** More loops = better game. The Rule of the Loop is the fundamental principle: the faster and more frequently you iterate, the better your game becomes. Every prototype should answer a question, and every risk should be mitigated early.

---

## The Rule of the Loop

> "The more times you test and improve your design, the better your game will be."

**The Informal Loop:**
1. Think of an idea
2. Try it out
3. Keep changing and testing until good enough

**The Formal Loop:**
1. State the problem
2. Brainstorm possible solutions
3. Choose a solution
4. List the risks
5. Build prototypes to mitigate risks
6. Test the prototypes—if good enough, stop
7. State new problems, go to step 2

---

## Risk Mitigation

**Identify risks early, address them immediately.**

### Lens #16: Risk Mitigation

> "Because the sage always confronts difficulties, he never experiences them." —Tao Te Ching

- What could keep this game from being great?
- How can we stop that from happening?

**Example Risks for "Bubble Rescue" Game:**

| Risk | Mitigation |
|------|------------|
| Core mechanic might not be fun | Build abstract 2D prototype in 1-2 weeks |
| Engine can't handle all elements | Build rendering stress-test prototype |
| Not enough time for all artwork | Artist creates one house to time it |
| Players might not like characters | Concept art + storyboards → focus test |
| Publisher might change theme | Push for decision OR design for flexibility |

---

## Ten Prototyping Tips

### Tip #1: Answer a Question

Every prototype must answer specific questions:
- How many animated characters can our tech support?
- Is our core gameplay fun?
- Do our characters and settings fit together aesthetically?
- How large does a level need to be?

**Resist overbuilding.** Focus only on answering the key question.

### Tip #2: Forget Quality

**Quick and dirty is the goal.** All that matters is whether it answers the question.

Polishing prototypes can **hide problems**—playtesters are more likely to point out issues with rough work than with polished work.

### Tip #3: Don't Get Attached

> "Plan to throw one away—you will anyway." —Fred Brooks

**Mind-set:** All prototypes are temporary. Keep pieces that work, discard the rest.

> "You must learn how to cut up your babies." —Nicole Epps

### Tip #4: Prioritize Your Prototypes

Face the biggest risks first. Consider dependencies—if one prototype's results could make others meaningless, do it first.

### Tip #5: Parallelize Prototypes Productively

Run multiple prototypes simultaneously:
- Engineers work on technology questions
- Artists work on art prototypes
- Designers work on gameplay prototypes

More loops in less time.

### Tip #6: It Doesn't Have to Be Digital

**Paper prototypes** can test videogame ideas:

**Tetris Paper Prototype:**
- Cut out cardboard pieces
- Someone slides them down a drawn "board"
- You grab and rotate them
- Use imagination or X-Acto knife to complete lines

**Halo Paper Prototype:**
- Graph paper map
- Game pieces for players/enemies
- Metronome app (one tick = one move)
- Slow-motion gives time to think about what works

**Benefits:**
- Lightning fast iteration
- Forces you to understand core mechanics
- Problems surface immediately

### Tip #7: It Doesn't Have to Be Interactive

Sketches and animations can answer questions about gameplay.

*Prince of Persia: Sands of Time* was prototyped with noninteractive animations of the acrobatics, helping the team visualize before coding.

### Tip #8: Pick a "Fast Loop" Game Engine

**Traditional (Baking Bread):**
1. Write code
2. Compile and link
3. Run game
4. Navigate to test area
5. Test
6. Repeat

**Fast Loop (Working with Clay):**
1. Run game
2. Navigate to test area
3. Test
4. Write code (while running)
5. Return to step 3

Scripting systems (Python, Lua, Blueprint, etc.) that allow runtime modification = more loops per day.

### Tip #9: Build the Toy First

Many games are built on top of toys. Make sure the toy is fun before designing the game around it.

**Examples:**
- Ball (toy) → Baseball (game)
- Running/jumping avatar (toy) → Donkey Kong (game)
- *Lemmings*: Built the "living world" first, then designed the game
- *GTA*: "Living, breathing city" first → "GTA came from Pac-Man"

### Lens #17: The Toy

- If my game had no goal, would it be fun at all?
- When people see my game, do they want to interact before knowing what to do?

### Tip #10: Seize Opportunities for More Loops

Unexpected events sometimes allow more loops.

**Halo Example:** Platform changes (Mac → PC → Xbox) forced rework but also gave time for more iteration. Each change = opportunity to improve gameplay.

---

## The Passion Check

### Lens #18: Passion

At the end of each prototype cycle:
- Am I filled with blinding passion about how great this game will be?
- If I've lost the passion, can I find it again?
- If the passion isn't coming back, shouldn't I be doing something else?

---

## How Much Is Enough?

> "The work is never finished—only abandoned."

**Mark Cerny's Method:**
- **Preproduction:** Until you have two publishable levels with all necessary features
- **Production:** Once you know what the game really is, you can schedule
- **Rule of Thumb:** This point is reached when ~30% of budget is spent

**Schell's Rules:**

**Plan-To-Cut Rule:**
Build so that if 50% of budget were removed, you'd still have a shippable game.

**50% Rule:**
All core gameplay should be fully playable at the halfway mark in your schedule.
- First half: Get it working
- Second half: Make it great

---

## Loop Examples

**Loop 1: "New Racing" Game**
- Problem: Come up with new racing concept
- Solution: Underwater submarine races with torpedoes
- Risks: Trackdesign unclear, might not feel innovative, tech limits
- Prototypes: Concept sketches, hacked existing racer, water effects test
- Results: Glowing path works, flying subs feel novel, some effects too expensive

**Loop 2: "Racing Subs" Game**
- New Problem: Design racing sub game where subs can fly
- More specific questions about art style, balance, networking

**Loop 3: "Flying Dinos" Game**
- Problem: Design flying dino game
- Even more specific: animation scheduling, level count, power-ups, weapons

**Key Pattern:** Problems get more specific with each loop. Ugly problems surface quickly because of early loops.

---

## Key Mantras

> "The more times you test and improve, the better your game will be."

> "Every prototype should answer a question."

> "Quick and dirty, not slow and beautiful."

> "Face the biggest risks first."

> "Plan to throw one away—you will anyway."

---

## Source

Schell, Jesse. *The Art of Game Design: A Book of Lenses* (3rd Edition). CRC Press, 2020. Chapter 8.
