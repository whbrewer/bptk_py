"""
Example usage of Pydantic Logfire integration with BPTK-Py

This demonstrates three different ways to enable Logfire logging in BPTK-Py.
"""

# Method 1: Configure Logfire when initializing BPTK
from BPTK_Py import bptk

# Initialize BPTK with Logfire configuration
bptk_instance = bptk(
    loglevel="INFO",
    configuration={
        "logfire_config": {
            "project_name": "bptk_simulations",
            "environment": "development",
            # Add your Logfire token if needed
            # "token": "your-logfire-token"
        }
    }
)

# Method 2: Configure Logfire directly via the logger module
import BPTK_Py.logger.logger as logmod

# Configure Logfire (if not already done via bptk initialization)
logmod.configure_logfire(
    project_name="bptk_simulations",
    environment="production"
)

# Later, you can disable Logfire if needed
# logmod.disable_logfire()

# Method 3: Use Logfire alongside file logging
# By default, logs go to both file and Logfire when configured
logmod.logmodes = ["logfile"]  # File logging is still active
logmod.loglevel = "INFO"

# Now when you run simulations, logs will be sent to Logfire
# Example:
# bptk_instance.plot_scenarios(
#     scenarios=["baseline", "optimized"],
#     scenario_managers=["my_model"]
# )

# The logs will include all INFO, WARN, and ERROR messages from:
# - Model loading and parsing
# - Scenario execution
# - File monitoring
# - Error handling
# - And more...

# To check if Logfire is available and enabled:
print(f"Logfire available: {logmod.LOGFIRE_AVAILABLE}")
print(f"Logfire enabled: {logmod.logfire_enabled}")