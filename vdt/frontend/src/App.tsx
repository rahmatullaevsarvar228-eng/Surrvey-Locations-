import { useEffect, useState } from 'react'
import { LangContext, DICTS, type Lang, type TKey } from './i18n'
import Corridor from './screens/Corridor'
import Compare from './screens/Compare'
import Emergency from './screens/Emergency'
import Invest from './screens/Invest'
import Econ from './screens/Econ'

const TABS: { id: string; key: TKey; el: () => React.ReactElement }[] = [
  { id: 'koridor', key: 'tab_corridor', el: () => <Corridor /> },
  { id: 'bugun-vs-ai', key: 'tab_compare', el: () => <Compare /> },
  { id: 'favqulodda', key: 'tab_emergency', el: () => <Emergency /> },
  { id: 'razyezd', key: 'tab_invest', el: () => <Invest /> },
  { id: 'samara', key: 'tab_econ', el: () => <Econ /> },
]

function readStore(k: string): string | null {
  try { return localStorage.getItem(k) } catch { return null }
}
function writeStore(k: string, v: string) {
  try { localStorage.setItem(k, v) } catch { /* ignore */ }
}

export default function App() {
  const [lang, setLang] = useState<Lang>(() => (readStore('vdt-lang') as Lang) || 'uz')
  const [tab, setTab] = useState(() => location.hash.slice(1) || 'bugun-vs-ai')
  const [demo, setDemo] = useState(() => readStore('vdt-demo') === '1')
  const d = DICTS[lang]
  useEffect(() => { writeStore('vdt-lang', lang); document.documentElement.lang = lang }, [lang])
  useEffect(() => { writeStore('vdt-demo', demo ? '1' : '0') }, [demo])
  useEffect(() => {
    const h = () => setTab(location.hash.slice(1) || 'bugun-vs-ai')
    window.addEventListener('hashchange', h)
    return () => window.removeEventListener('hashchange', h)
  }, [])
  const cur = TABS.find(x => x.id === tab) ?? TABS[1]
  return (
    <LangContext.Provider value={lang}>
      <div className={`app ${demo ? 'demo' : ''}`}>
        <header>
          <div className="brand">
            <div className="logo">═╪═</div>
            <div><div className="title">{d.app_title}</div><div className="sub">{d.app_sub}</div></div>
            <span className="synthetic">{d.synthetic}</span>
          </div>
          <div className="hdr-right">
            <label className="demo-toggle"><input type="checkbox" checked={demo} onChange={e => setDemo(e.target.checked)} /> {d.demo_mode}</label>
            <div className="langs">
              {(['uz', 'ru', 'en'] as Lang[]).map(l => (
                <button key={l} className={`btn chip ${lang === l ? 'on' : ''}`} onClick={() => setLang(l)}>{l.toUpperCase()}</button>
              ))}
            </div>
          </div>
        </header>
        <nav>
          {TABS.map(x => (
            <a key={x.id} href={`#${x.id}`} className={x.id === cur.id ? 'on' : ''}>{d[x.key]}</a>
          ))}
        </nav>
        <main key={cur.id}>{cur.el()}</main>
        <footer>
          <div>{d.authors}</div>
          <div className="muted">{d.synthetic_note}</div>
        </footer>
      </div>
    </LangContext.Provider>
  )
}
