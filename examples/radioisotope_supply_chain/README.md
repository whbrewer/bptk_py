# Radioisotope supply chain example

This example builds a hybrid ABM-style supply chain model for short-lived radioisotopes. It represents production, processing, distribution, and end-user demand while modeling transport delays, regulatory holds, and isotope decay. A monitor agent records key service metrics so you can compare baseline and disruption scenarios.

## What the model simulates

- Production facilities create isotope inventory with capacity limits, variability, and outages.
- Processing facilities convert production inventory into usable product with yields and delays.
- Distribution hubs ship product to end users and manage buffers.
- End users generate stochastic demand, consume inventory, and accumulate backlogs.
- Regulatory nodes inject stochastic delays and occasional holds.
- Decay is applied at each inventory node based on half-life.

## How to run

From the repo root:

```bash
python examples/radioisotope_supply_chain/run.py
```

The runner loads scenarios from `scenarios/radioisotope_supply_chain.json` and prints monitor metrics for baseline and disruption cases.

## Scenarios

- `baseline`: nominal operations with mild production variability and small regulatory delays.
- `reactor_outage`: higher outage probability and longer outages, plus higher inventory targets.
- `transport_delay`: increased regulatory and transport delays to stress decay-sensitive delivery.

## Key outputs

The monitor agent records:

- Inventories at production, processing, distribution, and end-user nodes.
- Backlog, total demand, fulfillment, and service level.
- Accumulated decay losses.

You can change scenario settings in `scenarios/radioisotope_supply_chain.json` to explore buffer policies, outage severity, or transport delays.
