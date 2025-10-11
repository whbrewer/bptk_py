from abc import ABCMeta, abstractmethod
import datetime
from typing import Any

import jsonpickle
from ..util import statecompression
from dataclasses import dataclass
import os
from ..logger import log

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
        log(f"[INFO] ExternalStateAdapter initialized with compression: {compress}")

  

    def save_instance(self, state: InstanceState):
        log(f"[INFO] Saving instance {state.instance_id if state else 'None'}")
        try:
            if(self.compress and state is not None and state.state is not None):
                log(f"[INFO] Compressing state for instance {state.instance_id}")
                state.state["settings_log"] = statecompression.compress_settings(state.state["settings_log"])
                state.state["results_log"] = statecompression.compress_results(state.state["results_log"])
                log(f"[INFO] State compression completed for instance {state.instance_id}")
            result = self._save_instance(state)
            log(f"[INFO] Instance {state.instance_id if state else 'None'} saved successfully")
            return result
        except Exception as e:
            log(f"[ERROR] Failed to save instance {state.instance_id if state else 'None'}: {str(e)}")
            raise


    def load_instance(self, instance_uuid: str) -> InstanceState:
        log(f"[INFO] Loading instance {instance_uuid}")
        try:
            state = self._load_instance(instance_uuid)

            if state is None:
                log(f"[WARN] No state found for instance {instance_uuid}")
                return state

            log(f"[INFO] State loaded for instance {instance_uuid}")

            if(self.compress and state.state is not None):
                log(f"[INFO] Decompressing state for instance {instance_uuid}")
                state.state["settings_log"] = statecompression.decompress_settings(state.state["settings_log"])
                state.state["results_log"] = statecompression.decompress_results(state.state["results_log"])
                log(f"[INFO] State decompression completed for instance {instance_uuid}")

            # Always restore numeric keys in scenario_cache (no compression, just JSON key conversion fix)
            if(state.state is not None):
                if "scenario_cache" in state.state:
                    log(f"[INFO] Restoring numeric keys in scenario_cache for instance {instance_uuid}")
                    state.state["scenario_cache"] = self._restore_numeric_keys(state.state["scenario_cache"])
                    log(f"[INFO] Numeric keys restored for instance {instance_uuid}")

            log(f"[INFO] Instance {instance_uuid} loaded successfully")
            return state
        except Exception as e:
            log(f"[ERROR] Failed to load instance {instance_uuid}: {str(e)}")
            raise

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
                        log(f"[INFO] Converted string key '{key}' to float {new_key}")
                    else:
                        # Try integer conversion for whole numbers
                        new_key = int(key)
                        log(f"[INFO] Converted string key '{key}' to int {new_key}")
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
    def _save_instance(self, state: InstanceState):
        pass

    @abstractmethod
    def _load_instance(self, instance_uuid: str) -> InstanceState:
        pass

    @abstractmethod
    def delete_instance(self, instance_uuid: str):
        pass

