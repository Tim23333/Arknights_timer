// Each page owns its connections and selected details, alongside the desktop.

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
