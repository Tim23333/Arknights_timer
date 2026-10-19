/** Compute the transitive enabled dependents; never enable a dependency implicitly. */
export function policyChanges(fields, id, layer, enabled) {
  const changes = {[id]: {[layer]: enabled}};
  if (layer !== 'collect' || enabled) return changes;
  let changed = true;
  while (changed) {
    changed = false;
    for (const field of fields) {
      if (changes[field.id] || !field.collect) continue;
      if ((field.dependencies || field.deps || []).some(dependency => changes[dependency])) {
        changes[field.id] = {collect: false};
        changed = true;
      }
    }
  }
  return changes;
}
