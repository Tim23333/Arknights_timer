/**
 * Own the backend's selected-detail target across drawer replacements.
 * Requests are serialized, obsolete selections skipped, and every possibly
 * applied selection released before a different target is installed. A failed
 * HTTP response cannot prove the backend did not apply the command.
 */
export function createDetailSelection(send, onError = () => {}) {
  let active = null, confirmed = false, revision = 0, tail = Promise.resolve();
  return {
    replace(target) {
      const desired = target ? {kind:target.kind, id:target.id} : null;
      const requested = ++revision;
      tail = tail.then(async () => {
        if (requested !== revision) return;
        if (!active && !desired) return;
        if (confirmed && active?.kind === desired?.kind && active?.id === desired?.id) return;
        if (active) {
          // Retain ownership if cancellation fails so the next transition can
          // retry; never issue a new selection ahead of an unfinished release.
          await send({kind:active.kind, id:null});
          active = null;
          confirmed = false;
        }
        if (requested !== revision || !desired) return;
        active = desired;
        confirmed = false;
        await send(desired);
        confirmed = true;
      }).catch(onError);
      return tail;
    },
  };
}
