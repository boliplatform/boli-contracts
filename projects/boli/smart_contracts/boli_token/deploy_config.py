# ~/Desktop/boli/projects/boli/smart_contracts/boli_token/deploy_config.py

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

def deploy() -> None:
    """Deploy the BOLI token contract."""
    # Import directly from contract.py
    from smart_contracts.boli_token.contract import boli_token_app
    
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
            app=boli_token_app,
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
        logger.info(f"Deployed BOLI Token app with ID: {app_id} and address: {app_addr}")
        
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
            
            # Create the BOLI token
            token_result = app_client.call(
                method="create_token",
                token_name="BOLI Stablecoin",
                unit_name="BOLI",
                treasury_address=deployer.address,  # Use deployer as initial treasury
                reserve_asset_id=0,  # Will be set later
                asset_registry_id=0   # Will be set later
            )
            
            token_id = token_result.return_value
            logger.info(f"Created BOLI Token with ASA ID: {token_id}")
        
        return app_id
    except Exception as e:
        logger.error(f"Error deploying contract: {e}")
        return None