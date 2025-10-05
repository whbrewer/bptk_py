import datetime
import jsonpickle
import redis
from .externalStateAdapter import ExternalStateAdapter, InstanceState


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

    def _get_instances_set_key(self) -> str:
        """Generate Redis key for the set of all instance UUIDs."""
        return f"{self._key_prefix}:instances"

    def _load_instance(self, instance_uuid: str) -> InstanceState:
        """Load a single instance from Redis."""
        key = self._get_instance_key(instance_uuid)
        data = self._redis_client.get(key)

        if data is None:
            return None

        try:
            instance_data = jsonpickle.loads(data)
            return InstanceState(
                state=jsonpickle.loads(instance_data["state"]),
                instance_id=instance_data["instance_id"],
                time=datetime.datetime.fromisoformat(instance_data["time"]),
                timeout=instance_data["timeout"],
                step=instance_data["step"]
            )
        except (KeyError, ValueError, TypeError) as e:
            print(f"Error loading instance {instance_uuid}: {e}")
            return None

    def _load_state(self) -> list[InstanceState]:
        """Load all instances from Redis."""
        instances = []
        instance_uuids = self._redis_client.smembers(self._get_instances_set_key())

        for instance_uuid in instance_uuids:
            instance_uuid_str = instance_uuid.decode('utf-8') if isinstance(instance_uuid, bytes) else instance_uuid
            instance_state = self._load_instance(instance_uuid_str)
            if instance_state is not None:
                instances.append(instance_state)

        return instances

    def delete_instance(self, instance_uuid: str):
        """Delete an instance from Redis."""
        key = self._get_instance_key(instance_uuid)
        instances_set_key = self._get_instances_set_key()

        # Use pipeline for atomic operations
        pipe = self._redis_client.pipeline()
        pipe.delete(key)
        pipe.srem(instances_set_key, instance_uuid)
        pipe.execute()

    def _save_instance(self, instance_state: InstanceState):
        """Save a single instance to Redis."""
        if instance_state is None or instance_state.instance_id is None:
            return

        try:
            # Prepare data for storage
            redis_data = {
                "state": jsonpickle.dumps(instance_state.state),
                "instance_id": instance_state.instance_id,
                "time": instance_state.time.isoformat(),
                "timeout": instance_state.timeout,
                "step": instance_state.step
            }

            key = self._get_instance_key(instance_state.instance_id)
            instances_set_key = self._get_instances_set_key()

            # Store data and add to instances set atomically
            pipe = self._redis_client.pipeline()
            pipe.set(key, jsonpickle.dumps(redis_data))
            pipe.sadd(instances_set_key, instance_state.instance_id)

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
                    pipe.expire(key, int(timeout_seconds))

            pipe.execute()

        except Exception as error:
            print(f"Error saving instance {instance_state.instance_id}: {error}")

    def _save_state(self, instance_states: list[InstanceState]):
        """Save multiple instances to Redis."""
        for instance_state in instance_states:
            self._save_instance(instance_state)