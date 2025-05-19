# ~/Desktop/boli/projects/boli/smart_contracts/renewable_energy/deploy_config.py

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

def deploy() -> None:
    """Deploy the renewable energy contract."""
    # Import directly from contract.py
    from smart_contracts.renewable_energy.contract import renewable_energy_app
    
    # Import algokit_utils
    try:
        import algokit_utils
        from algokit_utils import AlgorandClient
    except ImportError:
        logger.error("algokit_utils not found. Installing it...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "algokit-utils>=2.0.0,<3.0.0"])
        import algokit_utils
        from algokit_utils import AlgorandClient
    
    # Initialize Algorand client
    try:
        algorand = AlgorandClient.from_environment()
        logger.info("Connected to Algorand node")
    except Exception as e:
        logger.error(f"Error connecting to Algorand node: {e}")
        return
    
    # Get deployer account
    try:
        deployer = algorand.account.from_environment("DEPLOYER")
        logger.info(f"Using deployer account: {deployer.address}")
    except Exception as e:
        logger.error(f"Error getting deployer account: {e}")
        return
    
    # Create Application client
    try:
        app_client = algokit_utils.ApplicationClient(
            algod_client=algorand.client,
            app=renewable_energy_app,
            signer=deployer,
        )
        logger.info("Created Application client")
    except Exception as e:
        logger.error(f"Error creating Application client: {e}")
        return
    
    # Deploy the app
    try:
        result = app_client.create()
        app_id = result.app_id
        app_addr = result.app_addr
        logger.info(f"Deployed app with ID: {app_id} and address: {app_addr}")
        
        # Fund the app if it was created
        if app_id > 0:
            payment_txn = algorand.send.payment(
                algokit_utils.PaymentParams(
                    amount=algokit_utils.AlgoAmount(algo=1),
                    sender=deployer.address,
                    receiver=app_addr,
                )
            )
            logger.info(f"Funded app with 1 ALGO, txid: {payment_txn.txid}")
        
        return app_id
    except Exception as e:
        logger.error(f"Error deploying contract: {e}")
        return None