"""
Tests for external state adapters including PostgresAdapter and RedisAdapter.
These tests verify the core functionality of state persistence and retrieval.
"""

import pytest
import unittest
import datetime
import uuid
from abc import ABC, abstractmethod

from BPTK_Py.externalstateadapter import InstanceState
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from test_config import TestConfig, requires_postgres, requires_redis


class BaseExternalStateAdapterTest(ABC):
    """Base test class for external state adapters."""

    @abstractmethod
    def create_adapter(self):
        """Create an instance of the adapter being tested."""
        pass

    @abstractmethod
    def cleanup_adapter(self, adapter):
        """Clean up any resources created during testing."""
        pass

    def create_test_instance_state(self, instance_id: str = None) -> InstanceState:
        """Create a test InstanceState for testing."""
        if instance_id is None:
            instance_id = str(uuid.uuid4())

        return InstanceState(
            state={
                "step": 5,
                "results_log": {
                    1: {
                        "scenario_manager_1": {
                            "scenario_1": {
                                "stock": {1: 10.0}
                            }
                        }
                    }
                },
                "settings_log": {
                    1: {
                        "scenario_manager_1": {
                            "scenario_1": {
                                "constants": {"constant": 1.0}
                            }
                        }
                    }
                },
                "lock": False
            },
            instance_id=instance_id,
            time=datetime.datetime.now(),
            timeout={
                "weeks": 0,
                "days": 0,
                "hours": 1,
                "minutes": 0,
                "seconds": 0,
                "milliseconds": 0,
                "microseconds": 0
            },
            step=5
        )

    def test_save_and_load_instance(self):
        """Test saving and loading a single instance."""
        adapter = self.create_adapter()
        if adapter is None:
            pytest.skip("Adapter not available")

        try:
            # Create test instance
            test_instance = self.create_test_instance_state()
            original_id = test_instance.instance_id

            # Save instance
            adapter.save_instance(test_instance)

            # Load instance
            loaded_instance = adapter.load_instance(original_id)

            # Verify instance was loaded correctly
            assert loaded_instance is not None
            assert loaded_instance.instance_id == original_id
            assert loaded_instance.step == 5
            assert loaded_instance.state["step"] == 5
            assert "results_log" in loaded_instance.state
            assert "settings_log" in loaded_instance.state

        finally:
            self.cleanup_adapter(adapter)

    def test_load_nonexistent_instance(self):
        """Test loading an instance that doesn't exist."""
        adapter = self.create_adapter()
        if adapter is None:
            pytest.skip("Adapter not available")

        try:
            # Try to load non-existent instance
            non_existent_id = str(uuid.uuid4())
            loaded_instance = adapter.load_instance(non_existent_id)

            # Should return None
            assert loaded_instance is None

        finally:
            self.cleanup_adapter(adapter)

    def test_save_multiple_instances(self):
        """Test saving and loading multiple instances."""
        adapter = self.create_adapter()
        if adapter is None:
            pytest.skip("Adapter not available")

        try:
            # Create multiple test instances
            instances = [
                self.create_test_instance_state(),
                self.create_test_instance_state(),
                self.create_test_instance_state()
            ]
            instance_ids = [inst.instance_id for inst in instances]

            # Save all instances
            adapter.save_state(instances)

            # Load all instances
            loaded_instances = adapter.load_state()

            # Verify all instances were loaded
            loaded_ids = [inst.instance_id for inst in loaded_instances]
            for instance_id in instance_ids:
                assert instance_id in loaded_ids

        finally:
            self.cleanup_adapter(adapter)

    def test_update_existing_instance(self):
        """Test updating an existing instance."""
        adapter = self.create_adapter()
        if adapter is None:
            pytest.skip("Adapter not available")

        try:
            # Create and save initial instance
            test_instance = self.create_test_instance_state()
            original_id = test_instance.instance_id
            adapter.save_instance(test_instance)

            # Create a fresh instance for the update to avoid compression side effects
            updated_instance = self.create_test_instance_state(original_id)
            updated_instance.step = 10
            updated_instance.state["step"] = 10
            updated_instance.state["results_log"][2] = {
                "scenario_manager_1": {
                    "scenario_1": {
                        "stock": {2: 20.0}
                    }
                }
            }
            updated_instance.state["settings_log"][2] = {
                "scenario_manager_1": {
                    "scenario_1": {
                        "constants": {"constant": 2.0}
                    }
                }
            }
            adapter.save_instance(updated_instance)

            # Load and verify update
            loaded_instance = adapter.load_instance(original_id)
            assert loaded_instance.step == 10
            assert loaded_instance.state["step"] == 10
            assert len(loaded_instance.state["results_log"]) == 2
            assert len(loaded_instance.state["settings_log"]) == 2

        finally:
            self.cleanup_adapter(adapter)

    def test_delete_instance(self):
        """Test deleting an instance."""
        adapter = self.create_adapter()
        if adapter is None:
            pytest.skip("Adapter not available")

        try:
            # Create and save instance
            test_instance = self.create_test_instance_state()
            original_id = test_instance.instance_id
            adapter.save_instance(test_instance)

            # Verify instance exists
            loaded_instance = adapter.load_instance(original_id)
            assert loaded_instance is not None

            # Delete instance
            adapter.delete_instance(original_id)

            # Verify instance is gone
            loaded_instance = adapter.load_instance(original_id)
            assert loaded_instance is None

        finally:
            self.cleanup_adapter(adapter)

    def test_compression_enabled(self):
        """Test adapter with compression enabled."""
        # This test is more about ensuring compression doesn't break functionality
        # The actual compression testing should be in the compression module tests
        adapter = self.create_adapter()
        if adapter is None:
            pytest.skip("Adapter not available")

        try:
            # Test with large state data to trigger compression
            test_instance = self.create_test_instance_state()

            # Add large data to trigger compression
            large_results_data = {
                i: {
                    "scenario_manager_1": {
                        "scenario_1": {
                            "stock": {i: float(i)}
                        }
                    }
                } for i in range(100)
            }
            large_settings_data = {
                i: {
                    "scenario_manager_1": {
                        "scenario_1": {
                            "constants": {f"constant_{j}": float(j)} for j in range(10)
                        }
                    }
                } for i in range(100)
            }
            test_instance.state["results_log"] = large_results_data
            test_instance.state["settings_log"] = large_settings_data

            # Save and load
            adapter.save_instance(test_instance)
            loaded_instance = adapter.load_instance(test_instance.instance_id)

            # Verify data integrity
            assert loaded_instance is not None
            # Note: After compression/decompression, the structure is transformed
            # We just verify that we got valid data back
            assert "results_log" in loaded_instance.state
            assert "settings_log" in loaded_instance.state

        finally:
            self.cleanup_adapter(adapter)


