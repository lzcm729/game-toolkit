# Playtesting

Playtesting is where average games become excellent. It's not optional polish—it's essential design work.

> "The common denominator, I would guess, is passion. Everyone says, 'Well, why aren't games better—why aren't there more really good games?' And I think that the answer is that what this industry doesn't do, amazingly, is play the games it makes. We create a game, we ask the teams to work all the hours God sends, and we don't give them time to play the game. That's really what makes the difference—sitting down and playing for hours and hours and hours." — Peter Molyneux

## Playtesting vs. Debugging

**Debugging**: Finding and fixing code problems (crashes, broken features, graphical glitches). A programming task.

**Playtesting**: Evaluating whether the game is *fun* and finding faults in game mechanics. A design task.

Examples of playtesting concerns:
- Unit too powerful, dominates game
- Enemy AI behaves illogically
- Controls feel unintuitive
- Difficulty spike too severe
- Puzzle solutions unclear

---

## Types of Testers

### 1. Development Team
- Should play constantly throughout development
- Know the game intimately, motivated to improve it
- **Drawbacks**: Too close to be objective, too skilled from practice, personal attachments to their own work

### 2. Traditional Testers
- Start at alpha, continue until ship
- Mix of bug hunting and gameplay feedback
- Full-time, paid employees who love games
- **Drawback**: Skewed toward hardcore gamer perspective

### 3. First-Impression Testers
- Fresh players who have never seen the game
- Single-session testing (30-60 minutes)
- "Kleenex testers"—use once, discard
- **Purpose**: Test learnability, initial experience, control intuitiveness

### 4. Fellow Game Designers
- Designers from other projects
- Can look past obvious early-stage problems
- Provide insight on fundamental design issues
- Best for early prototypes and "is this fun?" questions
- **Drawback**: Too busy to test extensively

### 5. Non-Gamers
- People who don't play games regularly
- High intolerance for traditional game problems
- Expose fundamental usability issues
- "The guy who fixes the coffee machine"
- **Drawback**: Can't provide constructive solutions

---

## Who Should NOT Test

### Your Boss
- Tester must feel free to speak honestly
- Boss has different goals (budget, timeline)
- Power dynamic corrupts feedback

### Marketing
- Believes they know what anonymous audiences want
- Second-guessing based on market trends
- Often wrong as often as right about gameplay

### Close Friends/Family
- Want to strengthen relationship, not criticize
- Will sugarcoat opinions
- Can work if relationship is brutally honest

### Idiots
- Say idiotic things with idiotic opinions
- Identify early, isolate, ignore

### Would-Be Designers
- Want to change things to "how I would do it"
- Suggestions based on personal preference, not improvement
- Try to design through you

---

## When to Test

### Phase: Early Prototype
**Who**: Fellow game designers, development team
**Focus**: Is the core concept fun? Does it show promise?
**Expectations**: Game will crash, art is placeholder, features incomplete

### Phase: Alpha
**Who**: Traditional testers, first-impression testers
**Focus**: Gameplay evaluation, interface testing
**Expectations**: Most features complete, significant bugs remain

### Phase: Beta
**Who**: Traditional testers, extensive first-impression testing
**Focus**: Final polish, difficulty balancing
**Expectations**: Feature-complete, bug-fixing priority

**Warning**: Don't bring in testers too early expecting to accelerate by finding bugs before alpha. Testers will find obvious bugs you already know about, wasting everyone's time. The game needs to be playable first.

---

## How to Test

### Watch, Don't Coach

The temptation: "Go over there," "Use strafe buttons," "Try the power-foozle!"

**The problem**: Designer can't ship in the box with the game.

**Correct approach**: 
- Sit behind tester, silent
- Watch their natural play
- Note where they struggle
- Resist urge to teach

If the player gets stuck or can't master controls, ask: "What's causing this?" not "Let me show you."

### Listen Honestly

Common designer defenses when hearing criticism:
- "That tester is a fool"
- "Not our target audience"
- "Just complaining for the sake of it"

**Reality check**: When multiple testers raise the same issue, there's a problem. Period.

### Guided vs. Unguided Testing

**Guided**: "Please test the new inventory system"
- Useful for specific features
- Risk: Miss larger problems elsewhere

**Unguided**: "Play the game however you want"
- Reveals problems designer overlooked
- Tests game holistically
- Essential complement to guided testing

**Best practice**: Do both. Note off-topic feedback for later even if focusing on specific system.

---

## Balancing

