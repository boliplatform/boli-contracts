# ~/Desktop/boli/projects/boli/smart_contracts/config_constants.py

import os
import json
import logging

logger = logging.getLogger(__name__)

def get_contract_ids():
    """Get all contract IDs from the config file"""
    try:
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(script_dir, "boli_config.json")
        
        if not os.path.exists(config_path):
            logger.warning(f"Config file not found: {config_path}")
            return {}
        
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading contract IDs: {e}")
        return {}

# Constants for connector IDs
PILLARS_CONNECTOR_ID = get_contract_ids().get("pillars_connector", 0)
TERE_CONNECTOR_ID = get_contract_ids().get("tere_connector", 0)

# Constants for core contract IDs
BOLI_TOKEN_ID = get_contract_ids().get("boli_token", 0)
TREASURY_ID = get_contract_ids().get("treasury", 0)
ASSET_REGISTRY_ID = get_contract_ids().get("asset_registry", 0)
INVESTMENT_MANAGER_ID = get_contract_ids().get("investment_manager", 0)
REVENUE_DISTRIBUTION_ID = get_contract_ids().get("revenue_distribution", 0)