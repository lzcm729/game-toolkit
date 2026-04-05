# Interface Design (Jesse Schell)

From "The Art of Game Design: A Book of Lenses" (3rd Edition)

## Core Concept

**The interface is the gateway between player and game world.** Good interface design makes players feel powerful and in control. Information flows in a loop: Player → Physical Interface → Virtual Interface → World → Back to Player.

---

## The Feedback Loop

```
Player → Physical Input → Game World → Virtual Output → Player (loop)
```

Information flows continuously. The quality of this feedback dramatically affects player understanding and enjoyment.

### The Tenth of a Second Rule

If your interface doesn't respond to player input within **1/10 second**, players feel something is wrong.

**Common Problem:** Jump animations with wind-up/anticipation. Player pushes button, but character doesn't leave ground for half a second → frustration.

---

## Feedback

**Feedback is:** Judgment, reward, instruction, encouragement, and challenge.

**Example - Basketball Net:**
The net doesn't affect gameplay—it slows the ball so players can clearly see and hear the score.

**Example - Swiffer:**
Shows dirt on the cleaning cloth after use → concrete evidence of accomplishment.

### Lens #63: Feedback

- What do players need to know at this moment?
- What do players want to know?
- What do you want players to feel? How can feedback create that?
- What is the player's goal? What feedback helps toward it?

---

## Juiciness

**Juicy = Maximum output from minimum input**

Juicy interfaces give continuous, powerful, rewarding feedback. A little interaction → delicious flow of rewards.

**Key Element: Second-Order Motion**
Motion derived from player action that is:
- Easy to control
- Gives powerful feedback
- Rewards the player

**Example - Swiffer handle:**
Small wrist rotation → dramatic base movement. Feels like running a magic race car across the floor.

### Lens #64: Juiciness

- Is my interface giving continuous feedback for actions?
- Is second-order motion powerful and interesting?
- When I give a reward, how many ways am I simultaneously rewarding?

---

## Primality

**Primal = So intuitive an animal could do it.**

Touch interfaces are primal (300-400 million years of evolution). Tool use (mouse, controller) requires higher brain function (3 million years).

**Primal Game Elements:**
- Gather fruit-like items
- Fight threatening enemies
- Find your way through unfamiliar environments
- Overcome obstacles to get to a mate

### Lens #65: Primality

- What parts of my game are so primal an animal could play?
- What parts could be more primal?

---

## Channels and Dimensions

### Step 1: List and Prioritize Information

Example (Zelda-like game):
- **Every moment:** Immediate surroundings
- **Glance occasionally:** Health, keys, current weapon, rubies
- **Occasionally:** Full inventory

### Step 2: List Channels

Channels are ways of communicating data:
- Top/bottom/side of screen
- Avatar appearance
- Sound effects
- Music
- Borders
- Enemy indicators
- Word balloons

### Step 3: Map Information to Channels

Match importance to visibility:
- Most important → Most visible channel
- Least important → Hidden submenu

### Step 4: Review Dimensions

Each channel has multiple dimensions:
- Number displayed
- Color
- Size
- Font
- Position

Can use dimensions to:
- **Reinforce:** All dimensions emphasize same info
- **Multiplex:** Different dimensions carry different info

### Lens #66: Channels and Dimensions

- What data need to travel to/from the player?
- Which data are most important?
- What channels are available?
- Which channels are most appropriate for which data?
- How should I use the dimensions?

---

## Modes

A **mode** is a change in interface mapping. Same button does different things in different modes.

### Mode Tips

**Tip #1: Use as Few Modes as Possible**
Fewer modes = less confusion.

**Tip #2: Avoid Overlapping Modes**
If two modes use the same input channel, don't let them overlap.

**Tip #3: Make Different Modes Look Different**
Players must know what mode they're in:
- Change something large and visible on screen
- Change the action avatar is taking
- Change on-screen data
- Change camera perspective

### Lens #67: Modes

- What modes do I need? Why?
- Can any modes be collapsed or combined?
- Are modes overlapping? Can I put them on different input channels?
- How does the player know when mode changes?

---

## Interface Tips

### Tip #1: Steal (Top-Down)
Start with interface from successful game in same genre.

### Tip #2: Customize (Bottom-Up)
Design from scratch by listing information, channels, dimensions.

### Tip #3: Design Around Physical Interface
Games designed for specific hardware (touch, motion, controller) feel better than platform-agnostic designs.

### Tip #4: Theme Your Interface
Apply Lens #11: Unification to every inch of interface.

### Tip #5: Sound Maps to Touch
Sound simulates tactile feedback. Use clicks, whooshes, impacts to create sense of physical manipulation.

### Tip #6: Balance Options and Simplicity with Layers
Hide complexity in submodes. Keep primary interface clean.

### Tip #7: Use Metaphors
Make interface resemble something familiar.

**Example - ToyTopia radio signal:**
Visible radio wave traveling from button to toy explains network delay—turned confusion into understanding.

### Lens #67½: Metaphor

- Is my interface a metaphor for something else?
- Am I making the most of that metaphor?
- Would it be more intuitive if it were a metaphor?

### Tip #8: If It Looks Different, It Should Act Different
Same appearance → Same behavior
Different appearance → Different behavior

### Tip #9: Test, Test, Test!
No one gets interface right the first time. Prototype early and often.

### Tip #10: Break Rules to Help Players
Example: In single-button games, make both mouse buttons work—children often click the wrong one.

---

## Key Mantras

> "Fun is pleasure with surprises—if your interface is going to be fun, it should give both."

> "The mind easily maps sound to touch."

> "The more primal, the more intuitive."

---

## Source

Schell, Jesse. *The Art of Game Design: A Book of Lenses* (3rd Edition). CRC Press, 2020. Chapter 15.
