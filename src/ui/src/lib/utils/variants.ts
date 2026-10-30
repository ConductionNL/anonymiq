import { cn, type ClassValue } from "./cn";

type VariantMap = Record<string, Record<string, string>>;

export type VariantProps<T extends (props: never) => string> = Omit<
  NonNullable<Parameters<T>[0]>,
  "className"
>;

/**
 * Builds a class-name function from a base class and a map of variant
 * groups, falling back to the given defaults for an unset or null prop.
 */
export function createVariants<V extends VariantMap>(
  base: string,
  variants: V,
  defaults: { [K in keyof V]: keyof V[K] }
) {
  type Props = { [K in keyof V]?: keyof V[K] | null } & { className?: ClassValue };
  return (props: Props = {}): string => {
    const picked = (Object.keys(variants) as (keyof V)[]).map(
      (group) => variants[group][String(props[group] ?? defaults[group])]
    );
    return cn(base, picked, props.className);
  };
}
