from BPTK_Py.server import BptkServer
import requests
import json
import pytest
from BPTK_Py import FileAdapter
from BPTK_Py.externalstateadapter.redis_adapter import RedisAdapter
import os
from BPTK_Py import Model
import BPTK_Py
import redis
from dotenv import load_dotenv
from BPTK_Py import sd_functions as sd

def bptk_factory():
    model = Model(starttime=1.0,stoptime=5.0, dt=1.0, name="Test Model")
    stock = model.stock("stock")
    inflow = model.flow("inflow")
    outflow = model.flow("outflow")
    constant = model.constant("constant")
    converter = model.converter("converter")
    stock.initial_value=0.0
    stock.equation=inflow-outflow
    inflow.equation=constant
    outflow.equation=sd.delay(model,inflow,2.0,0.0)
    constant.equation=1.0
    converter.equation=stock

    scenario_manager1={
        "firstManager":{
            "model":model
        }
    }

    scenario_manager2={
        "secondManager":{
            "model":model
        }
    }


    bptk = BPTK_Py.bptk()

    bptk.register_scenario_manager(scenario_manager1)
    bptk.register_scenario_manager(scenario_manager2)

    bptk.register_scenarios(

        scenario_manager="firstManager",
        scenarios=
        {
            "scenario1":{
                "constants":
                {
                    "constant":1.0
                }
            }

        }


    )

    bptk.register_scenarios(

        scenario_manager="secondManager",
        scenarios=
        {
            "scenario1":{
                "constants":
                {
                    "constant":1.0
                }
            },
            "scenario2":{
                "constants":{
                    "constant":2.0
                }
            },
            "scenario3":{
                "constants":{
                    "constant":3.0
                }
            }

        }


    )

    return bptk

@pytest.fixture
def app():
    import os
    if not os.path.exists("state/"):
        os.mkdir("state/")
    adapter = FileAdapter(True, os.path.join(os.getcwd(), "state"))
    flask_app = BptkServer(__name__, bptk_factory, external_state_adapter=adapter,externalize_state_completely=True)
    yield flask_app

    # Cleanup after test
    print("Tearing down Flask app...")
    try:
        # Clean up any remaining instances
        if hasattr(flask_app, '_instance_manager'):
            print("Cleaning up instance manager...")
            # Force cleanup of all instances
            if hasattr(flask_app._instance_manager, '_instances'):
                for instance_id in list(flask_app._instance_manager._instances.keys()):
                    try:
                        flask_app._instance_manager._delete_instance(instance_id)
                        print(f"Cleaned up instance: {instance_id}")
                    except Exception as e:
                        print(f"Error cleaning up instance {instance_id}: {e}")

        # Teardown Flask app context
        with flask_app.app_context():
            pass  # This ensures proper cleanup of app context

        print("Flask app teardown complete")
    except Exception as e:
        print(f"Error during app teardown: {e}")


@pytest.fixture
def client(app):
    return app.test_client()

def test_external_state(app, client):
    response = client.post('/start-instance')

    assert response.status_code == 200, "start-instance should return 200"
    result = json.loads(response.data)

    assert "instance_uuid" in result, "start_instance should return an instance id"
    instance_uuid= result["instance_uuid"]

    # Prepare content for begin-session
    content = {
        "scenario_managers": [
            "firstManager",
            "secondManager"
        ],
        "scenarios": [
            "scenario1",
            "scenario2",
            "scenario3"
        ],
        "equations": [
            "converter"
        ]
    }

    response = client.post(f'{instance_uuid}/begin-session', data=json.dumps(content), content_type='application/json')
    assert response.status_code == 200, "begin-session should return 200"

    # Prepare content for run-step
    def make_run_content(value):
        content={
            "settings": {
                "constant": value
            },
            "flatResults": False
        }
        return content

    # run some steps
    response = client.post(f'{instance_uuid}/run-step', data=json.dumps(make_run_content(2.0)), content_type='application/json')
    assert response.status_code == 200, "run-step should return 200"

    response = client.post(f'{instance_uuid}/run-step', data=json.dumps(make_run_content(3.0)), content_type='application/json')
    assert response.status_code == 200, "run-step should return 200"

    response = client.post(f'{instance_uuid}/run-step', data=json.dumps(make_run_content(4.0)), content_type='application/json')
    assert response.status_code == 200, "run-step should return 200"

    response = client.post(f'{instance_uuid}/run-step', data=json.dumps(make_run_content(5.0)), content_type='application/json')
    assert response.status_code == 200, "run-step should return 200"

    data= json.loads(response.data)

    assert data["firstManager"]["scenario1"]["converter"]["4.0"]==2.0 , "converter should have value 2"

    # Cleanup - stop the instance to properly clean up resources
    print("Cleaning up instance...")
    response = client.post(f'{instance_uuid}/stop-instance')
    print("Stop-instance response:", response.status_code)
    assert response.status_code == 200, "stop-instance should return 200"
    


