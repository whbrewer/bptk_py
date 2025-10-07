import datetime

import jsonpickle
import psycopg
from .externalStateAdapter import ExternalStateAdapter, InstanceState

# Postgres Create Script:
#
# CREATE TABLE "state" (
#   "state" text,
#   "instance_id" text,
#   "time" text,
#   "timeout.weeks" bigint,
#   "timeout.days" bigint,
#   "timeout.hours" bigint,
#   "timeout.minutes" bigint,
#   "timeout.seconds" bigint,
#   "timeout.milliseconds" bigint,
#   "timeout.microseconds" bigint,
#   "step" bigint
# );


class PostgresAdapter(ExternalStateAdapter):
    def __init__(self, postgres_client, compress: bool):
        super().__init__(compress)
        self._postgres_client = postgres_client

    def _load_instance(self, instance_uuid: str) -> InstanceState:
        with self._postgres_client.cursor() as cur:
            cur.execute("SELECT * FROM state WHERE instance_id = %s", (instance_uuid,))
            res = cur.fetchone()

        return self._tuple_to_state(res)

    def _load_state(self) -> list[InstanceState]:
        with self._postgres_client.cursor() as cursor:
            cursor.execute(""" SELECT * FROM state LIMIT 1000000 """)
            instances = []
            while True:
                rows = cursor.fetchmany(5000)
                if not rows:
                    break

                for row in rows:
                    instances.append(self._tuple_to_state(row))

        return instances

    def delete_instance(self, instance_uuid: str):
        with self._postgres_client.cursor() as cur:
            cur.execute("DELETE FROM state WHERE instance_id = %s", (instance_uuid,))
            self._postgres_client.commit()
    
    def _save_instance(self, instance_state: InstanceState):
        try:
            with self._postgres_client.cursor() as cur:
                cur.execute("SELECT * FROM state WHERE instance_id = %s", (instance_state.instance_id,))

                postgres_data = {
                    "state": jsonpickle.dumps(instance_state.state) if instance_state.state is not None else None,
                    "instance_id": instance_state.instance_id,
                    "time": str(instance_state.time),
                    "timeout.weeks": instance_state.timeout["weeks"],
                    "timeout.days": instance_state.timeout["days"],
                    "timeout.hours": instance_state.timeout["hours"],
                    "timeout.minutes": instance_state.timeout["minutes"],
                    "timeout.seconds": instance_state.timeout["seconds"],
                    "timeout.milliseconds": instance_state.timeout["milliseconds"],
                    "timeout.microseconds": instance_state.timeout["microseconds"],
                    "step": instance_state.step
                }

                res = cur.fetchone()
                if res is None:
                    cur.execute(
                        "INSERT INTO state (state, instance_id, time, \"timeout.weeks\", \"timeout.days\", \"timeout.hours\", \"timeout.minutes\", \"timeout.seconds\", \"timeout.milliseconds\", \"timeout.microseconds\", step) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (postgres_data["state"], postgres_data["instance_id"], postgres_data["time"], postgres_data["timeout.weeks"], postgres_data["timeout.days"], postgres_data["timeout.hours"], postgres_data["timeout.minutes"], postgres_data["timeout.seconds"], postgres_data["timeout.milliseconds"], postgres_data["timeout.microseconds"], postgres_data["step"])
                    )
                    self._postgres_client.commit()
                elif res[10] != instance_state.step:
                    cur.execute("UPDATE state SET state = %s, time = %s, \"timeout.weeks\" = %s, \"timeout.days\" = %s, \"timeout.hours\" = %s, \"timeout.minutes\" = %s, \"timeout.seconds\" = %s, \"timeout.milliseconds\" = %s, \"timeout.microseconds\" = %s, step = %s WHERE instance_id = %s", (postgres_data["state"], postgres_data["time"], postgres_data["timeout.weeks"], postgres_data["timeout.days"], postgres_data["timeout.hours"], postgres_data["timeout.minutes"], postgres_data["timeout.seconds"], postgres_data["timeout.milliseconds"], postgres_data["timeout.microseconds"], postgres_data["step"], postgres_data["instance_id"]))
                    self._postgres_client.commit()

        except (Exception, psycopg.Error) as error:
            print(error)
    
    def _tuple_to_state(self, state_tuple: tuple) -> InstanceState:
        if state_tuple is None:
            return None

        return InstanceState(
            state=jsonpickle.loads(state_tuple[0]) if state_tuple[0] is not None else None,
            instance_id=state_tuple[1],
            time=datetime.datetime.strptime(state_tuple[2], "%Y-%m-%d %H:%M:%S.%f"),
            timeout = {
                "weeks": state_tuple[3],
                "days": state_tuple[4],
                "hours": state_tuple[5],
                "minutes":  state_tuple[6],
                "seconds": state_tuple[7],
                "milliseconds": state_tuple[8],
                "microseconds":state_tuple[9]
            },
            step=state_tuple[10]
        )

    def _save_state(self, instance_states: list[InstanceState]):
        try:
            for state in instance_states:
                with self._postgres_client.cursor() as cur:
                    cur.execute("SELECT * FROM state WHERE instance_id = %s", (state.instance_id,))

                    postgres_data = {
                        "state": jsonpickle.dumps(state.state) if state.state is not None else None,
                        "instance_id": state.instance_id,
                        "time": str(state.time),
                        "timeout.weeks": state.timeout["weeks"],
                        "timeout.days": state.timeout["days"],
                        "timeout.hours": state.timeout["hours"],
                        "timeout.minutes": state.timeout["minutes"],
                        "timeout.seconds": state.timeout["seconds"],
                        "timeout.milliseconds": state.timeout["milliseconds"],
                        "timeout.microseconds": state.timeout["microseconds"],
                        "step": state.step
                    }

                    res = cur.fetchone()
                    if res is None:
                        cur.execute(
                            "INSERT INTO state (state, instance_id, time, \"timeout.weeks\", \"timeout.days\", \"timeout.hours\", \"timeout.minutes\", \"timeout.seconds\", \"timeout.milliseconds\", \"timeout.microseconds\", step) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (postgres_data["state"], postgres_data["instance_id"], postgres_data["time"], postgres_data["timeout.weeks"], postgres_data["timeout.days"], postgres_data["timeout.hours"], postgres_data["timeout.minutes"], postgres_data["timeout.seconds"], postgres_data["timeout.milliseconds"], postgres_data["timeout.microseconds"], postgres_data["step"])
                        )
                        self._postgres_client.commit()
                    elif res[10] != state.step:
                        cur.execute("UPDATE state SET state = %s, time = %s, \"timeout.weeks\" = %s, \"timeout.days\" = %s, \"timeout.hours\" = %s, \"timeout.minutes\" = %s, \"timeout.seconds\" = %s, \"timeout.milliseconds\" = %s, \"timeout.microseconds\" = %s, step = %s WHERE instance_id = %s", (postgres_data["state"], postgres_data["time"], postgres_data["timeout.weeks"], postgres_data["timeout.days"], postgres_data["timeout.hours"], postgres_data["timeout.minutes"], postgres_data["timeout.seconds"], postgres_data["timeout.milliseconds"], postgres_data["timeout.microseconds"], postgres_data["step"], postgres_data["instance_id"]))
                        self._postgres_client.commit()
        except (Exception, psycopg.Error) as error:
            print(error)
            