/**
 * Sample TypeScript file for text-ingest tests.
 *
 * Contains: a named function, an interface, and an exported arrow function.
 * The chunker should emit one chunk per top-level declaration.
 */

export function greet(name: string): string {
  return `hello, ${name}`;
}

export interface User {
  id: string;
  email: string;
  createdAt: Date;
}

export const formatUser = (u: User): string => {
  return `${u.email} (${u.id})`;
};
