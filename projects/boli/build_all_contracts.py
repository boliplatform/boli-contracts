# ~/Desktop/boli/projects/boli/build_all_contracts.py (UPDATED)

#!/usr/bin/env python3

import os
import sys
import importlib
import subprocess
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("build_contracts")

def fix_import_paths():
    """Fix the import paths for contract files."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    
    # Add parent directory to path
    parent_dir = os.path.dirname(script_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

def fix_itoa_references(file_path):
    """Add an Itoa import if it uses Itoa but doesn't import it."""
    try:
        with open(file_path, 'r') as file:
            content = file.read()
        
        # Check if file uses Itoa
        if 'Itoa(' in content and 'from pyteal import' in content and 'Itoa' not in content:
            # Fix the import statement
            new_content = content.replace(
                'from pyteal import',
                'from pyteal import Itoa,'
            )
            with open(file_path, 'w') as file:
                file.write(new_content)
            logger.info(f"Fixed Itoa reference in {file_path}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error fixing Itoa references in {file_path}: {e}")
        return False

def fix_contract_base_import(file_path):
    """Fix the contract_base import for contract files."""
    try:
        with open(file_path, 'r') as file:
            content = file.read()
        
        # Check if file imports contract_base
        if 'from contract_base import' in content:
            # Fix the import statement
            new_content = content.replace(
                'from contract_base import',
                'from smart_contracts.contract_base import'
            )
            with open(file_path, 'w') as file:
                file.write(new_content)
            logger.info(f"Fixed contract_base import in {file_path}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error fixing contract_base import in {file_path}: {e}")
        return False

def build_contract(contract_dir):
    """Build a contract using direct compilation."""
    contract_name = os.path.basename(contract_dir)
    contract_path = os.path.join(contract_dir, "contract.py")
    
    # Handle special case for BOLI token and other new contracts that don't follow the standard naming
    if contract_name == "boli_token" or contract_name == "treasury" or contract_name == "asset_registry" or \
       contract_name == "investment_manager" or contract_name == "revenue_distribution" or contract_name == "token_allocation":
        contract_files = [f for f in os.listdir(contract_dir) if f.endswith('.py') and f != '__init__.py']
        if contract_files:
            contract_path = os.path.join(contract_dir, contract_files[0])
    
    if not os.path.exists(contract_path):
        logger.warning(f"No contract file found for {contract_name}")
        return False
    
    logger.info(f"Building contract: {contract_name}")
    
    # Fix any Itoa references
    fix_itoa_references(contract_path)
    
    # Fix contract_base imports
    fix_contract_base_import(contract_path)
    
    # Create artifacts directory
    artifacts_dir = os.path.join("artifacts", contract_name)
    os.makedirs(artifacts_dir, exist_ok=True)
    
    # Run the Python file directly to compile
    try:
        # Use subprocess to run the contract file
        process = subprocess.run(
            [sys.executable, contract_path],
            capture_output=True,
            text=True,
            env=dict(os.environ, PYTHONPATH=os.pathsep.join(sys.path))
        )
        
        if process.returncode == 0:
            logger.info(f"Successfully built {contract_name}")
            return True
        else:
            logger.error(f"Error building {contract_name}: {process.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error running {contract_name}: {e}")
        return False

def main():
    """Main function to build all contracts."""
    # Fix import paths
    fix_import_paths()
    
    # Get the directory containing this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if not script_dir:
        script_dir = "."
    
    # Build the root of the project
    contracts_root = os.path.join(script_dir, "smart_contracts")
    
    # Create the artifacts directory
    artifacts_dir = os.path.join(script_dir, "artifacts")
    os.makedirs(artifacts_dir, exist_ok=True)
    
    # Get all subdirectories that might contain contracts
    contract_dirs = []
    try:
        for d in os.listdir(contracts_root):
            full_path = os.path.join(contracts_root, d)
            if os.path.isdir(full_path) and not d.startswith('_'):
                # Check for standard contract.py
                contract_file = os.path.join(full_path, "contract.py")
                
                # Also check for any Python files for non-standard modules
                has_py_files = False
                for file in os.listdir(full_path):
                    if file.endswith('.py') and file != '__init__.py':
                        has_py_files = True
                        break
                
                if os.path.exists(contract_file) or has_py_files:
                    contract_dirs.append(full_path)
    except FileNotFoundError:
        logger.error(f"Directory {contracts_root} not found!")
        sys.exit(1)
    
    # Try to build each contract
    success_count = 0
    for contract_dir in contract_dirs:
        if build_contract(contract_dir):
            success_count += 1
    
    logger.info(f"Successfully built {success_count}/{len(contract_dirs)} contracts")

if __name__ == "__main__":
    main()