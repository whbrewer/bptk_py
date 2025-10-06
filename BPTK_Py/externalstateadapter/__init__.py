from .externalStateAdapter import ExternalStateAdapter, InstanceState
from .file_adapter import FileAdapter

# Optional imports - only import if dependencies are available
try:
    from .postgres_adapter import PostgresAdapter
except ImportError:
    class PostgresAdapter:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "PostgresAdapter requires 'psycopg' to be installed. "
                "Install it with: pip install psycopg[binary]"
            )

try:
    from .redis_adapter import RedisAdapter
except ImportError:
    class RedisAdapter:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "RedisAdapter requires 'redis' to be installed. "
                "Install it with: pip install redis"
            )