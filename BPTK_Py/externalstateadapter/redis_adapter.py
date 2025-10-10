import datetime
import jsonpickle
import jsonpickle.handlers
import redis
import numpy as np
from .externalStateAdapter import ExternalStateAdapter, InstanceState

# Try to configure ujson backend, but fall back gracefully if not available
try:
    import ujson
    jsonpickle.load_backend('ujson', 'ujson', ValueError)
    jsonpickle.set_preferred_backend('ujson')
    jsonpickle.set_encoder_options('ujson', ensure_ascii=False, sort_keys=True)
    jsonpickle.set_decoder_options('ujson', precise_float=True)
    print("jsonpickle configured to use ujson backend")
except (ImportError, AssertionError) as e:
    # Fall back to default JSON backend if ujson is not available
    print(f"ujson not available ({e}), using default JSON backend")
    pass

# Configure safer numpy serialization - convert to native Python types
# Use proper BaseHandler classes as per jsonpickle documentation

class NumpyFloatHandler(jsonpickle.handlers.BaseHandler):
    def flatten(self, obj, data):
        return float(obj)

class NumpyIntHandler(jsonpickle.handlers.BaseHandler):
    def flatten(self, obj, data):
        return int(obj)

class NumpyBoolHandler(jsonpickle.handlers.BaseHandler):
    def flatten(self, obj, data):
        return bool(obj)

class NumpyArrayHandler(jsonpickle.handlers.BaseHandler):
    def flatten(self, obj, data):
        return obj.tolist()

# Register handlers using proper jsonpickle handler classes
jsonpickle.handlers.register(np.float64, NumpyFloatHandler, base=True)
jsonpickle.handlers.register(np.float32, NumpyFloatHandler, base=True)
jsonpickle.handlers.register(np.int64, NumpyIntHandler, base=True)
jsonpickle.handlers.register(np.int32, NumpyIntHandler, base=True)
jsonpickle.handlers.register(np.int16, NumpyIntHandler, base=True)
jsonpickle.handlers.register(np.int8, NumpyIntHandler, base=True)
jsonpickle.handlers.register(np.uint64, NumpyIntHandler, base=True)
jsonpickle.handlers.register(np.uint32, NumpyIntHandler, base=True)
jsonpickle.handlers.register(np.uint16, NumpyIntHandler, base=True)
jsonpickle.handlers.register(np.uint8, NumpyIntHandler, base=True)
jsonpickle.handlers.register(np.bool_, NumpyBoolHandler, base=True)
jsonpickle.handlers.register(np.ndarray, NumpyArrayHandler, base=True)

class RedisAdapter(ExternalStateAdapter):
    """
    Redis adapter for storing BPTK instance state in Redis.
    Optimized for Upstash Redis but works with any Redis instance.
    """

    def __init__(self, redis_client: redis.Redis, compress: bool = True, key_prefix: str = "bptk:state"):
        """
        Initialize the Redis adapter.

        Args:
            redis_client: A configured Redis client (e.g., from redis.from_url())
            compress: Whether to compress state data (default: True)
            key_prefix: Prefix for Redis keys (default: "bptk:state")
        """
        super().__init__(compress)
        self._redis_client = redis_client
        self._key_prefix = key_prefix

    def _get_instance_key(self, instance_uuid: str) -> str:
        """Generate Redis key for an instance."""
        return f"{self._key_prefix}:{instance_uuid}"


    def _load_instance(self, instance_uuid: str) -> InstanceState:
        """Load a single instance from Redis."""
        key = self._get_instance_key(instance_uuid)
        data = self._redis_client.get(key)

        if data is None:
            return None

        try:
            instance_data = jsonpickle.decode(data)

            state = jsonpickle.decode(instance_data["state"]) if instance_data["state"] is not None else None
           
            result = InstanceState(
                state=state,
                instance_id=instance_data["instance_id"],
                time=datetime.datetime.fromisoformat(instance_data["time"]),
                timeout=instance_data["timeout"],
                step=instance_data["step"]
            )
         
            return result
        except (KeyError, ValueError, TypeError) as e:
            return None

  
    def load_instance(self, instance_uuid: str) -> InstanceState:
        """
        Override the base class method to handle compression/decompression internally.
        This prevents double decompression issues similar to FileAdapter.
        """
        state = self._load_instance(instance_uuid)

        # Apply scenario_cache numeric key restoration (no compression, just JSON key conversion fix)
        if(state is not None and state.state is not None):
            if "scenario_cache" in state.state:
                state.state["scenario_cache"] = self._restore_numeric_keys(state.state["scenario_cache"])

        return state

    def save_instance(self, state: InstanceState):
        """
        Override the base class method to handle compression internally.
        This prevents double compression issues similar to FileAdapter.
        """
        return self._save_instance(state)

    def delete_instance(self, instance_uuid: str):
        """Delete an instance from Redis."""
        key = self._get_instance_key(instance_uuid)
        self._redis_client.delete(key)

    def _save_instance(self, instance_state: InstanceState):
        """Save a single instance to Redis."""
        if instance_state is None or instance_state.instance_id is None:
            return

       
        try:
            # Prepare data for storage with make_refs=False to prevent py/id issues
            redis_data = {
                "state": jsonpickle.encode(instance_state.state, make_refs=False) if instance_state.state is not None else None,
                "instance_id": instance_state.instance_id,
                "time": instance_state.time.isoformat(),
                "timeout": instance_state.timeout,
                "step": instance_state.step
            }

            key = self._get_instance_key(instance_state.instance_id)

            # Store data with make_refs=False to prevent object reference issues
            self._redis_client.set(key, jsonpickle.encode(redis_data, make_refs=False))

            # Set TTL based on timeout if specified
            if instance_state.timeout:
                timeout_seconds = (
                    instance_state.timeout.get("weeks", 0) * 7 * 24 * 3600 +
                    instance_state.timeout.get("days", 0) * 24 * 3600 +
                    instance_state.timeout.get("hours", 0) * 3600 +
                    instance_state.timeout.get("minutes", 0) * 60 +
                    instance_state.timeout.get("seconds", 0) +
                    instance_state.timeout.get("milliseconds", 0) / 1000 +
                    instance_state.timeout.get("microseconds", 0) / 1000000
                )
                if timeout_seconds > 0:
                    self._redis_client.expire(key, int(timeout_seconds))

        except Exception as error:
            print(f"Error saving instance {instance_state.instance_id}: {error}")

  