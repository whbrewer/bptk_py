from BPTK_Py import bptk


def main():
    sim = bptk()
    results = sim.run_scenarios(
        scenarios=["baseline", "reactor_outage", "transport_delay"],
        scenario_managers=["radioisotopeSupplyChain"],
        agents=["monitor"],
        agent_states=["reporting"],
        agent_properties=[
            "production_inventory",
            "processing_inventory",
            "distribution_inventory",
            "end_user_inventory",
            "backlog",
            "service_level",
            "decay_losses",
        ],
        agent_property_types=["mean"],
        return_format="df",
    )
    print(results.tail())


if __name__ == "__main__":
    main()
