export type Kind = 'yuk' | 'yolovchi' | 'tezyurar'
export type Objective = 'umumiy' | 'ustuvorlik'

export interface Station { name: string; km: number; tracks: number; kind?: 'bekat' | 'obgon' }
export interface Train {
  id: string; kind: Kind; direction: number; speed: number
  release: number; weight: number; stops: Record<string, number>
}
export interface Disruption { segment: [number, number]; start: number; end: number }
export interface Row { bekat: number; kelish: number; ketish: number | null }
export type Schedule = Record<string, Row[]>

export interface Metrics {
  umumiy_kechikish_daq: number
  ortacha_kechikish_daq: number
  vaznli_kechikish: number
  tur_boyicha_ortacha: Partial<Record<Kind, number>>
  kutish_toxtashlari: number
  oxirgi_yetib_kelish_daq: number
}
export interface Deadlock { stuck_trains: string[]; at_station: Record<string, string>; vaqt: number }
export interface FifoResult {
  ok: boolean; deadlock: Deadlock | null; metrics: Metrics | null
  xatolar: string[] | null; schedule: Schedule
}
export interface AiResult {
  ok: boolean; status: string; hisob_soniya: number; time_limit?: number
  schedule: Schedule | null; metrics: Metrics | null; xatolar: string[] | null
}
export interface ScenarioData {
  nomi?: string; seed?: number; time_limit?: number; yaratilgan?: string
  scenario: { stations: Station[]; trains: Train[]; disruption: Disruption | null }
  fifo: FifoResult
  ai: Partial<Record<Objective, AiResult>>
  tiklanish?: { fifo: number | null; ai: Partial<Record<Objective, number | null>> }
  tez_hisob?: { soniya: number; status: string; umumiy_kechikish: number; xatolar: number }
}
export interface ObgonRank { peregon: string; k: number; uzunlik_km: number; tejaldi_daq: number; sezilarli: boolean; xatolar: number }
export interface ObgonVariant {
  peregon: string; k: number; punkt: string; tejaldi_daq: number
  scenario: { stations: Station[]; trains: Train[]; disruption: Disruption | null }
  oldin: Schedule; keyin: Schedule; metrics_oldin: Metrics; metrics_keyin: Metrics; xatolar: string[]
}
export interface ObgonStep { n: number; qoshildi: string; punktlar: string[]; qiymat: number; tejaldi_daq: number; xatolar: number }
export interface ObgonFull {
  scenario: { stations: Station[]; trains: Train[]; disruption: Disruption | null }
  oldin: Schedule; keyin: Schedule; metrics_oldin: Metrics; metrics_keyin: Metrics; xatolar: string[]; punktlar: number
}
export interface ObgonScenario {
  boshlangich: number; nazorat: number; shovqin: number; reyting: ObgonRank[]; variantlar: ObgonVariant[]
  bosqichlar?: ObgonStep[]; toliq?: ObgonFull
}
export interface ObgonData { hisob_s: number; seedlar: number[]; ssenariylar: Partial<Record<'oddiy' | 'avariya' | 'osish30', ObgonScenario>> }
