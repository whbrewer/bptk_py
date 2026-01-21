from BPTK_Py import bptk
import pandas as pd


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
    focus_metrics = ["backlog", "service_level", "decay_losses"]
    focus_columns = [
        column
        for column in results.columns
        if any(metric in column for metric in focus_metrics)
    ]
    stats = results[focus_columns].describe().transpose()
    summary = stats.reset_index().rename(columns={"index": "series"})
    split = summary["series"].str.split("_")
    summary["scenario"] = split.str[1]
    summary["metric"] = split.str[-2]
    summary["property_type"] = split.str[-1]
    summary = summary[
        [
            "scenario",
            "metric",
            "property_type",
            "mean",
            "std",
            "min",
            "max",
        ]
    ].sort_values(["scenario", "metric"])
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
