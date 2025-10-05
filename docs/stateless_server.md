# Stateless BPTK Server

This document explains how to configure BPTK Server for stateless operation, enabling horizontal scaling and improved resilience.

## Overview

The BPTK Server can now operate in a completely stateless mode when configured with an external state adapter. In this mode:

- Instance state is stored externally (PostgreSQL, Redis, etc.)
- Instances are automatically deleted from memory after each request
- The server becomes horizontally scalable
- No session affinity is required for load balancing

## Configuration

### Basic Setup

```python
from BPTK_Py.server.bptkServer import BptkServer
from BPTK_Py.externalstateadapter import RedisAdapter
import redis

# Create external state adapter
redis_client = redis.from_url("rediss://your-redis-url")
adapter = RedisAdapter(redis_client, compress=True)

# Create stateless server
app = BptkServer(
    __name__,
    bptk_factory=your_bptk_factory,
    external_state_adapter=adapter,
    externalize_state_completely=True  # Enable stateless mode
)
```

### Parameters

- `externalize_state_completely`: Boolean flag that enables stateless operation
  - Only effective when `external_state_adapter` is provided
  - When `True`, instances are deleted from memory after each request
  - When `False`, instances persist in memory and are backed up to external storage

## Available Adapters

### PostgresAdapter

Stores state in a PostgreSQL database.

```python
import psycopg2
from BPTK_Py.externalstateadapter import PostgresAdapter

conn = psycopg2.connect(host="...", database="...", user="...", password="...")
adapter = PostgresAdapter(conn, compress=True)
```

**Database Schema:**
```sql
CREATE TABLE "state" (
  "state" text,
  "instance_id" text,
  "time" text,
  "timeout.weeks" bigint,
  "timeout.days" bigint,
  "timeout.hours" bigint,
  "timeout.minutes" bigint,
  "timeout.seconds" bigint,
  "timeout.milliseconds" bigint,
  "timeout.microseconds" bigint,
  "step" bigint
);
```

### RedisAdapter

Stores state in Redis. Optimized for Upstash Redis but works with any Redis instance.

```python
import redis
from BPTK_Py.externalstateadapter import RedisAdapter

redis_client = redis.from_url("rediss://your-upstash-url")
adapter = RedisAdapter(
    redis_client=redis_client,
    compress=True,
    key_prefix="bptk:prod"  # Optional
)
```

**Features:**
- Automatic TTL based on instance timeout
- Atomic operations using Redis pipelines
- Configurable key prefix for multi-tenant setups

## Affected Routes

When `externalize_state_completely=True`, instances are automatically deleted after these routes:

- `/<instance_uuid>/run-step`
- `/<instance_uuid>/run-steps`
- `/<instance_uuid>/stream-steps`
- `/<instance_uuid>/begin-session`
- `/<instance_uuid>/end-session`
- `/<instance_uuid>/session-results`
- `/<instance_uuid>/flat-session-results`
- `/<instance_uuid>/keep-alive`

## Deployment Considerations

### Load Balancing

With stateless operation, you can use any load balancing strategy:
- Round-robin
- Least connections
- Random

No session affinity is required.

### Scaling

- Scale horizontally by adding more server instances
- All instances can handle any request for any simulation instance
- No coordination between server instances is needed

### Error Handling

- If a server instance crashes, another instance can continue processing
- Instance state is preserved in external storage
- Automatic cleanup on exceptions ensures consistency

## Example: Upstash Redis Setup

1. Create an Upstash Redis database at https://upstash.com/
2. Get your Redis URL from the dashboard
3. Configure the adapter:

```python
import redis
from BPTK_Py.externalstateadapter import RedisAdapter

redis_client = redis.from_url(
    "rediss://your-upstash-url",
    decode_responses=False  # Important for binary data
)

adapter = RedisAdapter(redis_client, compress=True)
```

## Performance Notes

- State compression is enabled by default to reduce storage size
- Redis adapter uses pipelines for atomic operations
- TTL is automatically set based on instance timeout settings
- Consider Redis memory policies for production deployments