Only possible when most of the game is complete. Balancing incomplete games wastes effort—everything changes when remaining features are added.

### The Balancing Loop
1. Make a pass adjusting values
2. You and testers play the game
3. Gather feedback
4. Adjust values
5. Repeat until shipping

### System Attributes

Break gameplay into tunable numbers:

**Weapon example** (baseball bat):
- Damage per hit
- Attack speed
- Durability (hits before breaking)
- Cost
- Hands required

**Enemy example**:
- Health
- Damage
- Movement speed
- Detection range
- Aggression level

### Interconnected Systems

Changing one value affects others:
- Making one weapon stronger might break a later combat encounter
- Adjusting enemy health changes pacing of entire game

**Requirement**: Playtest every change across entire game, not just locally.

### Accessibility

Balancing data must be editable without programmer intervention:
- Configuration files
- Level editor tools
- Designer-accessible formats

---

## Your Game Is Too Hard

This is not a guess. This is a law.

### Why It's Always True

1. Development team has played for 9-18 months
2. Team is in top 10% of skill for this game
3. To stay entertained, team tuned game challenging for themselves
4. 90% of eventual players are worse than the team

### The Denial Cycle

1. Testers say "This game is too hard"
2. Designer thinks "They'll get better"
3. Testers DO get better over 3 months
4. Testers stop thinking it's hard
5. Game ships brutally difficult

### Counter-Measures

**The Marathon Technique** (Jason Jones):
- Can development team beat entire game on hardest setting using only the fist weapon?
- If yes, normal players with guns on normal difficulty have a fair chance

**The Handicap Principle**:
- If designer can win with both arms tied behind back, regular players can win normally

**Explicit Difficulty Awareness**:
- Assume difficulty is overtuned
- Bias toward "too easy" (players rarely complain about this)
- Multiple difficulty settings as safety valve

---

## Focus Groups vs. Playtesting

### Focus Groups
- "Off the street" participants
- 1-2 hour presentation on multiple games
- Often can't play (games not developed yet)
- Hear descriptions, say if they'd buy
- Run by marketing

### Playtesting
- Known testers with established trust
- Play actual games
- Provide actionable feedback
- Run by development team

### Why Focus Groups Are Dangerous

Imagine a focus group for:
- Pac-Man
- Tetris  
- Civilization
- The Sims

Will Wright: The Sims focus group went so poorly the game was nearly canceled. It became one of the best-selling games of all time.

**Focus groups favor safe, uninnovative games.** They're designed to find the lowest common denominator, not to recognize innovation.

---

## The Artistic Vision

### You Can't Please Everyone

With enough testers, someone will dislike everything.

**Wrong approach**: Try to make everyone happy → Game everyone thinks is "OK," no one loves

**Right approach**: Delight some players deeply → Passionate fans

### Not Design By Committee

You don't have to implement every suggestion. Some ideas are reasonable but don't fit *your* game.

> In the end, if every single playtester tells you some part of the game must change, but you feel, in your gut, as an artist, that you do not want to change that portion of the game, then leave it as it is.

A committee cannot have the unity of vision a single person maintains.

---

## Tester Relationship Management

### Know Your Testers

Different testers have different biases:
- **Whiners**: Complain about everything, even things that work
- **The Shy**: "Maybe look at X" means "Obviously X is broken"
- **The Expert**: Forgets what it's like to be new
- **The Perfectionist**: Wants changes that don't improve the game

Understanding personality helps weight feedback appropriately.

### The Ideal Tester

Provides feedback like: "When fighting the twelfth clown on level three, I thought he was too hard. I had no idea what I was supposed to do or whether my attacks were working. I tried rolling the boulder at him but couldn't figure out how."

- Specific problem identification
- Detailed explanation of confusion
- Notes what they attempted

**These testers are rare. Treasure them.**

---

## Playtesting Checklist

Early development:
- [ ] Core concept tested with trusted fellow designers
- [ ] Team playing regularly

Alpha:
- [ ] Traditional testers onboarded
- [ ] First-impression testing for controls/interface
- [ ] Feedback documented, not dismissed

Beta:
- [ ] Multiple balancing passes completed
- [ ] Difficulty tested with handicap methods
- [ ] Both guided and unguided testing performed
- [ ] Non-gamer testing for accessibility
- [ ] Problems from early testing re-verified as fixed

Throughout:
- [ ] Designer watches testers play silently
- [ ] All feedback recorded, even if not immediately addressed
- [ ] Multiple testers raising same issue = real problem
