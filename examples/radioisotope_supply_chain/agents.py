import random

from BPTK_Py import Agent


class ProductionFacility(Agent):
    def initialize(self):
        self.agent_type = "production_facility"
        self.state = "operational"
        if "capacity" not in self.properties:
            self.set_property("capacity", {"type": "Double", "value": 100.0})
        if "variability" not in self.properties:
            self.set_property("variability", {"type": "Double", "value": 0.1})
        if "outage_probability" not in self.properties:
            self.set_property("outage_probability", {"type": "Double", "value": 0.0})
        if "outage_duration" not in self.properties:
            self.set_property("outage_duration", {"type": "Double", "value": 0.0})
        self.outage_remaining = 0.0

    def act(self, time, round_no, step_no):
        if self.outage_remaining > 0:
            self.outage_remaining = max(0.0, self.outage_remaining - self.model.dt)
            self.state = "outage"
            return

        if random.random() < self.outage_probability:
            self.outage_remaining = self.outage_duration
            self.state = "outage"
            return

        self.state = "operational"
        desired = max(self.model.requested_production, 0.0)
        base_output = min(self.capacity * self.model.dt, desired)
        variability = max(0.0, random.normalvariate(1.0, self.variability))
        produced = base_output * variability
        self.model.production_inventory += produced


class ProcessingFacility(Agent):
    def initialize(self):
        self.agent_type = "processing_facility"
        self.state = "available"
        if "throughput" not in self.properties:
            self.set_property("throughput", {"type": "Double", "value": 80.0})
        if "processing_delay" not in self.properties:
            self.set_property("processing_delay", {"type": "Double", "value": 4.0})
        if "processing_yield" not in self.properties:
            self.set_property("processing_yield", {"type": "Double", "value": 0.95})
        if "target_inventory" not in self.properties:
            self.set_property("target_inventory", {"type": "Double", "value": 200.0})

    def act(self, time, round_no, step_no):
        desired = max(
            self.model.requested_distribution + self.target_inventory - self.model.processing_inventory,
            0.0,
        )
        available = max(self.model.production_inventory, 0.0)
        processing_capacity = self.throughput * self.model.dt
        processed = min(available, processing_capacity, desired)

        if processed <= 0.0:
            self.state = "idle"
            return

        self.state = "processing"
        self.model.production_inventory -= processed

        delay = max(0.0, self.processing_delay + self.model.processing_regulatory_delay)
        effective_output = processed * self.processing_yield
        self.model.enqueue_processing_batch(effective_output, delay)

        self.model.requested_production = max(
            0.0,
            self.model.requested_distribution + self.target_inventory - self.model.production_inventory,
        )


class DistributionHub(Agent):
    def initialize(self):
        self.agent_type = "distribution_hub"
        self.state = "idle"
        if "shipping_capacity" not in self.properties:
            self.set_property("shipping_capacity", {"type": "Double", "value": 70.0})
        if "transport_delay" not in self.properties:
            self.set_property("transport_delay", {"type": "Double", "value": 6.0})
        if "target_inventory" not in self.properties:
            self.set_property("target_inventory", {"type": "Double", "value": 150.0})

    def act(self, time, round_no, step_no):
        requested_delivery = max(self.model.requested_delivery, 0.0)
        available = max(self.model.distribution_inventory, 0.0)
        shipping_capacity = self.shipping_capacity * self.model.dt
        delivery = min(available, shipping_capacity, requested_delivery)

        if delivery > 0.0:
            self.state = "shipping"
            self.model.distribution_inventory -= delivery
            delay = max(0.0, self.transport_delay + self.model.transport_regulatory_delay)
            self.model.enqueue_delivery_batch(delivery, delay)
        else:
            self.state = "idle"

        pending_transport = self.model.pending_transport_quantity()
        target = self.target_inventory + requested_delivery
        self.model.requested_distribution = max(
            0.0, target - (self.model.distribution_inventory + pending_transport)
        )

        if self.model.processing_inventory > 0.0:
            transport = min(
                self.model.processing_inventory,
                shipping_capacity,
                self.model.requested_distribution,
            )
            if transport > 0.0:
                self.model.processing_inventory -= transport
                delay = max(0.0, self.transport_delay + self.model.transport_regulatory_delay)
                self.model.enqueue_transport_batch(transport, delay)


class EndUser(Agent):
    def initialize(self):
        self.agent_type = "end_user"
        self.state = "active"
        if "demand_mean" not in self.properties:
            self.set_property("demand_mean", {"type": "Double", "value": 60.0})
        if "demand_stddev" not in self.properties:
            self.set_property("demand_stddev", {"type": "Double", "value": 10.0})
        if "target_inventory" not in self.properties:
            self.set_property("target_inventory", {"type": "Double", "value": 120.0})

    def act(self, time, round_no, step_no):
        backlog_clear = min(self.model.end_user_inventory, self.model.backlog)
        if backlog_clear > 0.0:
            self.model.end_user_inventory -= backlog_clear
            self.model.backlog -= backlog_clear

        demand = max(0.0, random.normalvariate(self.demand_mean, self.demand_stddev))
        fulfilled = min(self.model.end_user_inventory, demand)
        self.model.end_user_inventory -= fulfilled

        unfilled = demand - fulfilled
        self.model.backlog += unfilled

        self.model.total_demand += demand
        self.model.total_fulfilled += fulfilled
        self.model.total_unfilled += unfilled

        pending = self.model.pending_delivery_quantity()
        desired = max(0.0, self.target_inventory - (self.model.end_user_inventory + pending))
        self.model.requested_delivery = desired + self.model.backlog


class RegulatoryNode(Agent):
    def initialize(self):
        self.agent_type = "regulatory_node"
        self.state = "monitoring"
        if "processing_delay_mean" not in self.properties:
            self.set_property("processing_delay_mean", {"type": "Double", "value": 1.0})
        if "processing_delay_stddev" not in self.properties:
            self.set_property("processing_delay_stddev", {"type": "Double", "value": 0.2})
        if "transport_delay_mean" not in self.properties:
            self.set_property("transport_delay_mean", {"type": "Double", "value": 1.5})
        if "transport_delay_stddev" not in self.properties:
            self.set_property("transport_delay_stddev", {"type": "Double", "value": 0.3})
        if "hold_probability" not in self.properties:
            self.set_property("hold_probability", {"type": "Double", "value": 0.05})
        if "hold_delay" not in self.properties:
            self.set_property("hold_delay", {"type": "Double", "value": 4.0})

    def act(self, time, round_no, step_no):
        processing_delay = max(
            0.0, random.normalvariate(self.processing_delay_mean, self.processing_delay_stddev)
        )
        transport_delay = max(
            0.0, random.normalvariate(self.transport_delay_mean, self.transport_delay_stddev)
        )
        if random.random() < self.hold_probability:
            processing_delay += self.hold_delay
            transport_delay += self.hold_delay

        self.model.processing_regulatory_delay = processing_delay
        self.model.transport_regulatory_delay = transport_delay


class Monitor(Agent):
    def initialize(self):
        self.agent_type = "monitor"
        self.state = "reporting"
        for name in [
            "production_inventory",
            "processing_inventory",
            "distribution_inventory",
            "end_user_inventory",
            "backlog",
            "total_demand",
            "total_fulfilled",
            "total_unfilled",
            "service_level",
            "decay_losses",
        ]:
            if name not in self.properties:
                self.set_property(name, {"type": "Double", "value": 0.0})

    def act(self, time, round_no, step_no):
        pass
