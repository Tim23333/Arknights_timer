// The sleeping page owns no telemetry connections or renderers.
export function standbyDestination(state) {
  return state.handoff ? '/?handoff='+encodeURIComponent(state.handoff) : null;
}

export async function getPresentationClient() {
  const key='timeline.presentation.client';
  let id;
  try { id=sessionStorage.getItem(key); } catch { /* Storage may be blocked. */ }
  id ||= crypto.randomUUID();
  if (navigator.locks) {
    // Duplicating a tab clones sessionStorage. Reserve the ID for this document
    // so a clone receives a new identity, while ordinary navigation retains it.
    id=await new Promise((resolve,reject)=>{
      const acquire = candidate => navigator.locks.request('timeline-page-'+candidate,{ifAvailable:true}, lock=>{
        if (!lock) return acquire(crypto.randomUUID());
        resolve(candidate);
        return new Promise(release=>window.addEventListener('pagehide',release,{once:true}));
      });
      acquire(id).catch(reject);
    });
  }
  try { sessionStorage.setItem(key,id); } catch { /* ID remains valid in memory. */ }
  return id;
}

export async function waitForPresentation(read, onError, delay = ms => new Promise(resolve => setTimeout(resolve, ms))) {
  // Retry serially before creating consumers. The caller's HTTP request has a
  // timeout; a temporary control-plane failure must not strand the worktable.
  for (;;) {
    try { return await read(); }
    catch (error) { onError(error); await delay(2000); }
  }
}

export function createPresentationWatch(read, sleep) {
  let stopped=false, busy=false;
  return {async check() {
    if (stopped || busy) return;
    busy=true;
    try {
      const state=await read();
      if (state.mode === 'desktop' || state.active === false) { stopped=true; sleep(); }
    } catch { /* Control-plane failures must not discard a working frontend. */ }
    finally { busy=false; }
  }};
}
