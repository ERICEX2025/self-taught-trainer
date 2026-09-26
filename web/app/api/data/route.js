import { readFile } from "node:fs/promises"
import path from "node:path"

export const dynamic = "force-dynamic"

// Locally, read the files the Python loop writes (one folder up) so the dashboard is live.
// When deployed, fall back to the snapshot in public/data.
const DIRS = [process.env.STT_DATA_DIR || path.join(/*turbopackIgnore: true*/ process.cwd(), ".."), path.join(/*turbopackIgnore: true*/ process.cwd(), "public", "data")]

async function load(name) {
  for (const dir of DIRS) {
    try {
      return JSON.parse(await readFile(path.join(dir, name), "utf8"))
    } catch {}
  }
  return null
}

export async function GET() {
  const [live, stats, feed] = await Promise.all(["live.json", "stats.json", "feed.json"].map(load))
  return Response.json({ live, stats, feed })
}
