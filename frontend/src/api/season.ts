/**
 * Return the current NFL season year.
 *
 * The NFL season starts in September, so before September we still consider
 * the previous calendar year to be the "current" season (e.g. in March 2026
 * the active season is 2025).
 */
export function getCurrentNflSeason(): number {
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth(); // 0-indexed: 0=Jan, 8=Sep
  return month < 8 ? year - 1 : year;
}
