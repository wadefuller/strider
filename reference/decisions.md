# The decisions log

`decisions.md` sits in the training folder next to `athlete.md` and `plan.json`. It is the coach's memory of what the runner has told it, so nothing has to be said twice. It outlives any one block. (`plan.log` is different: it records what happened to this plan.)

## Read it first

Every skill starts with `coach.py decisions decisions.md`. It prints the entries in force today. Apply each one as if it were a rule in the plan. If it reports a `PROBLEM`, fix the entry with the runner before relying on it.

When a decision and the plan disagree, the decision wins until the runner says otherwise. Say which decision you applied ("Using the mapped distance for the river loop, as you asked on 11 Feb").

## Add one when

| The runner... | Kind | Applies |
|---|---|---|
| corrects a number or a reading ("the watch reads long on the bridge", "that max HR was a spike") | `correction` | standing |
| states how they want to train ("long run on Saturdays", "no doubles", "tell me splits in miles") | `preference` | standing |
| overrides a verdict ("I ran it anyway", "I want to keep the goal") and says why | `override` | once |
| has a dated exception (travel, illness, a work crunch) | `exception` | until DATE |
| confirms or changes the goal | `goal` | standing |
| tells you something worth keeping that fits none of these | `note` | standing |

```
coach.py decide decisions.md --kind correction --what "..." --why "..." [--applies until:2027-03-01] [--replaces 2027-02-01]
```

Rules:

- **Their words, not yours.** `What` is the decision in one sentence. `Why` is the runner's reason, or the data behind it with `--source data`.
- **Say you are keeping it.** "I've noted that for next time" is enough. Never record something the runner asked you not to keep.
- **Replace, do not contradict.** When a preference changes, add the new entry with `--replaces <date of the old one>` (same kind). The old one drops out of `decisions`.
- **Not for health data you do not need.** Record that a niggle exists and what it changes in training. Do not record diagnoses or medication.
- **Unattended runs propose.** A scheduled skill may suggest a decision in its report, but only adds it after the runner says yes.
- **Never commit it.** It is personal. The repository's `.gitignore` excludes `/decisions.md`.
