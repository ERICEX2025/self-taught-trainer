import { readFile } from "node:fs/promises"
import path from "node:path"

export const dynamic = "force-dynamic"

// Serves a saved Showdown replay (poke-env writes one HTML file per battle; it loads Showdown's own
// battle viewer). Only bare file names from the replays folder are allowed.
const DIRS = [path.join(/*turbopackIgnore: true*/ process.cwd(), "..", "replays"), path.join(/*turbopackIgnore: true*/ process.cwd(), "public", "replays")]

export async function GET(req) {
  const name = path.basename(new URL(req.url).searchParams.get("file") || "")
  if (!name.endsWith(".html")) return new Response("not found", { status: 404 })
  for (const dir of DIRS) {
    try {
      const html = await readFile(path.join(dir, name), "utf8")
      return new Response(html, { headers: { "content-type": "text/html; charset=utf-8" } })
    } catch {}
  }
  return new Response("not found", { status: 404 })
}
