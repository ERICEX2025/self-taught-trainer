"use client"

import { useEffect, useMemo, useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

const pct = (x) => (x == null ? "–" : `${Math.round(x * 100)}%`)
const short = (id) => (id || "").split(".").pop()

function describe(change) {
  if (!change) return "started here"
  const v = change.value
  switch (change.kind) {
    case "add_rule": return `added a rule: “${v}”`
    case "remove_rule": return `removed a rule: “${v}”`
    case "edit_prompt": return "rewrote its instructions"
    case "write_tool": return `wrote a tool: ${v?.name}`
    case "edit_tool": return `revised its tool ${v?.name}`
    case "remove_tool": return `removed the tool ${v}`
    case "set_context": return "changed how many past moves it sees"
    default: return change.kind
  }
}

function Label({ children }) {
  return <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted-foreground">{children}</div>
}

/* ---------------- Story ---------------- */

function Before({ label, children }) {
  return (
    <Card className="bg-destructive/5 ring-destructive/20">
      <CardHeader><Label>{label}</Label></CardHeader>
      <CardContent className="text-sm">{children}</CardContent>
    </Card>
  )
}
function After({ label, children }) {
  return (
    <Card className="bg-emerald-500/5 ring-emerald-600/20">
      <CardHeader><Label>{label}</Label></CardHeader>
      <CardContent className="text-sm">{children}</CardContent>
    </Card>
  )
}

function Bar({ label, value, strong }) {
  return (
    <div className="grid grid-cols-[120px_1fr_48px] items-center gap-3 text-sm sm:grid-cols-[160px_1fr_56px]">
      <span>{label}</span>
      <Progress value={value} className={strong ? "" : "opacity-60"} />
      <span className="text-right font-mono tabular-nums">{value}%</span>
    </div>
  )
}

function Story({ ladder }) {
  const base = ladder?.["stt-base"], evo = ladder?.["stt-evolved"]
  const b = base ? Math.round((100 * base.wins) / base.games) : 13
  const e = evo ? Math.round((100 * evo.wins) / evo.games) : 14
  return (
    <div className="mx-auto grid max-w-3xl gap-16 py-8">
      <header className="grid gap-4">
        <h1 className="text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
          An AI plays Pokémon. <span className="text-muted-foreground">Another AI makes it better.</span>
        </h1>
        <p className="max-w-prose text-lg text-muted-foreground">
          A small model plays Gen 1 Pokémon battles. It is never retrained. Instead, a coach AI rewrites the instructions, rules and tools around it, which is its <i>harness</i>.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {["play games", "coach rewrites the harness", "keep it only if it wins more", "test on real opponents"].map((s, i) => (
            <span key={s} className="flex items-center gap-2">
              {i > 0 && <span className="text-muted-foreground">→</span>}
              <Badge variant="outline">{s}</Badge>
            </span>
          ))}
        </div>
      </header>

      <section className="grid gap-4">
        <Label>The player</Label>
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            ["GPT-5.4 mini", "a small, cheap model with reasoning turned off, so it answers fast"],
            ["Never retrained", "its weights never change; only the harness around it does"],
            ["One move per turn", "it sees the battle as text, gives a one-line reason, and picks a legal move"],
          ].map(([t, d]) => (
            <Card key={t} size="sm">
              <CardHeader><CardTitle>{t}</CardTitle><CardDescription>{d}</CardDescription></CardHeader>
            </Card>
          ))}
        </div>
      </section>

      <section className="grid gap-4">
        <Label>1 · The coach</Label>
        <h2 className="text-3xl font-semibold tracking-tight text-balance">It read its losses and taught itself the rules.</h2>
        <p className="max-w-prose">
          <b>Why Gen 1 is a good test:</b> the model already knows a lot about Pokémon, but mostly the modern games. Gen 1 (1996) has different rules: freeze never thaws on its own,
          Hyper Beam skips its recharge turn after a knockout, and critical hits depend on Speed. Its starting instructions don&apos;t mention Pokémon at all, so everything
          Gen 1-specific it knows at the end, it had to find in its own losses.
        </p>
        <p className="max-w-prose text-muted-foreground">
          After every round, a coach AI studies the lost games and suggests one change. A change is kept only if the player then wins more on fresh games.
          In Run 1, its win rate against the training bot went from <b className="text-foreground">52% to 71%</b>.
        </p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Before label="Where it started">
            <p className="font-mono">“You are playing a turn-based game. Your goal is to win.”</p>
            <p className="mt-2 text-muted-foreground">No rules. Nothing about Pokémon.</p>
          </Before>
          <After label="What it learned · Runs 1 and 2">
            <ul className="grid list-disc gap-1.5 pl-4">
              <li>A Hyper Beam that knocks out skips the recharge turn in Gen 1</li>
              <li>Freeze is permanent in Gen 1, so press the advantage</li>
              <li>A foe can only have one status at a time</li>
              <li>Wrote its own tool: a Victreebel endgame warning</li>
            </ul>
          </After>
        </div>
      </section>

      <section className="grid gap-4">
        <Label>2 · The real test</Label>
        <h2 className="text-3xl font-semibold tracking-tight text-balance">Then we tested it against opponents it had never seen.</h2>
        <p className="max-w-prose text-muted-foreground">We entered the PokéAgent Challenge (a NeurIPS 2025 benchmark) and played ranked games against opponents we never trained against.</p>
        <Card>
          <CardContent className="grid gap-4">
            <Bar label="vs training bot" value={71} strong />
            <Bar label="ladder · start" value={b} />
            <Bar label="ladder · evolved" value={e} />
            <p className="text-xs text-muted-foreground">
              Ladder: {base?.wins ?? 20} wins of {base?.games ?? 156} games (start), {evo?.wins ?? 11} of {evo?.games ?? 80} (evolved).
            </p>
          </CardContent>
        </Card>
        <p><b>What we learned:</b> the gains against our training bots didn&apos;t carry over to the real ladder yet. A self-improving AI only gets as good as its sparring partners, so the next step is tougher opponents.</p>
      </section>
    </div>
  )
}

