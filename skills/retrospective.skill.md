---
allowed-tools: Bash(git diff:*), Bash(git log:*), Bash(git show:*), Read, Glob, Grep
description: Critical self-review that challenges implementation quality before PR
---

# Retrospective Command

Rigorous self-critique of recent work. Challenges assumptions, questions decisions, and pushes for elegant solutions over "good enough" fixes.

**Philosophy**: Don't settle for the first working solution. Ask "knowing everything I know now, what's the elegant way to solve this?"

## When to Use

* Before creating a PR
* After completing a feature/fix
* When something feels "off" but works
* When you want to challenge mediocre solutions

## Instructions

### Step 1: Gather Context

Determine scope based on arguments:

* No args: Review current feature branch vs main
* `--session`: Review work from current session (today's commits)
* `--commits N`: Review last N commits
* `--files path1 path2`: Review specific files

Run appropriate git commands to gather the diff.

### Step 2: The Grilling

Ask yourself these questions about EACH significant change. Be brutally honest.

#### Design Questions

1. **Why this approach?** What alternatives did I consider? Why were they rejected?
2. **Hidden complexity?** Am I pushing complexity somewhere it doesn't belong?
3. **Future me test**: Will I understand this in 6 months without comments?
4. **Delete test**: What's the minimum code that would solve this? Did I over-engineer?
5. **Name test**: Do names reveal intent or hide it? Any "Utils", "Helper", "Manager"?

#### Quality Questions

6. **Edge cases**: What inputs would break this? Empty collections? Nulls? Concurrency?
7. **Error paths**: What happens when things go wrong? Do errors propagate correctly?
8. **Performance traps**: Any N+1 queries? Unbounded loops? Memory leaks?
9. **Test coverage**: Can I prove this works? What's untestable about it?

#### Architecture Questions

10. **Dependency direction**: Does this create unwanted coupling?
11. **Single responsibility**: Is this class/method doing too much?
12. **Abstraction level**: Am I mixing high-level orchestration with low-level details?

### Step 3: The Verdict

Rate the implementation honestly:

| Grade | Meaning                      | Action                 |
|-------|------------------------------|------------------------|
| **A** | Elegant, minimal, clear      | Ready for PR           |
| **B** | Good but has rough edges     | Minor cleanup, then PR |
| **C** | Works but mediocre           | Consider rewrite       |
| **D** | Hacky, will cause problems   | Must rewrite           |
| **F** | Fundamentally wrong approach | Start over             |

### Step 4: The Challenge

If grade is C or below, ask:

> "Knowing everything you know now about this problem, the codebase, and the edge cases - if you could start fresh, what would the elegant solution look like?"

Then write a **detailed spec** for the better approach:

```markdown
## Elegant Solution Spec

### Problem Statement
[What we're actually solving, in one sentence]

### Key Insight
[The "aha" that makes this elegant vs hacky]

### Approach
[Step by step, with specific file/class names]

### Why This Is Better
[Concrete improvements over current implementation]

### Migration Path
[How to get from current to elegant without breaking things]
```

### Step 5: Quality Gate

Before approving for PR, verify:

* [ ] No TODOs that should be done now
* [ ] No commented-out code
* [ ] No magic numbers/strings without constants
* [ ] No copy-paste that should be abstracted
* [ ] Error messages are helpful, not cryptic
* [ ] Logging is appropriate (not too verbose, not silent)
* [ ] Tests exist and test the right things

### Step 6: Output

Present findings in this format:

```markdown
## Retrospective: [Feature/Branch Name]

### Summary
[1-2 sentences on what was built]

### Grade: [A/B/C/D/F]

### What's Good
- [Genuine positives, not participation trophies]

### What's Concerning
- [Honest issues, ranked by severity]

### The Hard Question
[The one thing that's nagging at you about this implementation]

### Recommendation
[ ] Ready for PR
[ ] Minor fixes first (list them)
[ ] Needs rewrite (spec below)
[ ] Needs discussion with team

### [If rewrite needed] Elegant Solution Spec
[Detailed spec as described above]
```

## Examples

### Example: Mediocre Fix

Grade: C

What's Concerning:

* Added a boolean flag to handle special case - this will grow into a mess
* Three nested if statements that should be strategy pattern
* "Helper" method that's doing two unrelated things

The Hard Question:

Why are we special-casing this at all? The real problem is the data model
doesn't represent the domain correctly.

Recommendation: Needs rewrite

Elegant Solution Spec:
...

### Example: Good Work

Grade: A

What's Good:

* Clean separation between parsing and validation
* Error messages include context for debugging
* Edge cases handled with early returns, not nested ifs

What's Concerning:

* Minor: Variable name 'x' in line 42 could be more descriptive

Recommendation: Ready for PR (fix the variable name first)

## Notes

* Be your own toughest critic - it's easier to fix now than after merge
* "It works" is necessary but not sufficient
* Technical debt is a choice, not an accident - make it consciously
* The elegant solution often has LESS code, not more
