#!/usr/bin/env python3
"""
Example demonstrating how to use bptkServer with external state adapters
for stateless operation.

This example shows:
1. How to set up bptkServer with PostgreSQL adapter
2. How to set up bptkServer with Redis (Upstash) adapter
3. How to enable completely stateless operation
"""

import redis
import psycopg
from BPTK_Py.server.bptkServer import BptkServer
from BPTK_Py.externalstateadapter import PostgresAdapter, RedisAdapter
from BPTK_Py.bptk import bptk


def create_bptk_factory():
    """Factory function to create BPTK instances."""
    # Replace with your actual BPTK configuration
    bptk_instance = bptk()
    # Add your models, scenarios, etc. here
    return lambda: bptk_instance


def example_with_postgres():
    """Example using PostgreSQL adapter with stateless operation."""

    # Connect to PostgreSQL
    # You'll need to create the state table first (see postgres_adapter.py for SQL)
    postgres_conn = psycopg.connect(
        host="your-postgres-host",
        dbname="your-database",
        user="your-username",
        password="your-password"
    )

    # Create PostgreSQL adapter
    postgres_adapter = PostgresAdapter(postgres_conn, compress=True)

    # Create stateless server
    app = BptkServer(
        __name__,
        bptk_factory=create_bptk_factory(),
        external_state_adapter=postgres_adapter,
        externalize_state_completely=True  # This enables stateless operation
    )

    return app


def example_with_redis():
    """Example using Redis (Upstash) adapter with stateless operation."""

    # Connect to Redis (example with Upstash Redis)
    # For Upstash, use the Redis URL from your Upstash dashboard
    redis_client = redis.from_url(
        "rediss://your-upstash-redis-url",
        decode_responses=False  # Important: keep this as False for binary data
    )

    # Alternatively, connect to local Redis:
    # redis_client = redis.Redis(host='localhost', port=6379, db=0)

    # Create Redis adapter
    redis_adapter = RedisAdapter(
        redis_client=redis_client,
        compress=True,
        key_prefix="bptk:prod"  # Optional: use different prefix for different environments
    )

    # Create stateless server
    app = BptkServer(
        __name__,
        bptk_factory=create_bptk_factory(),
        external_state_adapter=redis_adapter,
        externalize_state_completely=True  # This enables stateless operation
    )

    return app


def example_with_state_persistence():
    """Example using Redis adapter WITHOUT stateless operation (instances persist)."""

    redis_client = redis.from_url("rediss://your-upstash-redis-url")
    redis_adapter = RedisAdapter(redis_client, compress=True)

    # Create server with state persistence (stateful operation)
    app = BptkServer(
        __name__,
        bptk_factory=create_bptk_factory(),
        external_state_adapter=redis_adapter,
        externalize_state_completely=False  # Instances remain in memory + external storage
    )

    return app


if __name__ == "__main__":
    # Example: Start server with Redis adapter in stateless mode
    app = example_with_redis()

    # For production, use a proper WSGI server like Gunicorn:
    # gunicorn -w 4 -b 0.0.0.0:8000 stateless_server_example:app

    # For development:
    app.run(host='0.0.0.0', port=8000, debug=True)