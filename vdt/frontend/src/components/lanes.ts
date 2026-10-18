import type { Schedule, Station, Train } from '../types'

// Obgon uchastkasida yo'l tanlash. lane: 0 — asosiy, -1 — yuqori (chap), +1 — pastki (o'ng) aylanma yo'l.
export interface Passage { id: string; enter: number; exit: number; lane: number }

// Har bir uchastka (jl indeksi) bo'yicha o'tishlar va yo'l tanlash.
// Yolg'iz o'tgan poyezd — asosiy yo'lda. Bir vaqtda bir nechta bo'lsa: birinchi kirgani (sekin yoki
// uchrashuvga birinchi kelgani) o'z yo'nalishiga nisbatan o'ng aylanma yo'lga chiqadi, keyingisi asosiy
// yo'ldan o'tadi, uchinchisi — chap aylanma yo'ldan.
export function insertPassages(stations: Station[], trains: Train[], sched: Schedule): Map<number, Passage[]> {
  const out = new Map<number, Passage[]>()
  const dir = new Map(trains.map(t => [t.id, t.direction]))
  stations.forEach((s, i) => { if (s.kind === 'jl') out.set(i, []) })
  for (const t of trains) {
    const rows = sched[t.id] ?? []
    for (let k = 0; k < rows.length - 1; k++) {
      const a = rows[k], b = rows[k + 1]
      const lo = Math.min(a.bekat, b.bekat)
      if (stations[lo]?.kind === 'jl' && stations[lo + 1]?.kind === 'jr' && a.ketish != null) {
        out.get(lo)!.push({ id: t.id, enter: a.ketish, exit: b.kelish, lane: 0 })
      }
    }
  }
  for (const list of out.values()) {
    list.sort((x, y) => x.enter - y.enter)
    for (const p of list) {
      const others = list.filter(q => q !== p && q.enter < p.exit && p.enter < q.exit)
      if (!others.length) continue
      const group = [p, ...others].sort((x, y) => x.enter - y.enter)
      const pos = group.indexOf(p)
      const right = dir.get(p.id) === 1 ? 1 : -1
      p.lane = pos === 0 ? right : pos === 1 ? 0 : -right
    }
  }
  return out
}

