Run examined: `ladder:stt-base`, version `v1`. Read `README.md` and `HEAL.md` first. No Langfuse or Sentry MCP was connected, so the evidence comes from `observability/battles.jsonl` and `observability/summary.json`: 120 battles, 14 wins, 4,558 logged decisions, and five invalid answers.

The defect is misleading serialization of the special `fight` and `recharge` commands in the player's legal-action list. The log contains 194 `move:fight` actions across 80 battles (193 valid answers and one random fallback), plus 50 `move:recharge` actions. These examples show the player repeatedly interpreting `fight` as an attack:

| Battle | Turn | Recorded evidence |
| --- | --- | --- |
| `battle-gen1ou-18974234` | 13 | Cloyster at 92% HP versus Cloyster at 11%; valid `move:fight`, reason: “Fight can finish the weakened opposing Cloyster immediately.” |
| `battle-gen1ou-18969818` | 36 | Chansey at 29% versus Tauros at 8%; valid `move:fight`, reason: “Fighting is our only chance to finish the weakened Tauros.” |
| `battle-gen1ou-18969857` | 32 | Chansey at 85% versus Jynx at 58%; valid `move:fight`, reason: “The only legal move is to use Sleep Talk/Fight while asleep.” |
| `battle-gen1ou-18974263` | 20 | Valid `move:recharge`, reason: “Recharge is the only legal action available.” This establishes that the other command affected by the same serialization defect also occurs in the run. |

The installed poke-env library constructs synthetic `Move` objects for `fight` and `recharge`. Their placeholder data becomes Normal type, zero power, physical category, and `0.01` accuracy in Gen 1. `stt.adapter.describe()` treated those placeholders as real move data. Reproducing a Showdown request through the installed `Battle.parse_request()` produced this player-facing line before the fix:

```text
  move:fight  type Normal, power 0, physical, accuracy 0.01
```

Showdown's request-generation code identifies `fight` as the Gen 1 command presented during sleep, freeze, or partial trapping, and emits `recharge` for a recharge lock. These commands do not have the advertised attack statistics. See the primary implementation of [Fight requests](https://github.com/smogon/pokemon-showdown/blob/master/sim/pokemon.ts#L1014-L1036) and [Recharge requests](https://github.com/smogon/pokemon-showdown/blob/master/sim/pokemon.ts#L899-L906).

The small fix in `stt/adapter.py` describes these two commands explicitly instead of rendering their placeholder combat statistics:

```text
  move:fight  continue the turn without selecting an attack (asleep, frozen, or partially trapped)
  move:recharge  recharge this turn
```

The action IDs, move objects, order generation, switch availability, and ordinary move descriptions are preserved. This corrects the adapter's representation of server commands; it adds no strategy advice and changes no harness rules or GUARDRAILS. Only `stt/adapter.py`, `tests/test_adapter.py`, and this report were edited.

Validation completed:

- `/Users/eko/dev/stt/.venv/bin/python -m unittest discover -s tests -v`: all three tests passed. They exercise real poke-env requests for Fight with sleep, freeze, and no major status; a trapped Recharge request; and real Psychic, Recover, and Struggle moves. They also verify that legal switch choices and outgoing commands survive unchanged. Before the fix, all three Fight subcases and the Recharge case failed on the bogus attack metadata; the real-move cases passed.
- `/Users/eko/dev/stt/.venv/bin/python -m stt.selftest`: `selftest: PASS`.
- `git diff --check`: passed.

To verify in a new run, inspect generation inputs containing `move:fight` or `move:recharge`: neither legal-action line should contain type, power, category, or accuracy statistics. Compare the corresponding reasons with the cited cases, looking for fewer claims that Fight is a damaging move, Struggle, or Sleep Talk, while checking that submitted commands remain legal.

The offline export omits prompts, raw replies, latency, and tool output. The exact old prompt above is a local reproduction, not a recovered trace. The data cannot prove which of the five invalid answers were parsing failures, or that this defect caused a particular loss. No new model games were run, so a win-rate improvement is not claimed.