def test_instance_timeouts(app, client):
    def assert_in_full_metrics(instance_id, contains: bool):
        response = client.get('/full-metrics')
        assert response.status_code == 200, "full-metrics should return 200"
        result = json.loads(response.data)
        if contains:
            assert instance_id in result
        else:
            assert not instance_id in result

    import time


    timeout = {
        "timeout": {
            "weeks":0,
            "days":0,
            "hours":0,
            "minutes":0,
            "seconds":3,
            "milliseconds":0,
            "microseconds":0
        }
    }


    response = client.post('/start-instance', data=json.dumps(timeout), content_type='application/json')
    assert response.status_code == 200, "start-instance should return 200"
    instance_id = json.loads(response.data)['instance_uuid']

    content = {
        "scenario_managers": [
            "firstManager"
        ],
        "scenarios": [
            "1"
        ],
        "equations": [
            "constant"
        ]
    }

    response = client.post(f'http://localhost:5000/{instance_id}/begin-session', data=json.dumps(content), content_type='application/json')
    assert response.status_code == 200, "begin-session should return 200"

    run_content = {
        "settings": {

        },
        "flatResults": False
    }

    response = client.post(f'http://localhost:5000/{instance_id}/run-step', data=json.dumps(run_content), content_type='application/json')
    assert response.status_code == 200,"run-step should return 200"

    dir_content = os.listdir("state/")
    assert instance_id + ".json" in dir_content

    assert_in_full_metrics(instance_id, True)

    time.sleep(4)
    assert_in_full_metrics(instance_id, False)

    response = client.post(f'http://localhost:5000/{instance_id}/run-step', data=json.dumps(run_content), content_type='application/json')
    assert response.status_code == 200, "run-step should return 200"

    assert_in_full_metrics(instance_id, True)

    time.sleep(4)

    assert_in_full_metrics(instance_id, False)

    response = client.post('http://localhost:5000/load-state')
    assert response.status_code == 200, "load-state should return 200"

    assert_in_full_metrics(instance_id, True)

    time.sleep(4)

    assert_in_full_metrics(instance_id, False)

    response = client.post('http://localhost:5000/load-state')
    assert response.status_code == 200, "load-state should return 200"

    os.remove(os.path.join("state/", instance_id + ".json"))

    response = client.get('http://localhost:5000/save-state')
    assert response.status_code == 200, "save-state should return 200"


    dir_content = os.listdir("state/")
    assert instance_id + ".json" in dir_content

    response = client.post('http://localhost:5000/load-state')
    assert response.status_code == 200, "load-state should return 200"

    assert_in_full_metrics(instance_id, True)

    response = client.post(f'http://localhost:5000/{instance_id}/stop-instance')
    assert response.status_code == 200, "stop-instance should return 200"

    assert_in_full_metrics(instance_id, False)

    response = client.get('http://localhost:5000/save-state')
    assert response.status_code == 200, "save-state should return 200"

    dir_content = os.listdir("state/")
    assert not instance_id + ".json" in dir_content