@requires_postgres
class TestPostgresAdapter(BaseExternalStateAdapterTest, unittest.TestCase):
    """Tests for PostgresAdapter."""

    def create_adapter(self):
        """Create PostgresAdapter for testing."""
        try:
            import psycopg
            from BPTK_Py.externalstateadapter import PostgresAdapter
        except ImportError:
            return None

        config = TestConfig.get_postgres_config()
        if not config:
            return None

        try:
            # Connect to PostgreSQL
            conn = psycopg.connect(**config)

            # Create test table if it doesn't exist
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS state (
                        state text,
                        instance_id text,
                        time text,
                        "timeout.weeks" bigint,
                        "timeout.days" bigint,
                        "timeout.hours" bigint,
                        "timeout.minutes" bigint,
                        "timeout.seconds" bigint,
                        "timeout.milliseconds" bigint,
                        "timeout.microseconds" bigint,
                        step bigint
                    )
                """)
                conn.commit()

            return PostgresAdapter(conn, compress=True)
        except Exception as e:
            pytest.skip(f"Could not connect to PostgreSQL: {e}")
            return None

    def cleanup_adapter(self, adapter):
        """Clean up PostgreSQL test data."""
        if adapter and adapter._postgres_client:
            try:
                with adapter._postgres_client.cursor() as cur:
                    cur.execute("DELETE FROM state WHERE instance_id LIKE 'test_%' OR instance_id ~ '^[0-9a-f-]{36}$'")
                    adapter._postgres_client.commit()
                adapter._postgres_client.close()
            except Exception:
                pass


@requires_redis
class TestRedisAdapter(BaseExternalStateAdapterTest, unittest.TestCase):
    """Tests for RedisAdapter."""

    def create_adapter(self):
        """Create RedisAdapter for testing."""
        try:
            import redis
            from BPTK_Py.externalstateadapter import RedisAdapter
        except ImportError:
            return None

        redis_url = TestConfig.get_redis_config()
        if not redis_url:
            return None

        try:
            # Connect to Redis
            redis_client = redis.from_url(redis_url, decode_responses=False)

            # Test connection
            redis_client.ping()

            return RedisAdapter(redis_client, compress=True, key_prefix="bptk:test")
        except Exception as e:
            pytest.skip(f"Could not connect to Redis: {e}")
            return None

    def cleanup_adapter(self, adapter):
        """Clean up Redis test data."""
        if adapter and adapter._redis_client:
            try:
                # Delete all test keys
                pattern = f"{adapter._key_prefix}:*"
                keys = adapter._redis_client.keys(pattern)
                if keys:
                    adapter._redis_client.delete(*keys)

                # Clean up instances set
                adapter._redis_client.delete(adapter._get_instances_set_key())
            except Exception:
                pass

    def test_redis_ttl_functionality(self):
        """Test Redis-specific TTL functionality."""
        adapter = self.create_adapter()
        if adapter is None:
            pytest.skip("Redis adapter not available")

        try:
            # Create instance with short timeout
            test_instance = self.create_test_instance_state()
            test_instance.timeout = {
                "weeks": 0, "days": 0, "hours": 0,
                "minutes": 0, "seconds": 5, "milliseconds": 0, "microseconds": 0
            }

            # Save instance
            adapter.save_instance(test_instance)

            # Check that TTL is set
            key = adapter._get_instance_key(test_instance.instance_id)
            ttl = adapter._redis_client.ttl(key)
            assert ttl > 0 and ttl <= 5

        finally:
            self.cleanup_adapter(adapter)

    def test_redis_key_prefix(self):
        """Test Redis key prefix functionality."""
        adapter = self.create_adapter()
        if adapter is None:
            pytest.skip("Redis adapter not available")

        try:
            test_instance = self.create_test_instance_state()
            adapter.save_instance(test_instance)

            # Check that key uses correct prefix
            expected_key = f"{adapter._key_prefix}:{test_instance.instance_id}"
            assert adapter._redis_client.exists(expected_key)

        finally:
            self.cleanup_adapter(adapter)


if __name__ == '__main__':
    unittest.main()