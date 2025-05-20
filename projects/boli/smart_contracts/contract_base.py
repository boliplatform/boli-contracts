# ~/Desktop/boli/projects/boli/smart_contracts/contract_base.py (UPDATED)

from pyteal import *
from beaker import *

class BaseState:
    # Base asset state (existing fields)
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
    
    # NEW FIELDS FOR BOLI TOKEN INTEGRATION
    boli_allocation = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Amount of BOLI tokens allocated to this asset"
    )
    
    current_funding = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Current amount of BOLI tokens funded"
    )
    
    investment_status = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Investment status (registered, funding, funded, active, completed)"
    )
    
    asset_registry_id = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="App ID of the Asset Registry managing this asset"
    )
    
    treasury_app_id = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="App ID of the Treasury managing the backing"
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
    
    # NEW METHODS FOR BOLI TOKEN INTEGRATION
    @staticmethod
    def register_with_asset_registry(app, asset_name, asset_type, jurisdiction_code, boli_allocation):
        """Helper to register an asset with the BOLI Asset Registry"""
        return Seq([
            Assert(
                app.state.asset_registry_id.get() != Int(0),
                comment="Asset Registry ID not configured"
            ),
            
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: app.state.asset_registry_id.get(),
                TxnField.on_completion: OnComplete.NoOp,
                TxnField.application_args: [
                    Bytes("register_asset"),
                    Itob(Global.current_application_id()),
                    asset_type,
                    asset_name,
                    jurisdiction_code,
                    Itob(boli_allocation)
                ]
            }),
            InnerTxnBuilder.Submit(),
            
            # Store allocation amount and set initial status
            app.state.boli_allocation.set(boli_allocation),
            app.state.current_funding.set(Int(0)),
            app.state.investment_status.set(Bytes("registered"))
        ])
    
    @staticmethod
    def update_investment_status(app, new_status):
        """Helper to update the investment status"""
        return Seq([
            Assert(
                app.state.asset_registry_id.get() != Int(0),
                comment="Asset Registry ID not configured"
            ),
            
            app.state.investment_status.set(new_status),
            
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: app.state.asset_registry_id.get(),
                TxnField.on_completion: OnComplete.NoOp,
                TxnField.application_args: [
                    Bytes("update_asset_status"),
                    Itob(app.state.asset_id.get()),
                    new_status
                ]
            }),
            InnerTxnBuilder.Submit()
        ])
    
    @staticmethod
    def distribute_revenue(app, amount, distribution_type, note):
        """Helper to distribute revenue from the asset to token holders"""
        return Seq([
            Assert(
                app.state.asset_registry_id.get() != Int(0),
                comment="Asset Registry ID not configured"
            ),
            
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: app.state.asset_registry_id.get(),
                TxnField.on_completion: OnComplete.NoOp,
                TxnField.application_args: [
                    Bytes("create_distribution"),
                    Itob(app.state.asset_id.get()),
                    Itob(amount),
                    distribution_type,
                    note
                ]
            }),
            InnerTxnBuilder.Submit()
        ])