// A mode change always increments revision; checking both fields is deliberate
// defense-in-depth against a late callback crossing detached/semi/contact modes.
export function requestMatches(current, revision, mode) {
  return Boolean(current) && current.revision === revision && current.mode === mode;
}
