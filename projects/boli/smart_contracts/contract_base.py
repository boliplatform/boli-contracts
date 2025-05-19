# ~/Desktop/boli/projects/boli/smart_contracts/contract_base.py

from pyteal import *
from beaker import *

class BaseState:
    # Base asset state
    asset_id = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Asset ID of the tokenized asset"
    )
    
    asset_creator = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Address of the asset creator"
    )
    
    asset_type = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Type of the asset (e.g., 'blue-economy', 'carbon-credit', etc.)"
    )
    
    geolocation = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Geolocation information for the asset"
    )
    
    metadata = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="IPFS hash or other metadata reference"
    )
    
    jurisdiction_code = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Jurisdiction code where the asset is located/regulated"
    )
    
    compliance_status = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Compliance status of the asset (e.g., 'authorized', 'suspended')"
    )
    
    last_updated = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Timestamp of the last update to the asset"
    )

class ContractBase:
    """Base class for Boli's real-world asset tokenization contracts"""
    
    # This is meant to be inherited, not used directly
    
    @staticmethod
    def assert_sender_is_creator(app):
        """Helper to assert that sender is the app creator"""
        return Assert(
            Txn.sender() == Global.creator_address(),
            comment="Only the creator can perform this action"
        )