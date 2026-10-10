import type { InvestmentData, ScenarioData } from './types'

export type PresetName = 'oddiy' | 'avariya' | 'osish30'
export const PRESETS: PresetName[] = ['oddiy', 'avariya', 'osish30']

// Avval API'dan, bo'lmasa statik keshdan (cache/*.json) — internetsiz ishlaydi.
async function getJson<T>(api: string, file: string): Promise<T> {
  try {
    const r = await fetch(api)
    if (r.ok) return (await r.json()) as T
  } catch { /* API ishlamayapti — statik kesh */ }
  const r = await fetch(file)
  if (!r.ok) throw new Error(`${file}: ${r.status}`)
  return (await r.json()) as T
}

const cache = new Map<string, Promise<ScenarioData>>()
export function loadScenario(name: PresetName): Promise<ScenarioData> {
  if (!cache.has(name)) {
    const p = getJson<ScenarioData>(`api/scenarios/${name}`, `cache/${name}.json`)
    p.catch(() => cache.delete(name))
    cache.set(name, p)
  }
  return cache.get(name)!
}

export function loadInvestment(): Promise<InvestmentData> {
  return getJson<InvestmentData>('api/investment', 'cache/investment.json')
}

export async function solve(body: unknown): Promise<ScenarioData> {
  const r = await fetch('api/solve', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`)
  return (await r.json()) as ScenarioData
}

export const KIND_COLOR: Record<string, string> = {
  yuk: '#a0703a', yolovchi: '#2f6fde', tezyurar: '#d6336c',
}

export function hhmm(min: number): string {
  const m = Math.round(min)
  const h = Math.floor(m / 60)
  return `${String(h).padStart(2, '0')}:${String(((m % 60) + 60) % 60).padStart(2, '0')}`
}

export function pct(base: number, val: number): number | null {
  if (!base) return null
  return ((val - base) / base) * 100
}
