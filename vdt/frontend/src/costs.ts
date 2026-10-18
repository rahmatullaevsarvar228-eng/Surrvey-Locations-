// Taxminiy narxlar — ochiq manbalardan. Har biri ekranda "taxminiy" belgisi va manba bilan ko'rsatiladi;
// foydalanuvchi o'z qiymati bilan almashtiradi.
export const DEFAULTS = {
  sidingKm: 1.5,              // foydali uzunlik 850–1050 m + strelka zonalari
  trackPerKm: 1_000_000,      // O'zbekiston: 0,8 (Buxoro–Miskin) … 1,5 mln $/km (Samarqand–Buxoro modernizatsiyasi)
  switchesSignals: 1_500_000, // strelkalar, MPC/ESC, yer ishlari — manba yo'q, taxmin
  obgonLoops: 2,              // chap va o'ng aylanma yo'l
  obgonSwitches: 3_000_000,   // 4 ta strelka + signalizatsiya — manba yo'q, taxmin (2 strelka = 1,5 mln $ dan)
  idlePerHour: 300,           // poyezd-soat, $ (Lovett va boshq. 2015: 200–1000+ $)
  daysPerYear: 365,
}

export const SOURCES = [
  { t: 'Rail-construction cost per km in Uzbekistan: 0.8 M$ (Bukhara–Misken) – 11.4 M$ (Angren–Pap). E3S Web of Conferences (2023), ConMechHydro.',
    u: 'https://www.e3s-conferences.org/articles/e3sconf/pdf/2023/38/e3sconf_conmechydro23_03024.pdf' },
  { t: 'Samarkand–Bukhara high-speed upgrade: 259 km, ≈ $400 M (≈ 1.5 M$/km).', u: 'https://www.azernews.az/region/101413.html' },
  { t: 'ADB: Uzbekistan Railway Rehabilitation Project — $116.8 M, 320 km of track (≈ 0.37 M$/km, rehabilitation).',
    u: 'https://www.adb.org/documents/uzbekistan-railway-rehabilitation-project-and-railway-modernization-project-loans-1631-177' },
  { t: 'ARTC (Australia): new 1.5 km loops ≈ AUD 2.1 M each (2001); Nammoona loop AUD 5.3 M (2007); Aerosol Valley 2 km loop AUD 15.3 M (2009).',
    u: 'https://www.artc.com.au/2007/09/27/2007-10-10-154350/' },
  { t: 'Lovett et al. (2015), Determining Freight Train Delay Costs on Railroad Lines in North America: estimates $200 – $1,000+.',
    u: 'https://railtec.illinois.edu/wp/wp-content/uploads/2019/01/Lovett-et-al-2015-IAROR.pdf' },
]
