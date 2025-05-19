#!/usr/bin/env python3
# ~/Desktop/boli/projects/boli/test_helper.py

"""
Helper functions for testing Algorand smart contracts
"""

import os
import importlib
from pathlib import Path
import algosdk
from algosdk.v2client import algod
from algosdk.v2client import indexer
from algosdk import account, mnemonic
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_algod_client():
    """Get the Algorand client."""
    algod_token = os.getenv("ALGOD_TOKEN", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
    algod_server = os.getenv("ALGOD_SERVER", "http://localhost")
    algod_port = os.getenv("ALGOD_PORT", "4001")
    
    # Create the client
    algod_address = f"{algod_server}:{algod_port}"
    return algod.AlgodClient(algod_token, algod_address)

def get_indexer_client():
    """Get the Algorand indexer client."""
    indexer_token = os.getenv("INDEXER_TOKEN", "")
    indexer_server = os.getenv("INDEXER_SERVER", "http://localhost")
    indexer_port = os.getenv("INDEXER_PORT", "8980")
    
    # Create the client
    indexer_address = f"{indexer_server}:{indexer_port}"
    return indexer.IndexerClient(indexer_token, indexer_address)

def get_dev_account():
    """Get a development account from mnemonic."""
    dev_mnemonic = os.getenv("DEV_MNEMONIC", "")
    if not dev_mnemonic:
        # Create a new account if no mnemonic is provided
        private_key, address = account.generate_account()
        return {
            "private_key": private_key,
            "address": address,
            "mnemonic": mnemonic.from_private_key(private_key)
        }
    else:
        # Use the provided mnemonic
        private_key = mnemonic.to_private_key(dev_mnemonic)
        address = account.address_from_private_key(private_key)
        return {
            "private_key": private_key,
            "address": address,
            "mnemonic": dev_mnemonic
        }

def get_deployer_account():
    """Get the deployer account from mnemonic."""
    deployer_mnemonic = os.getenv("DEPLOYER_MNEMONIC", "")
    if not deployer_mnemonic:
        # Use the dev account if no deployer mnemonic is provided
        return get_dev_account()
    else:
        # Use the provided mnemonic
        private_key = mnemonic.to_private_key(deployer_mnemonic)
        address = account.address_from_private_key(private_key)
        return {
            "private_key": private_key,
            "address": address,
            "mnemonic": deployer_mnemonic
        }

def load_contract_module(contract_name):
    """Load a contract module by name."""
    try:
        # Import the contract module
        module_path = f"smart_contracts.{contract_name}.contract"
        return importlib.import_module(module_path)
    except ImportError as e:
        print(f"Error importing contract module: {e}")
        return None

def get_application_for_contract(contract_name):
    """Get the Application instance for a contract."""
    contract_module = load_contract_module(contract_name)
    if not contract_module:
        return None
    
    # Find the Application instance
    for var_name in dir(contract_module):
        var = getattr(contract_module, var_name)
        # Look for an instance of the Application class
        var_type = str(type(var))
        if 'Application' in var_type and not var_name.startswith('_'):
            return var
    
    return None

def get_client_for_contract(contract_name, app_id=0):
    """Get a client for interacting with a contract."""
    # Try to import algokit_utils
    try:
        import algokit_utils
    except ImportError:
        print("Error: algokit_utils not found. Please install it with 'pip install algokit-utils'")
        return None
    
    # Get the Application instance
    app = get_application_for_contract(contract_name)
    if not app:
        return None
    
    # Get accounts
    deployer = get_deployer_account()
    
    # Get algod client
    algod_client = get_algod_client()
    
    # Create the client
    app_client = algokit_utils.ApplicationClient(
        algod_client=algod_client,
        app=app,
        app_id=app_id,
        signer=deployer["private_key"]
    )
    
    return app_client

def wait_for_confirmation(client, txid, timeout=4):
    """Wait for a transaction to be confirmed."""
    try:
        status = client.status()
        start_round = status.get("last-round") + 1
        current_round = start_round
        
        while current_round < start_round + timeout:
            try:
                # Check if the transaction has been confirmed
                pending_txn = client.pending_transaction_info(txid)
                
                if pending_txn.get("confirmed-round", 0) > 0:
                    return pending_txn
                
                # Increment the round
                status = client.status_after_block(current_round)
                current_round += 1
            except Exception as e:
                raise Exception(f"Error waiting for transaction: {e}")
        
        raise Exception(f"Transaction not confirmed after {timeout} rounds")
    except Exception as e:
        raise Exception(f"Error waiting for confirmation: {e}")