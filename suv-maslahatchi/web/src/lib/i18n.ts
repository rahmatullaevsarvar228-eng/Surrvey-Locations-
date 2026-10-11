import uz from "@i18n/uz.json";
import ru from "@i18n/ru.json";
import { createContext, useContext } from "react";

export type Lang = "uz" | "ru";
const DICTS: Record<Lang, unknown> = { uz, ru };

function lookup(dict: unknown, key: string): string | undefined {
  let node: unknown = dict;
  for (const part of key.split(".")) {
    if (node && typeof node === "object" && part in (node as Record<string, unknown>)) {
      node = (node as Record<string, unknown>)[part];
    } else return undefined;
  }
  return typeof node === "string" ? node : undefined;
}

export function translate(lang: Lang, key: string, vars?: Record<string, string | number>): string {
  const s = lookup(DICTS[lang], key) ?? lookup(DICTS.uz, key) ?? key;
  return vars ? s.replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? `{${k}}`)) : s;
}

export function list(lang: Lang, key: string): string[] {
  let node: unknown = DICTS[lang];
  for (const part of key.split(".")) node = (node as Record<string, unknown> | undefined)?.[part];
  return Array.isArray(node) ? (node as string[]) : [];
}

export const LangCtx = createContext<Lang>("uz");
export function useT() {
  const lang = useContext(LangCtx);
  return {
    lang,
    t: (key: string, vars?: Record<string, string | number>) => translate(lang, key, vars),
    list: (key: string) => list(lang, key),
  };
}
