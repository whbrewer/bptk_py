import datetime
import jsonpickle
import os
from .externalStateAdapter import ExternalStateAdapter, InstanceState

from .externalStateAdapter import ExternalStateAdapter, InstanceState

class FileAdapter(ExternalStateAdapter):
    def __init__(self, compress: bool, path: str):
        super().__init__(compress)
        self.path = path

    def _save_state(self, instance_states: list[InstanceState]):
        for state in instance_states:
            self._save_instance(state)


    def _save_instance(self, state: InstanceState):
        data = {
            "data": {
                "state": jsonpickle.dumps(state.state),
                "instance_id": state.instance_id,
                "time": str(state.time),
                "timeout": state.timeout,
                "step": state.step
            }
        }

        f = open(os.path.join(self.path, str(state.instance_id) + ".json"), "w")
        f.write(jsonpickle.dumps(data))
        f.close()


    def _load_state(self) -> list[InstanceState]:
        instances = []
        instance_paths = os.listdir(self.path)

        for instance_uuid in instance_paths:
            instances.append(self._load_instance(instance_uuid.split(".")[0]))

        return instances

    def _load_instance(self, instance_uuid: str) -> InstanceState:
        try:
            f = open(os.path.join(self.path, str(instance_uuid) + ".json"), "r")
            instance_data = jsonpickle.loads(f.read())

            decoded_data = jsonpickle.loads(instance_data["data"]["state"])
            instance_id = instance_data["data"]["instance_id"]
            timeout = instance_data["data"]["timeout"]
            step = instance_data["data"]["step"]

            return InstanceState(decoded_data, instance_id, datetime.datetime.now(), timeout, step)
        except Exception as e:
            print("Error: " + str(e))
            return None

    def delete_instance(self, instance_uuid: str):
        try:
            os.remove(os.path.join(self.path, str(instance_uuid) + ".json"))
        except Exception as e:
            print("Error: " + str(e))