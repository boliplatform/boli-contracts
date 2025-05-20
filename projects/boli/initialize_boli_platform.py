# ~/Desktop/boli/projects/boli/initialize_boli_platform.py

import logging
import os
from pathlib import Path
import sys
import importlib.util
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("boli_init")

def import_module_from_path(module_name, file_path):
    """Import a module from a specific file path"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def deploy_contract(contract_dir, file_name="deploy_config.py"):
    """Deploy a contract using its deploy_config module."""
    contract_name = os.path.basename(contract_dir)
    logger.info(f"Deploying contract: {contract_name}")
    
    # Build the path to the deploy_config.py file
    deploy_config_path = os.path.join(contract_dir, file_name)
    if not os.path.exists(deploy_config_path):
        logger.error(f"No {file_name} found for {contract_name}")
        return None
    
    # Import the deploy_config module dynamically
    module_name = f"deploy_{contract_name}"
    try:
        deploy_module = import_module_from_path(module_name, deploy_config_path)
        
        # Call the deploy function
        logger.info(f"Executing deploy function for {contract_name}")
        if hasattr(deploy_module, "deploy"):
            app_id = deploy_module.deploy()
            if app_id:
                logger.info(f"Deployed {contract_name} successfully with app ID: {app_id}")
                return app_id
            else:
                logger.error(f"Deployment of {contract_name} failed or returned no app ID")
                return None
        else:
            logger.error(f"No deploy function found in {module_name}")
            return None
    except Exception as e:
        logger.error(f"Error deploying {contract_name}: {e}")
        return None

def main():
    """Initialize the BOLI platform by deploying all necessary contracts."""
    
    # Get the root directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    contracts_root = os.path.join(script_dir, "smart_contracts")
    
    # Dictionary to store app IDs of deployed contracts
    app_ids = {}
    
    # Step 1: Deploy BOLI Token contract
    logger.info("Step 1: Deploying BOLI Token contract")
    boli_contract_dir = os.path.join(contracts_root, "boli_token")
    boli_app_id = deploy_contract(boli_contract_dir)
    if not boli_app_id:
        logger.error("Failed to deploy BOLI Token contract. Initialization aborted.")
        return
    app_ids["boli_token"] = boli_app_id
    
    # Step 2: Deploy Treasury Management contract
    logger.info("Step 2: Deploying Treasury Management contract")
    treasury_contract_dir = os.path.join(contracts_root, "treasury")
    treasury_app_id = deploy_contract(treasury_contract_dir)
    if not treasury_app_id:
        logger.error("Failed to deploy Treasury Management contract. Initialization aborted.")
        return
    app_ids["treasury"] = treasury_app_id
    
    # Step 3: Deploy Asset Registry contract
    logger.info("Step 3: Deploying Asset Registry contract")
    registry_contract_dir = os.path.join(contracts_root, "asset_registry")
    registry_app_id = deploy_contract(registry_contract_dir)
    if not registry_app_id:
        logger.error("Failed to deploy Asset Registry contract. Initialization aborted.")
        return
    app_ids["asset_registry"] = registry_app_id
    
    # Step 4: Deploy Investment Manager contract
    logger.info("Step 4: Deploying Investment Manager contract")
    investment_contract_dir = os.path.join(contracts_root, "investment_manager")
    investment_app_id = deploy_contract(investment_contract_dir)
    if not investment_app_id:
        logger.error("Failed to deploy Investment Manager contract. Initialization aborted.")
        return
    app_ids["investment_manager"] = investment_app_id
    
    # Step 5: Deploy Revenue Distribution contract
    logger.info("Step 5: Deploying Revenue Distribution contract")
    revenue_contract_dir = os.path.join(contracts_root, "revenue_distribution")
    revenue_app_id = deploy_contract(revenue_contract_dir)
    if not revenue_app_id:
        logger.error("Failed to deploy Revenue Distribution contract. Initialization aborted.")
        return
    app_ids["revenue_distribution"] = revenue_app_id
    
    # Step 6: Configure the contracts to work together
    logger.info("Step 6: Configuring contracts to work together")
    try:
        # Import algokit_utils for client interactions
        import algokit_utils
        from algokit_utils import AlgorandClient
        
        # Initialize Algorand client
        algorand = AlgorandClient.from_environment()
        deployer = algorand.account.from_environment("DEPLOYER")
        
        # Configure BOLI Token with connections to other contracts
        boli_client = algokit_utils.ApplicationClient(
            algod_client=algorand.client,
            app_id=boli_app_id,
            signer=deployer
        )
        
        # Configure Treasury with connections to other contracts
        treasury_client = algokit_utils.ApplicationClient(
            algod_client=algorand.client,
            app_id=treasury_app_id,
            signer=deployer
        )
        treasury_client.call(
            method="configure_treasury",
            boli_token_id=app_ids["boli_token"],
            stablecoin_reserve_id=0,  # Will be set to actual stablecoin ASA ID later
            asset_registry_id=app_ids["asset_registry"]
        )
        
        # Configure Asset Registry with connections to other contracts
        registry_client = algokit_utils.ApplicationClient(
            algod_client=algorand.client,
            app_id=registry_app_id,
            signer=deployer
        )
        registry_client.call(
            method="configure_registry",
            boli_token_id=app_ids["boli_token"],
            treasury_app_id=app_ids["treasury"]
        )
        
        # Configure Investment Manager with connections to other contracts
        investment_client = algokit_utils.ApplicationClient(
            algod_client=algorand.client,
            app_id=investment_app_id,
            signer=deployer
        )
        investment_client.call(
            method="configure_manager",
            boli_token_id=app_ids["boli_token"],
            treasury_app_id=app_ids["treasury"],
            asset_registry_id=app_ids["asset_registry"],
            stablecoin_id=0  # Will be set to actual stablecoin ASA ID later
        )
        
        # Configure Revenue Distribution with connections to other contracts
        revenue_client = algokit_utils.ApplicationClient(
            algod_client=algorand.client,
            app_id=revenue_app_id,
            signer=deployer
        )
        revenue_client.call(
            method="configure_distribution",
            boli_token_id=app_ids["boli_token"],
            asset_registry_id=app_ids["asset_registry"]
        )
        
        logger.info("All contracts configured successfully!")
        
    except Exception as e:
        logger.error(f"Error during contract configuration: {e}")
        return
    
    # Step 7: Save the app IDs to a configuration file
    logger.info("Step 7: Saving contract configuration")
    try:
        config_path = os.path.join(script_dir, "boli_config.json")
        with open(config_path, "w") as f:
            json.dump(app_ids, f, indent=4)
        logger.info(f"Contract configuration saved to {config_path}")
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
    
    logger.info("BOLI Platform initialization completed successfully!")
    logger.info(f"App IDs: {app_ids}")

if __name__ == "__main__":
    main()