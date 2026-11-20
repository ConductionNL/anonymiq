import { twMerge } from "tailwind-merge";

export type ClassValue =
  | string
  | number
  | bigint
  | boolean
  | null
  | undefined
  | ClassValue[]
  | { [key: string]: unknown };

function toClassString(value: ClassValue): string {
  if (!value) return "";
  if (Array.isArray(value)) {
    return value.map(toClassString).filter(Boolean).join(" ");
  }
  if (typeof value === "object") {
    return Object.keys(value)
      .filter((key) => value[key])
      .join(" ");
  }
  return typeof value === "string" || typeof value === "number" || typeof value === "bigint"
    ? String(value)
    : "";
}

export function cn(...inputs: ClassValue[]) {
  return twMerge(toClassString(inputs));
}