/* ---------------- Live ---------------- */

function Live({ battle }) {
  const turns = battle?.turns || []
  const [sel, setSel] = useState(null)
  const t = turns[sel ?? Math.max(0, turns.length - 1)]
  if (!battle) return <p className="text-muted-foreground">No battle yet.</p>
  const replay = battle.replay ? `/api/replay?file=${encodeURIComponent(battle.replay.split("/").pop())}` : null
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
      <Card className="min-w-0">
        <CardHeader>
          <CardTitle>Watch the battle</CardTitle>
          <CardDescription>
            The real Pokémon Showdown viewer · {short(battle.version)} · {turns.length} turns ·{" "}
            <Badge variant={battle.won ? "default" : "destructive"}>{battle.won ? "won" : "lost"}</Badge>
          </CardDescription>
        </CardHeader>
        <CardContent>
          {replay ? <iframe src={replay} title="Pokémon Showdown replay" className="h-[620px] w-full rounded-md border bg-white" />
            : <p className="text-muted-foreground">No replay saved for this battle.</p>}
        </CardContent>
      </Card>
      <div className="grid min-w-0 content-start gap-4">
        <Card>
          <CardHeader>
            <CardTitle>The player's mind · turn {t?.turn}</CardTitle>
            <CardDescription>Why it chose, and what it saw</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3">
            <p className="text-lg">“{t?.reason}”</p>
            <p className="font-mono text-sm">→ {t?.action} {t?.invalid && <Badge variant="destructive">invalid</Badge>}</p>
            <details>
              <summary className="cursor-pointer text-sm text-muted-foreground">What it saw</summary>
              <pre className="mt-2 max-h-[240px] overflow-auto rounded-md bg-muted p-3 font-mono text-xs whitespace-pre-wrap">{t?.context}</pre>
            </details>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Every turn</CardTitle>
            <CardDescription>Click a turn to read the player's reason</CardDescription>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-[330px] pr-3">
              <div className="grid gap-1">
                {turns.map((x, i) => (
                  <button key={i} onClick={() => setSel(i)}
                    className={`grid grid-cols-[44px_1fr] gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted ${t === x ? "bg-muted" : ""}`}>
                    <span className="font-mono text-muted-foreground">T{x.turn}</span>
                    <span>
                      <b className="font-medium">{(x.action || "").replace(/^(move|switch):/, "")}</b>
                      <span className="text-muted-foreground"> · {x.me} {x.me_hp}% vs {x.opp} {x.opp_hp}%</span>
                    </span>
                  </button>
                ))}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

/* ---------------- Harness ---------------- */

function Harness({ detail }) {
  const kept = useMemo(() => (detail?.versions || []).filter((v) => ["baseline", "promoted"].includes(v.status)), [detail])
  const [selId, setSelId] = useState(null)
  const v = kept.find((x) => x._id === selId) || kept[kept.length - 1]
  if (!v) return <p className="text-muted-foreground">No versions for this run.</p>
  const tried = (detail.versions || []).length - kept.length
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        {kept.map((x, i) => (
          <span key={x._id} className="flex items-center gap-2">
            {i > 0 && <span className="text-muted-foreground">›</span>}
            <button onClick={() => setSelId(x._id)}>
              <Badge variant={x._id === v._id ? "default" : "outline"}>{short(x._id)}{x.started_from ? ` = ${x.started_from}` : ""} · {pct(x.score)}</Badge>
            </button>
          </span>
        ))}
        <span className="text-sm text-muted-foreground">kept versions · {tried} other ideas were tested and rejected</span>
      </div>
      <p className="text-muted-foreground">
        {v.parent ? <>The coach {describe(v.change)}. {v.change?.rationale && <>Its reason: {v.change.rationale}</>}</>
          : v.started_from ? <>Starting point: a copy of <b className="text-foreground">{v.started_from}</b>, the best version from an earlier run.</>
          : "Starting point: one generic sentence, no rules, no tools, nothing about Pokémon strategy."}
      </p>
      <div className="grid gap-3 md:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Instructions</CardTitle><CardDescription>editable by the coach</CardDescription></CardHeader>
          <CardContent className="font-mono text-sm">{v.system_prompt}</CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Guardrails</CardTitle><CardDescription>locked</CardDescription></CardHeader>
          <CardContent>
            <ul className="grid list-disc gap-1 pl-4 text-sm">
              <li>Answer with one legal action; illegal answers become a random legal move</li>
              <li>Never forfeit or stall</li>
            </ul>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Learned rules</CardTitle><CardDescription>{v.rules.length} rules</CardDescription></CardHeader>
          <CardContent>
            {v.rules.length ? <ul className="grid list-disc gap-1.5 pl-4 text-sm">{v.rules.map((r) => <li key={r}>{r}</li>)}</ul>
              : <p className="text-sm text-muted-foreground">None yet.</p>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Tools it wrote</CardTitle><CardDescription>Python, run in a sandbox</CardDescription></CardHeader>
          <CardContent className="grid gap-2">
            {(v.custom_tools || []).length ? v.custom_tools.map((tl) => (
              <details key={tl.name} className="text-sm">
                <summary className="cursor-pointer"><b className="font-mono">{tl.name}</b> · {tl.description}</summary>
                <pre className="mt-2 max-h-64 overflow-auto rounded-md bg-muted p-3 font-mono text-xs">{tl.code}</pre>
              </details>
            )) : <p className="text-sm text-muted-foreground">None yet.</p>}
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader><CardTitle>Every idea the coach tried</CardTitle><CardDescription>kept only if it won more on fresh games, twice</CardDescription></CardHeader>
        <CardContent>
          <Table>
            <TableHeader><TableRow><TableHead>Version</TableHead><TableHead>Change</TableHead><TableHead className="text-right">Win rate</TableHead><TableHead>Result</TableHead></TableRow></TableHeader>
            <TableBody>
              {(detail.versions || []).filter((x) => x.parent).map((x) => (
                <TableRow key={x._id}>
                  <TableCell className="font-mono">{short(x._id)}</TableCell>
                  <TableCell className="max-w-[520px] whitespace-normal">{describe(x.change)}</TableCell>
                  <TableCell className="text-right font-mono tabular-nums">{pct(x.score)}</TableCell>
                  <TableCell><Badge variant={x.status === "promoted" ? "default" : "secondary"}>{x.status === "promoted" ? "kept" : "rejected"}</Badge></TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

/* ---------------- Effects ---------------- */

function Effects({ discoveries, run }) {
  const all = discoveries || []
  const list = all.filter((d) => d.run === run)
  const shown = list.length ? list : all
  if (!shown.length) return <p className="text-muted-foreground">No kept changes yet.</p>
  return (
    <div className="grid gap-4">
      <p className="max-w-prose text-muted-foreground">
        Every change the coach kept, with the mistake it was meant to fix and what happened to the win rate. Each change had to win twice:
        once on 30 fresh games, then again in a head-to-head re-test against the version before it.
        {!list.length && <> (No kept changes in {run}; showing all runs.)</>}
      </p>
      {shown.map((d) => {
        const c = d.change || {}, rt = d.retest || {}, ex = d.examples || {}
        const before = rt.best_avg ?? d.first?.best, after = rt.top_avg ?? d.first?.top
        return (
          <Card key={d.version}>
            <CardHeader>
              <CardDescription className="flex flex-wrap items-center gap-2">
                <Badge variant="outline">{d.run} · gen {d.generation}</Badge>
                <span className="font-mono">{short(d.parent)} → {short(d.version)}</span>
              </CardDescription>
              <CardTitle className="text-lg leading-snug">
                {c.kind === "write_tool" || c.kind === "edit_tool" ? <>Wrote a tool: <span className="font-mono">{c.value?.name}</span></> : <>“{typeof c.value === "string" ? c.value : describe(c)}”</>}
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
              <div className="grid content-start gap-2">
                <Label>The mistake it fixed</Label>
                <p className="text-sm">{ex.plain || c.rationale}</p>
                {(ex.lines || []).length > 0 && (
                  <pre className="overflow-auto rounded-md bg-muted p-3 font-mono text-xs whitespace-pre-wrap">{ex.lines.join("\n")}</pre>
                )}
              </div>
              <div className="grid content-start gap-3">
                <Label>Win rate · before → after</Label>
                <div className="text-3xl font-semibold tabular-nums">{pct(before)} → {pct(after)}</div>
                <div className="grid gap-2 text-sm">
                  <div className="grid grid-cols-[64px_1fr_40px] items-center gap-2"><span className="text-muted-foreground">before</span><Progress value={Math.round((before || 0) * 100)} className="opacity-60" /><span className="text-right font-mono">{pct(before)}</span></div>
                  <div className="grid grid-cols-[64px_1fr_40px] items-center gap-2"><span>after</span><Progress value={Math.round((after || 0) * 100)} /><span className="text-right font-mono">{pct(after)}</span></div>
                </div>
                <p className="text-xs text-muted-foreground">Average of the first test and the head-to-head re-test, 30 fresh games each. Small samples, so a few points can be luck.</p>
              </div>
            </CardContent>
          </Card>
        )
      })}
    </div>
  )
}

/* ---------------- Ladder ---------------- */

function Ladder({ ladder, recent }) {
  const rows = [["stt-base", "v1 · the starting harness"], ["stt-evolved", "r1.v10 · best of Run 1"]]
  return (
    <div className="grid gap-4">
      <p className="max-w-prose text-muted-foreground">
        The PokéAgent Challenge (NeurIPS 2025) runs a public Gen 1 OU ladder. We played ranked games against the organizers' baseline agents, which we never trained against.
      </p>
      <div className="grid gap-3 md:grid-cols-2">
        {rows.map(([agent, what]) => {
          const d = ladder?.[agent]
          if (!d) return null
          return (
            <Card key={agent}>
              <CardHeader>
                <CardTitle className="font-mono">{agent}</CardTitle>
                <CardDescription>{what}</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-4">
                <div className="text-5xl font-semibold tabular-nums">{pct(d.wins / d.games)}</div>
                <p className="text-sm text-muted-foreground">{d.wins} wins of {d.games} ranked games</p>
                <Table>
                  <TableHeader><TableRow><TableHead>Opponent family</TableHead><TableHead className="text-right">Games</TableHead><TableHead className="text-right">Won</TableHead></TableRow></TableHeader>
                  <TableBody>
                    {Object.entries(d.families || {}).map(([f, x]) => (
                      <TableRow key={f}>
                        <TableCell className="font-mono">{f}</TableCell>
                        <TableCell className="text-right tabular-nums">{x.games}</TableCell>
                        <TableCell className="text-right tabular-nums">{pct(x.wins / x.games)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )
        })}
      </div>
      {recent?.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Recent ladder games</CardTitle></CardHeader>
          <CardContent className="flex flex-wrap gap-1.5">
            {recent.map((g) => (
              <Badge key={g.battle} variant={g.won ? "default" : "secondary"} title={`${g.opponent} · ${g.turns} turns`}>{g.won ? "W" : "L"} · {g.opponent}</Badge>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

/* ---------------- Atlas ---------------- */

const COLLECTIONS = [
  ["harness_versions", "one version of the harness", "_id (r2.v21), parent, rules[], custom_tools[{name, code}], system_prompt, change{kind, value, rationale}, score, status", "the version tree: what changed, and whether it was kept"],
  ["battles", "one game", "version, opponent, won, turns, log[{turn, action, reason, me, opp, me_hp, opp_hp}], replay", "what the coach reads; win rates come from aggregation pipelines"],
  ["reflections", "one coach decision", "run, generation, saw{n_battles, n_losses}, candidates[{change, score}], result{kept, retest}", "every idea tried, including the rejected ones"],
  ["lessons", "one sentence the coach learned", "text, from_version, archived, wealth (+ embedding)", "long-term memory, searched by meaning before each decision"],
]

const SEARCH_PIPELINE = `db.lessons.aggregate([
  { $vectorSearch: {
      index: "lessons_auto",        // Atlas embeds "text" itself (Voyage voyage-4)
      path: "text",
      query: "<summary of the latest lost games>",
      model: "voyage-4",
      numCandidates: 50, limit: 8,
      filter: { archived: false } } },
  { $project: { text: 1, from_version: 1,
                score: { $meta: "vectorSearchScore" } } }
])
// then Voyage rerank-2.5 picks the best 3 for the coach`

function Atlas({ atlas, feed, search, pipelines }) {
  const counts = atlas?.counts || {}
  return (
    <div className="grid gap-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {Object.entries(counts).map(([k, n]) => (
          <Card key={k} size="sm">
            <CardHeader><Label>{k}</Label></CardHeader>
            <CardContent className="text-3xl font-semibold tabular-nums">{n.toLocaleString()}</CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader><CardTitle>Data model</CardTitle><CardDescription>MongoDB Atlas · database <span className="font-mono">trainer</span> · everything the system learns is a document</CardDescription></CardHeader>
        <CardContent>
          <Table>
            <TableHeader><TableRow><TableHead>Collection</TableHead><TableHead>One document is</TableHead><TableHead>Key fields</TableHead><TableHead>Used for</TableHead></TableRow></TableHeader>
            <TableBody>
              {COLLECTIONS.map(([name, doc, fields, use]) => (
                <TableRow key={name}>
                  <TableCell className="font-mono align-top">{name}</TableCell>
                  <TableCell className="align-top whitespace-normal">{doc}</TableCell>
                  <TableCell className="max-w-[380px] align-top font-mono text-xs whitespace-normal">{fields}</TableCell>
                  <TableCell className="align-top whitespace-normal text-muted-foreground">{use}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>How vector search is used</CardTitle>
          <CardDescription>The coach's long-term memory · index {atlas?.index} · {atlas?.index_status}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 lg:grid-cols-2">
          <ol className="grid list-decimal content-start gap-2 pl-5 text-sm">
            <li>When a change is kept, its one-sentence lesson is saved to <span className="font-mono">lessons</span>.</li>
            <li>Atlas turns each lesson into a vector automatically (Automated Embeddings, Voyage <span className="font-mono">voyage-4</span>). We never call an embedding API ourselves.</li>
            <li>Before each coach decision, we search with a summary of the latest losses. Lessons with a similar <i>meaning</i> come back, even with different words.</li>
            <li>Voyage <span className="font-mono">rerank-2.5</span> picks the 3 most relevant, and they go into the coach's prompt.</li>
          </ol>
          <pre className="overflow-auto rounded-md bg-muted p-3 font-mono text-xs">{SEARCH_PIPELINE}</pre>
        </CardContent>
      </Card>

      <div className="grid gap-3 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>A real search</CardTitle>
            <CardDescription>What the coach asked, and the lessons that came back</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm">
            {search ? <>
              <pre className="max-h-32 overflow-auto rounded-md border p-2 font-mono text-xs whitespace-pre-wrap text-muted-foreground">{search.query}</pre>
              {(search.hits || []).map((h, i) => (
                <div key={i} className="rounded-md bg-muted p-2"><span className="font-mono text-xs text-muted-foreground">#{i + 1} · learned in {h.from_version} · similarity {h.score?.toFixed?.(2)} · rerank {h.rerank?.toFixed?.(2)}</span><br />{h.text}</div>
              ))}
            </> : <p className="text-muted-foreground">No search yet.</p>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Live writes · change stream</CardTitle><CardDescription>pushed by Atlas as they happen</CardDescription></CardHeader>
          <CardContent>
            <ScrollArea className="h-[320px] pr-3">
              <div className="grid gap-1 font-mono text-xs">
                {(feed || []).slice().reverse().map((e, i) => (
                  <div key={i} className="grid grid-cols-[64px_56px_1fr] gap-2"><span className="text-muted-foreground">{e.t}</span><span>{e.op}</span><span>{e.coll} · {e.what}</span></div>
                ))}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader><CardTitle>Analysis runs inside Atlas</CardTitle><CardDescription>aggregation pipelines behind the ladder and run tables</CardDescription></CardHeader>
        <CardContent><pre className="max-h-72 overflow-auto rounded-md bg-muted p-3 font-mono text-xs">{JSON.stringify(pipelines, null, 2)}</pre></CardContent>
      </Card>
    </div>
  )
}

/* ---------------- Page ---------------- */

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [run, setRun] = useState("r2")
  const [tab, setTab] = useState("story")

  useEffect(() => {
    let alive = true
    const load = () => fetch("/api/data", { cache: "no-store" }).then((r) => r.json()).then((d) => alive && setData(d)).catch(() => {})
    load()
    const id = setInterval(load, 5000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  const live = data?.live, stats = data?.stats
  const runs = Object.keys(stats?.run_detail || {}).filter((r) => r !== "test")
  const detail = stats?.run_detail?.[run]
  const best = detail?.versions?.find((v) => v._id === detail.best)
  const recent = [...(live?.ladders?.["stt-base"]?.recent || []), ...(live?.ladders?.["stt-evolved"]?.recent || [])].slice(0, 40)

  return (
    <main className="mx-auto grid max-w-[1440px] gap-6 px-4 py-6 sm:px-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Self-Taught Trainer</h1>
          <p className="font-mono text-xs text-muted-foreground">
            Gen 1 OU · player {live?.models?.play || "gpt-5.4-mini"} · coach {live?.models?.coach || "gpt-5.4"} · MongoDB Atlas
          </p>
        </div>
        {runs.length > 0 && (
          <div className="flex items-center gap-3 text-sm">
            <span className="text-muted-foreground">Run</span>
            <Select value={run} onValueChange={(v) => v && setRun(v)}>
              <SelectTrigger className="w-28"><SelectValue /></SelectTrigger>
              <SelectContent>{runs.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent>
            </Select>
            {best && <Badge variant="outline">best {short(best._id)} · {pct(best.score)}</Badge>}
          </div>
        )}
      </header>

      <Tabs value={tab} onValueChange={(v) => { setTab(v); window.scrollTo(0, 0) }}>
        <TabsList variant="line" className="flex-wrap">
          <TabsTrigger value="story">Story</TabsTrigger>
          <TabsTrigger value="live">Live</TabsTrigger>
          <TabsTrigger value="harness">Harness</TabsTrigger>
          <TabsTrigger value="effects">Effects</TabsTrigger>
          <TabsTrigger value="ladder">Ladder</TabsTrigger>
          <TabsTrigger value="atlas">Atlas</TabsTrigger>
        </TabsList>
        {!data ? <p className="py-10 text-muted-foreground">Loading…</p> : <>
          {tab === "story" && <TabsContent value="story"><Story ladder={stats?.ladder} /></TabsContent>}
          {tab === "live" && <TabsContent value="live" className="pt-4"><Live battle={live?.last_battle} /></TabsContent>}
          {tab === "harness" && <TabsContent value="harness" className="pt-4"><Harness key={run} detail={detail} /></TabsContent>}
          {tab === "effects" && <TabsContent value="effects" className="pt-4"><Effects discoveries={stats?.discoveries} run={run} /></TabsContent>}
          {tab === "ladder" && <TabsContent value="ladder" className="pt-4"><Ladder ladder={stats?.ladder} recent={recent} /></TabsContent>}
          {tab === "atlas" && <TabsContent value="atlas" className="pt-4"><Atlas atlas={stats?.atlas} feed={data?.feed} search={live?.last_search} pipelines={stats?.pipelines} /></TabsContent>}
        </>}
      </Tabs>
    </main>
  )
}
