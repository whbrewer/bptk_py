import math

from BPTK_Py import Model
from BPTK_Py.modeling.simultaneousScheduler import SimultaneousScheduler

from .agents import (
    DistributionHub,
    EndUser,
    Monitor,
    ProcessingFacility,
    ProductionFacility,
    RegulatoryNode,
)


class RadioisotopeSupplyChain(Model):
    def __init__(self, starttime=0.0, stoptime=240.0, dt=1.0, name="radioisotope_supply_chain", scheduler=None, data_collector=None):
        scheduler = scheduler or SimultaneousScheduler()
        super().__init__(starttime=starttime, stoptime=stoptime, dt=dt, name=name, scheduler=scheduler, data_collector=data_collector)
        self.reset_state()

    def instantiate_model(self):
        self.register_agent_factory(
            "production_facility",
            lambda agent_id, model, properties: ProductionFacility(agent_id, model, properties),
        )
        self.register_agent_factory(
            "processing_facility",
            lambda agent_id, model, properties: ProcessingFacility(agent_id, model, properties),
        )
        self.register_agent_factory(
            "distribution_hub",
            lambda agent_id, model, properties: DistributionHub(agent_id, model, properties),
        )
        self.register_agent_factory(
            "end_user",
            lambda agent_id, model, properties: EndUser(agent_id, model, properties),
        )
        self.register_agent_factory(
            "regulatory_node",
            lambda agent_id, model, properties: RegulatoryNode(agent_id, model, properties),
        )
        self.register_agent_factory(
            "monitor",
            lambda agent_id, model, properties: Monitor(agent_id, model, properties),
        )

        self.set_property("half_life_hours", {"type": "Double", "value": 66.0})
        self.set_property("production_initial_inventory", {"type": "Double", "value": 200.0})
        self.set_property("processing_initial_inventory", {"type": "Double", "value": 100.0})
        self.set_property("distribution_initial_inventory", {"type": "Double", "value": 80.0})
        self.set_property("end_user_initial_inventory", {"type": "Double", "value": 60.0})
        self.set_property("decay_loss_weight", {"type": "Double", "value": 1.0})

    def configure(self, config):
        super().configure(config)
        self.reset_state()

    def reset_state(self):
        self.production_inventory = 0.0
        self.processing_inventory = 0.0
        self.distribution_inventory = 0.0
        self.end_user_inventory = 0.0
        self.backlog = 0.0
        self.decay_losses = 0.0
        self.total_demand = 0.0
        self.total_fulfilled = 0.0
        self.total_unfilled = 0.0
        self.service_level = 1.0

        self.processing_queue = []
        self.transport_queue = []
        self.delivery_queue = []

        self.processing_regulatory_delay = 0.0
        self.transport_regulatory_delay = 0.0
        self.requested_delivery = 0.0
        self.requested_distribution = 0.0
        self.requested_production = 0.0

    def begin_round(self, time, sim_round, step):
        if time <= self.starttime:
            self.production_inventory = self.production_initial_inventory
            self.processing_inventory = self.processing_initial_inventory
            self.distribution_inventory = self.distribution_initial_inventory
            self.end_user_inventory = self.end_user_initial_inventory
        self.requested_delivery = 0.0
        self.requested_distribution = 0.0
        self.requested_production = 0.0

    def end_round(self, time, sim_round, step):
        self._advance_queue(self.processing_queue, self._receive_processing)
        self._advance_queue(self.transport_queue, self._receive_transport)
        self._advance_queue(self.delivery_queue, self._receive_delivery)

        self._apply_decay()
        self._update_service_level()
        self._update_monitor()

    def enqueue_processing_batch(self, quantity, delay):
        if quantity <= 0.0:
            return
        self.processing_queue.append({"quantity": quantity, "remaining": delay})

    def enqueue_transport_batch(self, quantity, delay):
        if quantity <= 0.0:
            return
        self.transport_queue.append({"quantity": quantity, "remaining": delay})

    def enqueue_delivery_batch(self, quantity, delay):
        if quantity <= 0.0:
            return
        self.delivery_queue.append({"quantity": quantity, "remaining": delay})

    def pending_delivery_quantity(self):
        return sum(item["quantity"] for item in self.delivery_queue)

    def pending_transport_quantity(self):
        return sum(item["quantity"] for item in self.transport_queue)

    def _advance_queue(self, queue, receive_fn):
        if not queue:
            return
        completed = []
        for batch in queue:
            batch["remaining"] -= self.dt
            if batch["remaining"] <= 0.0:
                completed.append(batch)
        for batch in completed:
            queue.remove(batch)
            receive_fn(batch["quantity"])

    def _receive_processing(self, quantity):
        self.processing_inventory += quantity

    def _receive_transport(self, quantity):
        self.distribution_inventory += quantity

    def _receive_delivery(self, quantity):
        self.end_user_inventory += quantity

    def _apply_decay(self):
        decay_rate = math.log(2.0) / max(self.half_life_hours, 1e-6)
        for attr in [
            "production_inventory",
            "processing_inventory",
            "distribution_inventory",
            "end_user_inventory",
        ]:
            inventory = getattr(self, attr)
            decay = inventory * decay_rate * self.dt
            if decay > 0.0:
                setattr(self, attr, max(0.0, inventory - decay))
                self.decay_losses += decay * self.decay_loss_weight

    def _update_service_level(self):
        if self.total_demand > 0:
            self.service_level = self.total_fulfilled / self.total_demand
        else:
            self.service_level = 1.0

    def _update_monitor(self):
        monitor = self._get_monitor()
        if not monitor:
            return
        monitor.set_property_value("production_inventory", self.production_inventory)
        monitor.set_property_value("processing_inventory", self.processing_inventory)
        monitor.set_property_value("distribution_inventory", self.distribution_inventory)
        monitor.set_property_value("end_user_inventory", self.end_user_inventory)
        monitor.set_property_value("backlog", self.backlog)
        monitor.set_property_value("total_demand", self.total_demand)
        monitor.set_property_value("total_fulfilled", self.total_fulfilled)
        monitor.set_property_value("total_unfilled", self.total_unfilled)
        monitor.set_property_value("service_level", self.service_level)
        monitor.set_property_value("decay_losses", self.decay_losses)

    def _get_monitor(self):
        ids = self.agent_type_map.get("monitor", [])
        if not ids:
            return None
        return self.agent(ids[0])
