// A mode change always increments revision; checking both fields is deliberate
// defense-in-depth against a late worker callback crossing detached/contact modes.
export function requestMatches(current, revision, contact) {
  return Boolean(current) && current.revision === revision && current.contact === contact;
}
