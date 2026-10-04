"""Session-local entity identities and arbitrary JSON components."""
from collections.abc import Mapping
from threading import RLock
from copy import deepcopy

from ._data import clone, integer, name, readonly


class World:
    def __init__(self, lock=None):
        self._lock = lock or RLock()
        self._entities = {}
        self._aliases = {}
        self._next_id = 1
        self._versions = {}
        self._views = {}

    def create(self, definition_id, components, tags=(), alias=None):
        with self._lock:
            name(definition_id, "definition_id")
            if not isinstance(components, Mapping):
                raise ValueError("components must be an object")
            components = clone(components)
            if isinstance(tags, str):
                raise ValueError("tags must be a collection of strings")
            tags = sorted(set(name(tag, "tag") for tag in tags))
            if alias is not None:
                name(alias, "alias")
                if alias in self._aliases:
                    raise ValueError(f"Alias already exists: {alias}")
            entity_id = self._next_id
            self._next_id += 1
            self._entities[entity_id] = {"id": entity_id, "definition_id": definition_id,
                                         "tags": tags, "components": components}
            self._versions[entity_id] = 1
            if alias is not None:
                self._aliases[alias] = entity_id
            return entity_id

    def resolve(self, alias_or_id):
        with self._lock:
            if isinstance(alias_or_id, str):
                if alias_or_id not in self._aliases:
                    raise KeyError(f"Unknown entity alias: {alias_or_id}")
                return self._aliases[alias_or_id]
            integer(alias_or_id, "entity_id", 1)
            if alias_or_id not in self._entities:
                raise KeyError(f"Unknown entity ID: {alias_or_id}")
            return alias_or_id

    def get(self, entity_id):
        with self._lock:
            entity_id = self.resolve(entity_id)
            version = self._versions[entity_id]
            cached = self._views.get(entity_id)
            if cached is None or cached[0] != version:
                # Stored records already passed the JSON boundary. readonly()
                # recursively copies every container, so another JSON round
                # trip adds cost without increasing isolation.
                view = dict(self._entities[entity_id])
                view["version"] = version
                cached = (version, readonly(view))
                self._views[entity_id] = cached
            return cached[1]

    def version(self, entity_id):
        """Revision of an identity, including tombstones for deleted IDs."""
        with self._lock:
            if isinstance(entity_id, str):
                entity_id = self.resolve(entity_id)
            integer(entity_id, "entity ID", 1)
            if entity_id not in self._versions:
                raise KeyError(f"Unknown entity ID: {entity_id}")
            return self._versions[entity_id]

    def entities(self):
        with self._lock:
            return tuple(self.get(key) for key in sorted(self._entities))

    def component_view(self, entity_id, path, default=None):
        """Freeze only a requested component subtree under the same World lock.

        The returned value owns immutable children and never aliases mutable
        World data. Mapping-only traversal matches the domain context reader.
        Entity view identities and version counters are unchanged by this read.
        """
        with self._lock:
            entity_id = self.resolve(entity_id)
            value = self._entities[entity_id]["components"]
            for part in path:
                if not isinstance(value, Mapping) or part not in value:
                    return default
                value = value[part]
            return readonly(value)

    def set(self, entity_id, path, value):
        """Set a component field; parent paths must already exist."""
        with self._lock:
            if not isinstance(path, (list, tuple)) or not path:
                raise ValueError("set path must contain at least one component field")
            value = clone(value)
            entity_id = self.resolve(entity_id)
            node = self._entities[entity_id]["components"]
            for part in path[:-1]:
                node = self._child(node, part)
            last = path[-1]
            if isinstance(node, dict):
                name(last, "object path key")
                node[last] = value
            elif isinstance(node, list):
                integer(last, "list path index", 0)
                if last >= len(node):
                    raise IndexError(f"List path index out of range: {last}")
                node[last] = value
            else:
                raise ValueError("set parent must be an object or array")
            self._versions[entity_id] += 1
            self._views.pop(entity_id, None)

    @staticmethod
    def _child(node, part):
        if isinstance(node, dict):
            name(part, "object path key")
            return node[part]
        if isinstance(node, list):
            integer(part, "list path index", 0)
            return node[part]
        raise ValueError("path traverses a scalar component value")

    def delete(self, entity_id):
        with self._lock:
            entity_id = self.resolve(entity_id)
            del self._entities[entity_id]
            self._versions[entity_id] += 1
            self._views.pop(entity_id, None)
            self._aliases = {key: value for key, value in self._aliases.items() if value != entity_id}

    def _fork_validated(self):
        """Private detached stores; public JSON boundaries remain unchanged."""
        with self._lock:
            fork = World()
            # create(name) permits str subclasses; JSON formerly normalized
            # these metadata values. Never invoke their deepcopy overrides.
            entities = {}
            for key, value in self._entities.items():
                record = dict(value)
                record["definition_id"] = str.__str__(record["definition_id"])
                record["tags"] = sorted(set(str.__str__(tag) for tag in record["tags"]))
                entities[key] = record
            fork._entities = deepcopy(entities)
            fork._aliases = {str.__str__(key): value for key, value in self._aliases.items()}
            fork._next_id = self._next_id
            fork._versions = dict(self._versions)
            fork._validated_fork = True
            return fork

    def _adopt_validated(self, fork, *, preserve_views):
        """Transfer isolated fork ownership once, with no user-code callback."""
        if type(fork) is not World or fork is self or not getattr(fork, "_validated_fork", False):
            raise ValueError("Expected an unconsumed private validated World fork")
        with self._lock, fork._lock:
            views = {key: cached for key, cached in self._views.items()
                     if key in fork._entities and cached[0] == fork._versions[key]} if preserve_views else {}
            self._entities, self._aliases, self._next_id = fork._entities, fork._aliases, fork._next_id
            self._versions, self._views = fork._versions, views
            # A retained staged object can never mutate the newly published data.
            fork._entities, fork._aliases, fork._versions, fork._views = {}, {}, {}, {}
            fork._next_id, fork._validated_fork = 1, False

    def snapshot(self):
        with self._lock:
            return clone({"entities": [self._entities[key] for key in sorted(self._entities)],
                          "aliases": self._aliases, "next_id": self._next_id,
                          "versions": {str(key): self._versions[key] for key in sorted(self._versions)}})

    def restore(self, data):
        with self._lock:
            data = clone(data)
            if not isinstance(data, dict):
                raise ValueError("World checkpoint must be an object")
            entities = {}
            for item in data["entities"]:
                entity_id = integer(item["id"], "entity ID", 1)
                if entity_id in entities:
                    raise ValueError(f"Duplicate entity ID: {entity_id}")
                name(item["definition_id"], "definition_id")
                if not isinstance(item["components"], dict):
                    raise ValueError("components must be an object")
                if not isinstance(item["tags"], list):
                    raise ValueError("tags must be an array")
                item["tags"] = sorted(set(name(tag, "tag") for tag in item["tags"]))
                entities[entity_id] = item
            aliases = data["aliases"]
            if not isinstance(aliases, dict):
                raise ValueError("aliases must be an object")
            for alias, entity_id in aliases.items():
                name(alias, "alias")
                integer(entity_id, "alias entity ID", 1)
                if entity_id not in entities:
                    raise ValueError(f"Alias {alias} refers to absent entity {entity_id}")
            next_id = integer(data["next_id"], "next entity ID", 1)
            if entities and next_id <= max(entities):
                raise ValueError("next entity ID would reuse an existing ID")
            raw_versions = data.get("versions", {str(key): 1 for key in entities})
            if not isinstance(raw_versions, dict):
                raise ValueError("entity versions must be an object")
            versions = {}
            for key, revision in raw_versions.items():
                if not key.isdecimal() or str(int(key)) != key:
                    raise ValueError("entity version keys must be canonical positive IDs")
                entity_id = integer(int(key), "version entity ID", 1)
                if entity_id >= next_id:
                    raise ValueError("entity version refers to an unallocated identity")
                versions[entity_id] = integer(revision, "entity revision", 1)
            if not set(entities).issubset(versions):
                raise ValueError("entity checkpoint lacks a revision")
            self._entities, self._aliases, self._next_id = entities, aliases, next_id
            self._versions, self._views = versions, {}
