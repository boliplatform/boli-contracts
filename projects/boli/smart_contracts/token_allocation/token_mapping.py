# ~/Desktop/boli/projects/boli/smart_contracts/token_allocation/token_mapping.py

from pyteal import *
from beaker import *

class TokenAllocationMapping:
    """Utility class for managing token-to-asset allocations"""
    
    @staticmethod
    def create_allocation_key(asset_id):
        """Create a standard key for asset allocations"""
        return Concat(Bytes("alloc-"), Itob(asset_id))
    
    @staticmethod
    def create_investor_key(investor_address, asset_id):
        """Create a standard key for investor allocations"""
        return Concat(Bytes("inv-"), investor_address, Bytes("-"), Itob(asset_id))
    
    @staticmethod
    def allocate_tokens_to_asset(app_id, asset_id, amount):
        """Call the asset registry to allocate tokens to an asset"""
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: app_id,
                TxnField.on_completion: OnComplete.NoOp,
                TxnField.application_args: [
                    Bytes("allocate_tokens_to_asset"),
                    Itob(asset_id),
                    Itob(amount)
                ]
            }),
            InnerTxnBuilder.Submit()
        )
    
    @staticmethod
    def allocate_tokens_to_investor(app_id, asset_id, investor, amount):
        """Call the asset registry to allocate tokens to an investor for an asset"""
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: app_id,
                TxnField.on_completion: OnComplete.NoOp,
                TxnField.application_args: [
                    Bytes("allocate_tokens_to_investor"),
                    Itob(asset_id),
                    investor,
                    Itob(amount)
                ]
            }),
            InnerTxnBuilder.Submit()
        )
    
    @staticmethod
    def get_asset_allocation(app_id, asset_id):
        """Get the allocation for an asset"""
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: app_id,
                TxnField.on_completion: OnComplete.NoOp,
                TxnField.application_args: [
                    Bytes("get_asset_allocation"),
                    Itob(asset_id)
                ]
            }),
            InnerTxnBuilder.Submit()
        )
    
    @staticmethod
    def get_investor_allocation(app_id, investor, asset_id):
        """Get the allocation for an investor for an asset"""
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: app_id,
                TxnField.on_completion: OnComplete.NoOp,
                TxnField.application_args: [
                    Bytes("get_investor_allocation"),
                    investor,
                    Itob(asset_id)
                ]
            }),
            InnerTxnBuilder.Submit()
        )