from abc import ABCMeta, abstractmethod
import datetime
from typing import Any

import jsonpickle
from ..util import statecompression
from dataclasses import dataclass
import os

@dataclass
class InstanceState:
    state: Any
    instance_id: str
    time: str
    timeout: Any
    step: Any

class ExternalStateAdapter(metaclass=ABCMeta):
    @abstractmethod
    def __init__(self, compress: bool):
        self.compress = compress

    def save_state(self, state: list[InstanceState]):
        if(self.compress):
            for cur_state in state:
                if(cur_state is not None and cur_state.state is not None):
                    cur_state.state["settings_log"] = statecompression.compress_settings(cur_state.state["settings_log"])
                    cur_state.state["results_log"] = statecompression.compress_results(cur_state.state["results_log"])
        
        return self._save_state(state)

    def save_instance(self, state: InstanceState):
        if(self.compress and state is not None and state.state is not None):
                state.state["settings_log"] = statecompression.compress_settings(state.state["settings_log"])
                state.state["results_log"] = statecompression.compress_results(state.state["results_log"])
        return self._save_instance(state)

    def load_state(self) -> list[InstanceState]:
        state = self._load_state()
        if(self.compress):
            for cur_state in state:
                if(cur_state is not None and cur_state.state is not None):
                    cur_state.state["settings_log"] = statecompression.decompress_settings(cur_state.state["settings_log"])
                    cur_state.state["results_log"] = statecompression.decompress_results(cur_state.state["results_log"])

        # Always restore numeric keys in scenario_cache (no compression, just JSON key conversion fix)
        for cur_state in state:
            if(cur_state is not None and cur_state.state is not None):
                if "scenario_cache" in cur_state.state:
                    cur_state.state["scenario_cache"] = self._restore_numeric_keys(cur_state.state["scenario_cache"])
        return state

    def load_instance(self, instance_uuid: str) -> InstanceState:
        state = self._load_instance(instance_uuid)
        if(self.compress and state is not None and state.state is not None):
            state.state["settings_log"] = statecompression.decompress_settings(state.state["settings_log"])
            state.state["results_log"] = statecompression.decompress_results(state.state["results_log"])

        # Always restore numeric keys in scenario_cache (no compression, just JSON key conversion fix)
        if(state is not None and state.state is not None):
            if "scenario_cache" in state.state:
                state.state["scenario_cache"] = self._restore_numeric_keys(state.state["scenario_cache"])

        return state

    def _restore_numeric_keys(self, data):
        """
        Recursively restore numeric keys that were converted to strings during JSON serialization.
        This handles the scenario_cache structure where floating point timesteps get converted to strings.
        """
        if not isinstance(data, dict):
            return data

        restored = {}
        for key, value in data.items():
            # Try to convert string keys back to numbers
            new_key = key
            if isinstance(key, str):
                # Try to convert to float first (for timesteps like "1.0", "2.5")
                try:
                    if '.' in key:
                        new_key = float(key)
                    else:
                        # Try integer conversion for whole numbers
                        new_key = int(key)
                except ValueError:
                    # If conversion fails, keep as string
                    new_key = key

            # Recursively process nested dictionaries
            if isinstance(value, dict):
                restored[new_key] = self._restore_numeric_keys(value)
            else:
                restored[new_key] = value

        return restored

    @abstractmethod
    def _save_state(self, state: list[InstanceState]):
        pass

    @abstractmethod
    def _save_instance(self, state: InstanceState):
        pass

    @abstractmethod
    def _load_state(self) -> list[InstanceState]:
        pass

    @abstractmethod
    def _load_instance(self, instance_uuid: str) -> InstanceState:
        pass

    @abstractmethod
    def delete_instance(self, instance_uuid: str):
        pass

