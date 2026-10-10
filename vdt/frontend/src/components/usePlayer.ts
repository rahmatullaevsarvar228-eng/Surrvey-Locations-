import { useCallback, useEffect, useRef, useState } from 'react'

// Vaqt kursori: speed = model daqiqalari / real soniya.
export function usePlayer(range: [number, number]) {
  const [t, setT] = useState(range[0])
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(10)
  const raf = useRef(0)
  const last = useRef<number | null>(null)
  const tRef = useRef(t)
  tRef.current = t

  useEffect(() => { setT(range[0]); setPlaying(false) }, [range[0], range[1]]) // eslint-disable-line

  useEffect(() => {
    if (!playing) { last.current = null; return }
    const step = (now: number) => {
      if (last.current != null) {
        const nt = tRef.current + ((now - last.current) / 1000) * speed
        if (nt >= range[1]) { setT(range[1]); setPlaying(false); return }
        setT(nt)
      }
      last.current = now
      raf.current = requestAnimationFrame(step)
    }
    raf.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf.current)
  }, [playing, speed, range])

  const play = useCallback(() => {
    if (tRef.current >= range[1]) setT(range[0])
    setPlaying(true)
  }, [range])
  const pause = useCallback(() => setPlaying(false), [])
  const reset = useCallback(() => { setPlaying(false); setT(range[0]) }, [range])
  const seek = useCallback((v: number) => setT(Math.min(range[1], Math.max(range[0], v))), [range])
  return { t, playing, speed, setSpeed, play, pause, reset, seek }
}
