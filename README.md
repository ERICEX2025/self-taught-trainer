# Self-Taught Trainer

**A self-improving agent harness that learns a game its own model gets wrong.**
Built at the MongoDB × Cerebral Valley *Harness Engineering & Model Wrangling* hackathon, NYC, Sept 26 2026 (Statement One: Recursive Harnessing).

An LLM plays Pokémon Showdown **Gen 1 OU** (the original Red/Blue rules) with a fixed team. The model never changes. What changes is its **harness**: the instructions, rules, tools and context it reads every turn. A coach model studies the player's losses (including the player's own one-line reasoning for every move), proposes several changes, and only the changes that win a fair, re-tested comparison are kept. Everything lives in MongoDB Atlas.

Gen 1 is deliberately hard mode: its mechanics differ from modern Pokémon, so the model's instincts are often wrong. Improvements have to come from the agent's own games, not from what the model already "knows".

## What it discovered on its own

In the first run, starting from a one-sentence generic prompt:

1. **"Use Hyper Beam mainly as a finisher."** The coach saw losses like *Victreebel (55%) Hyper Beams a full-HP Snorlax, fails to KO, then loses a turn recharging*. Kept after a head-to-head re-test (50% → 59%).
2. **"If Hyper Beam is likely to KO, use it: in Gen 1 a KO skips the recharge turn."** The coach then noticed the player had become too cautious, finishing a 5%-HP Snorlax with Razor Leaf "without risking Hyper Beam recharge". This is a real Gen 1-only mechanic. Kept: **52% → 71%** averaged over the first test and the re-test.

## How it works

```
play (fresh battles) → coach reads losses + wins + player reasons + past lessons (Atlas vector search)
   → 3–4 candidate changes (rule, prompt, context, or a tool it writes in Python, run in a sandbox)
   → every candidate AND the current best play fresh battles at the same time
   → the top candidate is re-tested head-to-head (the best of 4 is usually lucky)
   → kept only if it beats the best by a margin; rejected ideas are shown to the coach next time
```

- `stt/adapter.py` the only game-specific code: battle → text, legal actions
- `stt/harness.py` the harness as a document, and the player that reads it every turn
- `stt/coach.py` the coach, the change types, and verified example quotes for kept changes
- `stt/tools.py` sandbox for tools the coach writes (restricted builtins, banned words, test run)
- `stt/loop.py` the self-improvement loop
- `stt/ladder.py` puts a harness version on the PokéAgent Challenge ladder
- `lab.html` live view: Discoveries, Live, Harness, Evolution, Benchmark ladder, Atlas

## MongoDB Atlas is the system's memory

| Collection | One document | Used for |
|---|---|---|
| `harness_versions` | one harness version, its score, and its parent | the family tree of every version, kept or rolled back |
| `battles` | one battle, every turn, the move and the player's reason | the coach's evidence; ladder and win-rate stats |
| `reflections` | one coach decision: what it saw, proposed, and what the test decided | the audit trail and the Discoveries view |
| `lessons` | a learned sentence with an embedding | recalled by **Atlas Vector Search** before each coach decision; `archived` is a vector-index filter |

Also used: **aggregation pipelines** (ladder results per opponent family, win rate per version, computed in Atlas), a **change stream** (live feed of every write in the lab), and a vector index created from code.

## Checked against the outside world

- **PokéAgent Challenge** (NeurIPS 2025 benchmark): the starting harness (`stt-base`) and the evolved one (`stt-evolved`) play ranked Gen 1 OU games against the organizers' RL agents and rule bots. Same model, same team; only the harness differs.
- **PokéChamp** (ICML 2025), an expert hand-built LLM harness, run locally with the same model, team and opponent as the comparison arm.
- **Held-out opponent**: versions are re-scored against a bot the loop never trained against.

## Run it

```bash
python -m stt.loop --run r1 --generations 5 --battles 60   # needs a local Showdown server on :8000
python -m stt.ladder stt-base r1.v1 30                       # PokéAgent ladder
python -m stt.feed & python -m stt.stats &                   # change stream + Atlas stats for the lab
python -m http.server 8800 --bind 127.0.0.1                  # open http://127.0.0.1:8800/lab.html
```

`.env`: `OPENAI_API_KEY`, `MONGODB_URI`, `MONGODB_DB`, `POKEAGENT_PASSWORD`.
Player: GPT-5.4 mini (reasoning off), fixed all day. Coach: GPT-5.4.
