import datetime
import jsonpickle
import os
from .externalStateAdapter import ExternalStateAdapter, InstanceState
from ..util import statecompression

class FileAdapter(ExternalStateAdapter):
    def __init__(self, compress: bool, path: str):
        super().__init__(compress)
        self.path = path

    def _is_already_compressed_results(self, results_log):
        """
        Check if results_log is already in compressed format.
        Compressed format: {scenario_manager: {scenario: {constant: [values]}}}
        Uncompressed format: {step: {scenario_manager: {scenario: {constant: value}}}}
        """
        if not isinstance(results_log, dict) or not results_log:
            return False

        # Check if the first level keys look like scenario managers (strings) rather than steps (floats/step strings)
        first_key = next(iter(results_log.keys()))
        if isinstance(first_key, str) and not (first_key.replace('.', '').isdigit()):
            # This looks like a scenario manager name, so probably compressed format
            # Double-check by looking at the structure
            try:
                first_sm = results_log[first_key]
                if isinstance(first_sm, dict):
                    first_scenario = next(iter(first_sm.values()))
                    if isinstance(first_scenario, dict):
                        first_constant = next(iter(first_scenario.values()))
                        # If the constant value is a list, it's likely compressed
                        return isinstance(first_constant, list)
            except (StopIteration, KeyError, AttributeError):
                pass

        return False

    def load_instance(self, instance_uuid: str) -> InstanceState:
        """
        Override the base class method to handle compression/decompression internally.
        The base class tries to decompress after we've already handled it.
        """
        print(f"[FileAdapter] load_instance called for {instance_uuid}")
        return self._load_instance(instance_uuid)

    def save_instance(self, state: InstanceState):
        """
        Override the base class method to handle compression internally.
        The base class tries to compress before we handle it.
        """
        print(f"[FileAdapter] save_instance called for {state.instance_id if state else 'None'}")
        return self._save_instance(state)

    def _save_state(self, instance_states: list[InstanceState]):
        print(f"[FileAdapter] _save_state called with {len(instance_states)} instances")
        for state in instance_states:
            self._save_instance(state)


    def _save_instance(self, state: InstanceState):
        print(f"[FileAdapter] _save_instance called for instance {state.instance_id if state else 'None'}")
        # Apply compression for settings_log and results_log (scenario_cache compression is disabled)
        if self.compress and state is not None and state.state is not None:
            # Create a copy to avoid modifying the original state
            state_copy = state.state.copy()
            if "settings_log" in state_copy:
                print(f"[FileAdapter] Compressing settings_log, type: {type(state_copy['settings_log'])}")
                try:
                    state_copy["settings_log"] = statecompression.compress_settings(state_copy["settings_log"])
                except Exception as e:
                    print(f"[FileAdapter] Error compressing settings_log: {e}")
                    # Keep original data if compression fails
            if "results_log" in state_copy:
                print(f"[FileAdapter] Compressing results_log, type: {type(state_copy['results_log'])}")
                print(f"[FileAdapter] Results_log structure sample: {str(state_copy['results_log'])[:200]}...")
                # Check if data is already in compressed format by looking at the structure
                results_log = state_copy["results_log"]
                if results_log and self._is_already_compressed_results(results_log):
                    print(f"[FileAdapter] Results_log appears to already be compressed, skipping compression")
                else:
                    try:
                        state_copy["results_log"] = statecompression.compress_results(state_copy["results_log"])
                        print(f"[FileAdapter] Successfully compressed results_log")
                    except Exception as e:
                        print(f"[FileAdapter] Error compressing results_log: {e}")
                        # Keep original data if compression fails
        else:
            state_copy = state.state

        data = {
            "data": {
                "state": jsonpickle.dumps(state_copy),
                "instance_id": state.instance_id,
                "time": state.time.isoformat() if isinstance(state.time, datetime.datetime) else str(state.time),
                "timeout": state.timeout,
                "step": state.step
            }
        }

        file_path = os.path.join(self.path, str(state.instance_id) + ".json")
        print(f"[FileAdapter] Saving instance {state.instance_id} to {file_path}")
        f = open(file_path, "w")
        f.write(jsonpickle.dumps(data))
        f.close()
        print(f"[FileAdapter] Successfully saved instance {state.instance_id}")


    def _load_state(self) -> list[InstanceState]:
        print(f"[FileAdapter] _load_state called, checking directory: {self.path}")
        instances = []
        instance_paths = os.listdir(self.path)
        print(f"[FileAdapter] Found files: {instance_paths}")

        for instance_uuid in instance_paths:
            if instance_uuid.endswith('.json'):
                uuid = instance_uuid.split(".")[0]
                print(f"[FileAdapter] Loading instance {uuid}")
                instance = self._load_instance(uuid)
                if instance:
                    instances.append(instance)
                    print(f"[FileAdapter] Successfully loaded instance {uuid}")
                else:
                    print(f"[FileAdapter] Failed to load instance {uuid}")

        print(f"[FileAdapter] _load_state returning {len(instances)} instances")
        return instances

    def _load_instance(self, instance_uuid: str) -> InstanceState:
        file_path = os.path.join(self.path, str(instance_uuid) + ".json")
        print(f"[FileAdapter] _load_instance called for {instance_uuid}, file: {file_path}")
        try:
            f = open(file_path, "r")
            instance_data = jsonpickle.loads(f.read())
            f.close()
            print(f"[FileAdapter] Successfully read data for instance {instance_uuid}")

            decoded_data = jsonpickle.loads(instance_data["data"]["state"])
            instance_id = instance_data["data"]["instance_id"]
            time_str = instance_data["data"]["time"]
            timeout = instance_data["data"]["timeout"]
            step = instance_data["data"]["step"]

            # Parse the time back from string
            try:
                if isinstance(time_str, str):
                    time = datetime.datetime.fromisoformat(time_str)
                else:
                    time = time_str
            except ValueError:
                # Fallback for old format or parsing issues
                time = datetime.datetime.now()

            # Apply decompression for settings_log and results_log (scenario_cache compression is disabled)
            if self.compress and decoded_data is not None:
                if "settings_log" in decoded_data:
                    try:
                        decoded_data["settings_log"] = statecompression.decompress_settings(decoded_data["settings_log"])
                        print(f"[FileAdapter] Successfully decompressed settings_log")
                    except Exception as e:
                        print(f"[FileAdapter] Error decompressing settings_log (keeping original): {e}")
                        # Keep original data if decompression fails
                if "results_log" in decoded_data:
                    results_log = decoded_data["results_log"]
                    if self._is_already_compressed_results(results_log):
                        try:
                            decoded_data["results_log"] = statecompression.decompress_results(decoded_data["results_log"])
                            print(f"[FileAdapter] Successfully decompressed results_log")
                        except Exception as e:
                            print(f"[FileAdapter] Error decompressing results_log (keeping original): {e}")
                            # Keep original data if decompression fails
                    else:
                        print(f"[FileAdapter] Results_log doesn't appear to be compressed, skipping decompression")

            result = InstanceState(decoded_data, instance_id, time, timeout, step)
            print(f"[FileAdapter] Successfully created InstanceState for {instance_uuid}")
            return result
        except Exception as e:
            print(f"[FileAdapter] Error loading instance {instance_uuid}: {str(e)}")
            return None

    def delete_instance(self, instance_uuid: str):
        file_path = os.path.join(self.path, str(instance_uuid) + ".json")
        print(f"[FileAdapter] delete_instance called for {instance_uuid}, file: {file_path}")
        try:
            os.remove(file_path)
            print(f"[FileAdapter] Successfully deleted instance {instance_uuid}")
        except Exception as e:
            print(f"[FileAdapter] Error deleting instance {instance_uuid}: {str(e)}")