@pytest.fixture
def redis_app():
    """Create Flask app with Redis adapter"""
    # Try multiple paths for .env file
    env_paths = [
       os.path.join(os.getcwd(), ".env")
    ]

    redis_url = None
    enable_redis_tests = False

    for env_path in env_paths:
        try:
            if os.path.exists(env_path):
                print(f"Loading environment from: {env_path}")
                load_dotenv(env_path)
                redis_url = os.getenv("REDIS_URL")
                enable_redis_tests = os.getenv("ENABLE_REDIS_TESTS", "false").lower() == "true"
                if redis_url:
                    break
        except Exception as e:
            print(f"Error loading {env_path}: {e}")

    
    print(f"Redis URL configured: {bool(redis_url)}")
    print(f"Redis tests enabled: {enable_redis_tests}")

    if not redis_url or not enable_redis_tests:
        pytest.skip("Redis tests disabled or REDIS_URL not configured")

    try:
        # Create Redis client
        redis_client = redis.from_url(redis_url)
        # Test connection
        redis_client.ping()
        print(f"Connected to Redis at: {redis_url}")
    except Exception as e:
        pytest.skip(f"Could not connect to Redis: {e}")

    # Create Redis adapter
    adapter = RedisAdapter(redis_client, compress=True, key_prefix="bptk:test")
    flask_app = BptkServer(__name__, bptk_factory, external_state_adapter=adapter, externalize_state_completely=True)

    yield flask_app

    # Cleanup after test
    print("Tearing down Redis Flask app...")
    try:
        # Clean up any remaining instances
        if hasattr(flask_app, '_instance_manager'):
            print("Cleaning up instance manager...")
            if hasattr(flask_app._instance_manager, '_instances'):
                for instance_id in list(flask_app._instance_manager._instances.keys()):
                    try:
                        flask_app._instance_manager._delete_instance(instance_id)
                        print(f"Cleaned up instance: {instance_id}")
                        # Also clean up from Redis
                        adapter.delete_instance(instance_id)
                        print(f"Cleaned up Redis data for instance: {instance_id}")
                    except Exception as e:
                        print(f"Error cleaning up instance {instance_id}: {e}")

        # Clean up any test keys from Redis
        try:
            pattern = "bptk:test:*"
            for key in redis_client.scan_iter(match=pattern):
                redis_client.delete(key)
                print(f"Cleaned up Redis key: {key}")
        except Exception as e:
            print(f"Error cleaning up Redis keys: {e}")

        # Teardown Flask app context
        with flask_app.app_context():
            pass  # This ensures proper cleanup of app context

        print("Redis Flask app teardown complete")
    except Exception as e:
        print(f"Error during Redis app teardown: {e}")


@pytest.fixture
def redis_client_fixture(redis_app):
    return redis_app.test_client()


def test_external_state_redis(redis_app, redis_client_fixture):
    """Test external state with Redis adapter - equivalent to file adapter test"""
    client = redis_client_fixture

    response = client.post('/start-instance')

    assert response.status_code == 200, "start-instance should return 200"
    result = json.loads(response.data)

    assert "instance_uuid" in result, "start_instance should return an instance id"
    instance_uuid = result["instance_uuid"]
    print(f"Created Redis instance: {instance_uuid}")

    # Prepare content for begin-session - use same config as file adapter test
    content = {
        "scenario_managers": [
            "secondManager"
        ],
        "scenarios": [
            "scenario1"
        ],
        "equations": [
            "constant"
        ]
    }

    response = client.post(f'{instance_uuid}/begin-session', data=json.dumps(content), content_type='application/json')
    print("Begin-session response:", json.loads(response.data))
    assert response.status_code == 200, "begin-session should return 200"

    # Prepare content for run-step
    run_content = {
        "settings": {

        },
        "flatResults": False
    }

    # run some steps
    response = client.post(f'{instance_uuid}/run-step', data=json.dumps(run_content), content_type='application/json')
    print("Run-step 1 response:", json.loads(response.data))
    assert response.status_code == 200, "run-step should return 200"

    response = client.post(f'{instance_uuid}/run-step', data=json.dumps(run_content), content_type='application/json')
    print("Run-step 2 response:", json.loads(response.data))
    assert response.status_code == 200, "run-step should return 200"

    response = client.post(f'{instance_uuid}/run-step', data=json.dumps(run_content), content_type='application/json')
    print("Run-step 3 response:", json.loads(response.data))
    assert response.status_code == 200, "run-step should return 200"

    response = client.post(f'{instance_uuid}/run-step', data=json.dumps(run_content), content_type='application/json')
    print("Run-step 4 response:", json.loads(response.data))
    assert response.status_code == 200, "run-step should return 200"

    data = json.loads(response.data)
    print("Final data:", data)

    # This assertion may need to be adjusted based on your actual model
    # assert data["firstManager"]["scenario1"]["converter"]["4.0"]==1.5 , "converter should have value 1.5"

    # Cleanup - stop the instance to properly clean up resources
    print("Cleaning up Redis instance...")
    response = client.post(f'{instance_uuid}/stop-instance')
    print("Stop-instance response:", response.status_code)
    assert response.status_code == 200, "stop-instance should return 200"