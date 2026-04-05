# Planning and Iteration (Tynan Sylvester)

From "Designing Games: A Guide to Engineering Experiences"

## Core Insight

**Iteration is the most important method in game design.** You plan, build, test. Then you do it again and again, learning from each test.

The most important single determinant of game quality is the **number of iteration loops** it goes through.

## Planning Horizon

**PLANNING HORIZON:** The length of time a designer plans into the future.

### Choosing the Right Horizon

| Situation | Planning Horizon |
|-----------|------------------|
| Plans very uncertain | Short (test often) |
| Plans likely to work | Long (execute more before testing) |
| Original game | Short (nothing to build on) |
| Sequel/derivative | Long (established knowledge) |
| Low test cost | Short (why think when you can test in 15 min?) |
| Making conceptual leaps | Long (need to disconnect to find mountains) |

**Key principle:** Planning horizon should match uncertainty level.

**Project evolution:** Typically starts short (shifting sands of assumption), lengthens over time (worrying about tiny details in established structure).

## The Hill-Climbing Problem

**Iteration is a hill-climbing algorithm.** Blind mountaineer climbs whatever slope he's on, taking short steps, testing if they're improvements.

**Problem:** Can't tell if climbing mountain or hill. If starting on low hill, will reach top but miss nearby mountain.

**Solution:** Occasionally make large design changes without testing. Risky—might land in foothills—but only way to discover radical new ideas and escape design ruts.

## Why We Overplan

### Cultural Habit
We're taught to plan from young age. Works for Hoover Dam (known structure), not games (Halo changed from top-down strategy to FPS mid-development).

### Inborn Overconfidence (Optimism Bias)

**Quiz test:** Set 90% confidence ranges for 10 questions (birth year of Archimedes, etc.). Most people get 2-4 correct instead of expected 9.

> "A designer will have 90% confidence in a design that only has a 30% chance of actually working."

### Therapeutic Planning
Planning done to feel better about uncertain future, not to coordinate work. A plan takes away anxiety by creating false certainty.

### Group Planning Bias
Groups reward overconfident over rationally uncertain. "Confident Bob" gets followers even when "Rational Alice" is more accurate.

**Safety valve broken:** In weather, Bob gets proven wrong quickly. In game design, cause/effect hard to see, results take years, memory confused.

### Hindsight Bias
Silently rearranges memories to make past events look more predictable than they were.

After the fact, development always looks smoother than it was. We edit out tangents, mistakes, misunderstandings. The lessons are IN the messy parts we edit out.

## Test Protocol

**TEST PROTOCOL:** Set of rules and procedures for carrying out a playtest.

### Self-Testing
Cheapest. Reveals flow, pacing, balance problems. Good for earliest iteration loops.

### Over-the-Shoulder Playtesting
Designer watches others play. Can vary testers (old, young, aggressive, passive).

**Critical rule:** Remain completely silent. Don't talk, laugh, groan, or signal thoughts. Say "Sorry, I can't answer that." Painful to watch player stuck for 15 minutes, but telling them corrupts the test.

### Choosing Playtesters

| Type | Purpose |
|------|---------|
| **Kleenex testers** | Never played before; reveals first moments of play; can only use once |
| **Dedicated testers** | Play intensely for long periods; reveals high-skill balance |
| **Matching testers** | Knowledge approximates real player at that point in game |

### Sample Size
> "Good design decisions can only be made when a designer has built up an understanding of all the different experiences the game can generate."

**Rule of thumb:** Stop playtesting when testers start repeating same experiences often.

### Questioning Technique

**Best question:** "Tell me the story of what just happened in the game."
- Memory probe reveals what was perceived, retained, considered important
- Things not mentioned may be dead weight

**Don't ask:** "Did you notice the door on the left?" (Gives information, corrupts answer)
**Ask instead:** "Tell me about why you chose that path."

## Grayboxing

**GRAYBOX:** Low-fidelity placeholder version of mechanic, system, or level.

**Can graybox almost anything:**
- Cutscenes → still images or text popups
- Interfaces → labeled buttons
- Sounds → cheap synthesized beeps
- Dialogue → text-to-speech or on-screen text
- Creatures → cubes with rectangles for limbs (Mass Effect 3)

### Benefits
- Test and iterate without investing in art for unproven designs
- Might cost 100x less effort than finished version
- Artists appreciate it (their art gets thrown out less often)

### What Not to Graybox
Less useful for audiovisually-driven experiences (LIMBO, Flower would suffer; Counter-Strike would play well).

### Premature Production
**Definition:** Adding polished assets too early.

**Short-term:** Feels great, smiles in review meetings.
**Long-term:** Every iteration slowed by reworking art. Art cost paid again and again. Weak mechanical core can't be fixed without tearing art off.

**Discipline required:** After failed playtest, tempting to cover design faults with art. But unless art brings useful data in next test, it's a mistake.

### Graybox Evaluation Skill
Playing good graybox ≠ playing good game. Skill must be learned through practice.

**Problem:** People without this skill reject excellent graybox because it's ugly (halo effect). Nobody without practice should make decisions about graybox design.

## The Paradox of Quality

> "In game design, temporarily accepting poor-quality work ultimately leads to better-quality work."

Traditional: Work slowly, attend to every detail → quality product.
Games: Obsession with quality at every stage slows iteration → poorer game.

**Don't reject imperfect work in early iterations.** Designer who does this is like novelist who can't get word down because it needs to be perfect.

Work in earliest iterations isn't building final game—it's building platform from which to jump to final game.

## The Fallacy of Vision

**FALLACY OF VISION:** Idea that mental movie of experience equals design for system that generates that experience.

**Aerospace engineer example:**
- Bad: "Passengers board hassle-free, enjoy martinis in private booths, love is found..."
- This describes flight experience, not airplane design

**Vision tells nothing about:**
- Trade-offs and costs in system
- All the OTHER experiences game will generate
- Flaws (we naturally envision only best experiences)

**Antidote:** Instead of envisioning best experiences, envision the worst. Picture every frustrating failure, boring grind, unclear interaction.

## Serendipity

> "Most revolutionary game designs aren't authored—they're stumbled upon."

**Examples:**
- Big Daddy (BioShock): Originally generic mutant in diving suit
- GLaDOS voice (Portal): Noticed players found text-to-speech funnier than expected
- Braid's final level: Discovered late when Jon Blow realized time-shift could reverse character
- Tetris: Emerged from Russian puzzle game pentominoes
- The Sims: From architecture simulation when Will Wright noticed players liked characters more than houses
- SimCity: Wright enjoyed making maps more than blowing them up

**For deep planners:** Capturing serendipity means throwing out beloved, costly plan. Often, they throw out serendipity instead.

**For iterators:** Future is open—can fill it with new discoveries as they appear.

**Key to capturing serendipity:**
1. Be observant (notice strange behaviors, nonsensical results)
2. Be adaptable (reorganize thoughts around observations, not observations around worldview)

## Key Mantras

- "The most important single determinant of the quality of a game is the number of iteration loops it goes through."
- "Good tools let you take risks. This is how they let you discover designs that you could not notice if work was so slow that you had to plan and get everything right the first time."
- "In game design, temporarily accepting poor-quality work ultimately leads to better-quality work."
- "A mental movie of an experience is NOT equivalent to a design for a system that generates that experience."
