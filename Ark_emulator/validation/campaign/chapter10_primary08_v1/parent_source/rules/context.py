"""Read-only provider data plus nested pure calculation services."""
from collections.abc import Mapping

from ark_sim.contracts.models import freeze


class ProviderContext(Mapping):
    """Providers can calculate, but receive no world or state mutation service.

    Mapping entries are precisely the JSON data recorded in the trace. Service
    methods are deliberately outside that mapping and therefore never serialized.
    """
    __slots__ = ("_data", "_calculation_service", "_provider_service", "_frozen")

    def __init__(self, data, calculation_service, provider_service):
        object.__setattr__(self, "_data", freeze(data))
        object.__setattr__(self, "_calculation_service", calculation_service)
        object.__setattr__(self, "_provider_service", provider_service)
        object.__setattr__(self, "_frozen", True)

    def __setattr__(self, name, value):
        raise TypeError("ProviderContext is read-only")

    def __delattr__(self, name):
        raise TypeError("ProviderContext is read-only")

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)

    def calculate(self, calculation_id, inputs, rule_id=None):
        return self._calculation_service(calculation_id, inputs, rule_id)

    def invoke_provider(self, name, inputs, params=None):
        return self._provider_service(name, inputs, params)
