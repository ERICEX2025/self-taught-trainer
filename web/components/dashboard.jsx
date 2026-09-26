"use client"

import { useEffect, useMemo, useState } from "react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
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
          An AI plays Pokémon. <span className="text-muted-foreground">Two more AIs make it better.</span>
        </h1>
        <p className="max-w-prose text-lg text-muted-foreground">
          A small model plays Gen 1 Pokémon battles. It is never retrained. Instead, other AIs rewrite the instructions and code around it, which is its <i>harness</i>.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          {["play games", "coach fixes strategy", "healer fixes code", "test on real opponents"].map((s, i) => (
            <span key={s} className="flex items-center gap-2">
              {i > 0 && <span className="text-muted-foreground">→</span>}
              <Badge variant="outline">{s}</Badge>
            </span>
          ))}
        </div>
      </header>

      <section className="grid gap-4">
        <Label>1 · The coach</Label>
        <h2 className="text-3xl font-semibold tracking-tight text-balance">It read its losses and taught itself the rules.</h2>
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
        <Label>2 · The healer</Label>
        <h2 className="text-3xl font-semibold tracking-tight text-balance">It found a bug in our own code that we never noticed.</h2>
        <p className="max-w-prose text-muted-foreground">
          A coding agent reads the logs of every game, looking for places where the code, not the strategy, is wrong. When a Pokémon is asleep or frozen, the game offers a “Fight” button, and our code described that button as an attack.
        </p>
        <blockquote className="border-l-2 pl-4 text-xl italic">
          “Fight can finish the weakened opposing Cloyster immediately.”
          <div className="mt-1 font-mono text-xs not-italic text-muted-foreground">the player, fooled, 194 times across 80 games</div>
        </blockquote>
        <div className="grid gap-3 sm:grid-cols-2">
          <Before label="What the player saw"><p className="font-mono">move:fight · type Normal, power 0, accuracy 0.01</p></Before>
          <After label="After the healer's fix"><p className="font-mono">move:fight · continue the turn without selecting an attack (asleep, frozen, or trapped)</p></After>
        </div>
        <p className="text-muted-foreground">It fixed 8 lines, wrote 3 tests, and had to pass a safety check it cannot edit before a human merged it.</p>
      </section>

      <section className="grid gap-4">
        <Label>3 · The real test</Label>
        <h2 className="text-3xl font-semibold tracking-tight text-balance">Then we tested it where it counts, and it barely moved.</h2>
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
        <p><b>What we learned:</b> an AI that improves itself only gets as good as its sparring partners. Our training bots were too easy. Next: train against strong reinforcement-learning agents.</p>
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

/* ---------------- Healer ---------------- */

function Healer({ heals }) {
  if (!heals?.length) return <p className="text-muted-foreground">No healer runs yet.</p>
  return (
    <div className="grid gap-4">
      <p className="max-w-prose text-muted-foreground">
        The healer is a coding agent (Codex). It reads the app's logs (MongoDB, and Langfuse and Sentry over MCP), finds one real bug in the code, and fixes it on its own git branch.
        A gate it cannot edit checks which files it touched, the locked guardrails and the tests. A human merges.
      </p>
      {heals.map((h) => (
        <Card key={h.branch}>
          <CardHeader>
            <CardTitle className="text-xl">{(h.summary || "").split(". ")[0].replace(/`/g, "")}.</CardTitle>
            <CardDescription className="flex flex-wrap items-center gap-2">
              <Badge>passed gate · {h.gate}</Badge>
              <span>branch {h.branch}</span>·<span>{h.seconds}s</span>·<span>changed {(h.changed || []).join(", ")}</span>
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="prose-sm max-w-none text-sm leading-relaxed [&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:font-mono [&_code]:text-xs [&_p]:my-3 [&_pre]:overflow-auto [&_pre]:rounded-md [&_pre]:bg-muted [&_pre]:p-3 [&_table]:my-3 [&_table]:w-full [&_td]:border-b [&_td]:p-2 [&_td]:align-top [&_th]:border-b [&_th]:p-2 [&_th]:text-left [&_ul]:list-disc [&_ul]:pl-5">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{h.report}</ReactMarkdown>
            </div>
          </CardContent>
        </Card>
      ))}
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

function Atlas({ atlas, feed, search, pipelines }) {
  const counts = atlas?.counts || {}
  return (
    <div className="grid gap-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {Object.entries(counts).map(([k, n]) => (
          <Card key={k}>
            <CardHeader><Label>{k}</Label></CardHeader>
            <CardContent className="text-3xl font-semibold tabular-nums">{n.toLocaleString()}</CardContent>
          </Card>
        ))}
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Memory · vector search</CardTitle>
            <CardDescription>index {atlas?.index} · {atlas?.index_status}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-2 text-sm">
            {search ? <>
              <p className="text-muted-foreground">The coach asked: “{search.query}”</p>
              {(search.hits || []).map((h, i) => (
                <div key={i} className="rounded-md bg-muted p-2"><span className="font-mono text-xs text-muted-foreground">{h.from_version} · rerank {h.rerank?.toFixed?.(2)}</span><br />{h.text}</div>
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

      <Tabs defaultValue="story">
        <TabsList variant="line" className="flex-wrap">
          <TabsTrigger value="story">Story</TabsTrigger>
          <TabsTrigger value="live">Live</TabsTrigger>
          <TabsTrigger value="harness">Harness</TabsTrigger>
          <TabsTrigger value="healer">Healer</TabsTrigger>
          <TabsTrigger value="ladder">Ladder</TabsTrigger>
          <TabsTrigger value="atlas">Atlas</TabsTrigger>
        </TabsList>
        {!data ? <p className="py-10 text-muted-foreground">Loading…</p> : <>
          <TabsContent value="story"><Story ladder={stats?.ladder} /></TabsContent>
          <TabsContent value="live" className="pt-4"><Live battle={live?.last_battle} /></TabsContent>
          <TabsContent value="harness" className="pt-4"><Harness key={run} detail={detail} /></TabsContent>
          <TabsContent value="healer" className="pt-4"><Healer heals={stats?.heals} /></TabsContent>
          <TabsContent value="ladder" className="pt-4"><Ladder ladder={stats?.ladder} recent={recent} /></TabsContent>
          <TabsContent value="atlas" className="pt-4"><Atlas atlas={stats?.atlas} feed={data?.feed} search={live?.last_search} pipelines={stats?.pipelines} /></TabsContent>
        </>}
      </Tabs>
    </main>
  )
}
