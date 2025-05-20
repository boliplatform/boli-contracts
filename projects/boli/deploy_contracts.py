
# ~/Desktop/boli/projects/boli/deploy_contracts.py (UPDATED)

#!/usr/bin/env python3

import os
import sys
import importlib
import argparse
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("deploy_contracts")

def deploy_contract(contract_dir):
    """Deploy a contract using its deploy_config module."""
    contract_name = os.path.basename(contract_dir)
    logger.info(f"Deploying contract: {contract_name}")
    
    # Check for deploy_config.py
    deploy_config_path = os.path.join(contract_dir, "deploy_config.py")
    if not os.path.exists(deploy_config_path):
        logger.error(f"No deploy_config.py found for {contract_name}")
        return False
    
    # Import the deploy_config module
    module_name = f"smart_contracts.{contract_name}.deploy_config"
    try:
        # Make sure the directory containing this script is in the Python path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
            
        # Import the deploy_config module
        deploy_module = importlib.import_module(module_name)
        
        # Call the deploy function
        logger.info(f"Executing deploy function for {contract_name}")
        if hasattr(deploy_module, "deploy"):
            result = deploy_module.deploy()
            if result:
                logger.info(f"Deployed {contract_name} successfully with app ID: {result}")
                return True
            else:
                logger.error(f"Deployment of {contract_name} failed or returned no app ID")
                return False
        else:
            logger.error(f"No deploy function found in {module_name}")
            return False
    except Exception as e:
        logger.error(f"Error deploying {contract_name}: {e}")
        return False

def main():
    """Main function to deploy contracts."""
    parser = argparse.ArgumentParser(description="Deploy Algorand smart contracts")
    parser.add_argument(
        "--contract", "-c", 
        help="Specific contract name to deploy (folder name in smart_contracts directory)"
    )
    # Add argument for BOLI initialization
    parser.add_argument(
        "--boli-init", "-b",
        action="store_true",
        help="Initialize the BOLI platform (deploy and configure all BOLI contracts)"
    )
    args = parser.parse_args()
    
    # Get the directory containing this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if not script_dir:
        script_dir = "."
    
    # Check if BOLI initialization is requested
    if args.boli_init:
        logger.info("Running BOLI platform initialization")
        try:
            # Import and run the initialization script
            sys.path.insert(0, script_dir)
            from initialize_boli_platform import main as init_main
            init_main()
            return
        except Exception as e:
            logger.error(f"Error initializing BOLI platform: {e}")
            return
    
    # Build the root of the project
    contracts_root = os.path.join(script_dir, "smart_contracts")
    
    # Find contracts to deploy
    contract_dirs = []
    
    if args.contract:
        # Deploy a specific contract
        contract_dir = os.path.join(contracts_root, args.contract)
        if os.path.isdir(contract_dir):
            contract_dirs.append(contract_dir)
        else:
            logger.error(f"Contract directory not found: {args.contract}")
            return
    else:
        # Deploy all contracts
        try:
            for d in os.listdir(contracts_root):
                full_path = os.path.join(contracts_root, d)
                if os.path.isdir(full_path) and not d.startswith('_'):
                    deploy_config = os.path.join(full_path, "deploy_config.py")
                    if os.path.exists(deploy_config):
                        contract_dirs.append(full_path)
        except FileNotFoundError:
            logger.error(f"Directory {contracts_root} not found!")
            sys.exit(1)
    
    # Deploy each contract
    success_count = 0
    for contract_dir in contract_dirs:
        if deploy_contract(contract_dir):
            success_count += 1
    
    logger.info(f"Successfully deployed {success_count}/{len(contract_dirs)} contracts")

if __name__ == "__main__":
    main()