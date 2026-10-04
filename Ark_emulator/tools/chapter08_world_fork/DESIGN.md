# Validated internal World fork

The parent is frozen projectile-leaf core71d. Public create/set/restore and checkpoint snapshot keep their current finite JSON validation and detachment. Only internal transaction staging and atomic savepoints replace snapshot→restore with a private fork of already validated stores.

Components and restored extra fields are plain JSON containers. Public `name` validation also permits str subclasses in definition IDs, tags and alias keys. Before deepcopy, the private fork normalizes those metadata strings using the built-in str implementation, matching the former JSON roundtrip without invoking custom deepcopy hooks. Component values remain detached by the unchanged public clone boundary.

The fork owns all mutable entity, component, alias and revision containers. Immutable read views are not copied into staging. Adoption moves ownership, empties and consumes the fork, and preserves only unchanged cached views for commit. Rollback discards cached views, as the previous public restore did; Session still increments its derived-cache epoch.

Session holds its existing executor RLock for commit and all nested atomic scopes. Private forks have separate locks and are not published to callbacks. Scheduler, event append, random snapshots, exception handling, intent validation, time and traces are unchanged.

Required evidence: metadata-subclass hook not invoked; malformed public inputs remain rejected; no mutation sharing between fork, original, saved outer transaction and consumed stage; revision/order/cache behavior; nested failure with every store restored; multi-thread Session serialization; actual CP/replay and exact parent/candidate all-value comparison. Profiling is a bounded paired measurement, not a statistical performance guarantee. Full suite/base runs wait for a stable interface and root review.
