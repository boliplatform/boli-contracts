# ~/Desktop/boli/projects/boli/smart_contracts/asset_registry/contract.py

from pyteal import *
from beaker import *
from beaker.lib.storage import BoxMapping

class AssetRegistryState:
    """State class for Asset Registry contract"""
    
    # Registry configuration
    boli_token_id = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Asset ID of the BOLI token"
    )
    
    treasury_app_id = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="App ID of the treasury management"
    )
    
    # Registry statistics
    asset_count = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Total number of registered assets"
    )
    
    # Operations and security
    admin_address = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Address of the admin"
    )
    
    operations_paused = GlobalStateValue(
        stack_type=TealType.uint64,  # 0 = false, 1 = true
        descr="Whether registry operations are paused"
    )
    
    # Asset mappings
    class AssetMappingValue(abi.NamedTuple):
        app_id: abi.Uint64
        asset_type: abi.String
        asset_name: abi.String
        jurisdiction: abi.String
        boli_allocation: abi.Uint64
        investment_status: abi.String
        creation_date: abi.Uint64
    
    # Use BoxMapping for asset information
    assets = BoxMapping(
        key_type=abi.Uint64,  # Asset ID
        value_type=AssetMappingValue,
        prefix=Bytes("asset")
    )
    
    # Map apps to their asset IDs
    app_to_asset = BoxMapping(
        key_type=abi.Uint64,  # App ID
        value_type=abi.Uint64,  # Asset ID
        prefix=Bytes("app")
    )

asset_registry_app = Application(
    "AssetRegistry",
    descr="Central Asset Registry for BOLI Platform",
    state=AssetRegistryState()
)

@asset_registry_app.create
def create():
    """Initialize the Asset Registry contract"""
    return Seq([
        asset_registry_app.state.admin_address.set(Global.creator_address()),
        asset_registry_app.state.operations_paused.set(Int(0)),  # Not paused initially
        asset_registry_app.state.asset_count.set(Int(0)),
        Approve()
    ])

@asset_registry_app.external
def configure_registry(
    boli_token_id: abi.Uint64,
    treasury_app_id: abi.Uint64,
    *,
    output: abi.Bool
) -> Expr:
    """Configure the asset registry with token and treasury information"""
    
    # Only allow the admin to configure the registry
    assert_admin = Assert(
        Txn.sender() == asset_registry_app.state.admin_address.get(),
        comment="Only admin can configure registry"
    )
    
    # Store configuration
    store_config = Seq([
        asset_registry_app.state.boli_token_id.set(boli_token_id.get()),
        asset_registry_app.state.treasury_app_id.set(treasury_app_id.get())
    ])
    
    return Seq([
        assert_admin,
        store_config,
        output.set(Int(1))  # True
    ])

@asset_registry_app.external
def register_asset(
    app_id: abi.Uint64,
    asset_type: abi.String,
    asset_name: abi.String,
    jurisdiction: abi.String,
    boli_allocation: abi.Uint64,
    *,
    output: abi.Uint64
) -> Expr:
    """Register a new asset and request allocation from treasury"""
    
    # Only allow the admin to register assets
    assert_admin = Assert(
        Txn.sender() == asset_registry_app.state.admin_address.get(),
        comment="Only admin can register assets"
    )
    
    # Check that operations are not paused
    assert_not_paused = Assert(
        asset_registry_app.state.operations_paused.get() == Int(0),
        comment="Registry operations are paused"
    )
    
    # Check that app_id is not already registered
    app_already_registered = asset_registry_app.state.app_to_asset[app_id].exists()
    
    assert_not_registered = Assert(
        Not(app_already_registered),
        comment="App ID is already registered"
    )
    
    # Generate an asset ID (we'll use the app_id for simplicity but in production
    # you might want a more sophisticated ID generation)
    asset_id = app_id
    
    # Reserve allocation from treasury
    reserve_allocation = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.ApplicationCall,
            TxnField.application_id: asset_registry_app.state.treasury_app_id.get(),
            TxnField.on_completion: OnComplete.NoOp,
            TxnField.application_args: [
                Bytes("reserve_allocation"),
                Itob(asset_id.get()),
                Itob(boli_allocation.get())
            ]
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Create the asset mapping value
    asset_mapping = asset_registry_app.state.AssetMappingValue()
    set_asset_mapping = Seq([
        asset_mapping.app_id.set(app_id.get()),
        asset_mapping.asset_type.set(asset_type.get()),
        asset_mapping.asset_name.set(asset_name.get()),
        asset_mapping.jurisdiction.set(jurisdiction.get()),
        asset_mapping.boli_allocation.set(boli_allocation.get()),
        asset_mapping.investment_status.set(Bytes("registered")),
        asset_mapping.creation_date.set(Global.latest_timestamp())
    ])
    
    # Store the asset information
    store_asset = Seq([
        asset_registry_app.state.assets[asset_id].set(asset_mapping),
        asset_registry_app.state.app_to_asset[app_id].set(asset_id),
        asset_registry_app.state.asset_count.set(
            asset_registry_app.state.asset_count.get() + Int(1)
        )
    ])
    
    return Seq([
        assert_admin,
        assert_not_paused,
        assert_not_registered,
        reserve_allocation,
        set_asset_mapping,
        store_asset,
        output.set(asset_id)
    ])

@asset_registry_app.external
def update_asset_status(
    asset_id: abi.Uint64,
    new_status: abi.String,
    *,
    output: abi.Bool
) -> Expr:
    """Update the investment status of an asset"""
    
    # Only allow the admin to update asset status
    assert_admin = Assert(
        Txn.sender() == asset_registry_app.state.admin_address.get(),
        comment="Only admin can update asset status"
    )
    
    # Check that operations are not paused
    assert_not_paused = Assert(
        asset_registry_app.state.operations_paused.get() == Int(0),
        comment="Registry operations are paused"
    )
    
    # Check that the asset exists
    asset_exists = asset_registry_app.state.assets[asset_id].exists()
    
    assert_asset_exists = Assert(
        asset_exists,
        comment="Asset does not exist"
    )
    
    # Get the current asset mapping
    asset_mapping = asset_registry_app.state.assets[asset_id].get()
    
    # Validate the status transition
    # In a more complex implementation, you would have a state machine
    # to validate all possible transitions
    valid_status = Or(
        new_status.get() == Bytes("registered"),
        new_status.get() == Bytes("funding"),
        new_status.get() == Bytes("funded"),
        new_status.get() == Bytes("active"),
        new_status.get() == Bytes("completed")
    )
    
    assert_valid_status = Assert(
        valid_status,
        comment="Invalid status"
    )
    
    # Update the status
    asset_mapping.investment_status.set(new_status.get())
    
    # Store the updated asset information
    store_updated_asset = asset_registry_app.state.assets[asset_id].set(asset_mapping)
    
    # If status is "funded", complete the asset in treasury
    complete_in_treasury = If(
        new_status.get() == Bytes("funded"),
        Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.ApplicationCall,
                TxnField.application_id: asset_registry_app.state.treasury_app_id.get(),
                TxnField.on_completion: OnComplete.NoOp,
                TxnField.application_args: [
                    Bytes("complete_asset_funding"),
                    Itob(asset_id.get())
                ]
            }),
            InnerTxnBuilder.Submit()
        ),
        Seq([])  # No-op for other status values
    )
    
    return Seq([
        assert_admin,
        assert_not_paused,
        assert_asset_exists,
        assert_valid_status,
        store_updated_asset,
        complete_in_treasury,
        output.set(Int(1))  # True
    ])

@asset_registry_app.external
def allocate_tokens_to_investor(
    asset_id: abi.Uint64,
    investor: abi.Address,
    amount: abi.Uint64,
    *,
    output: abi.Bool
) -> Expr:
    """Allocate BOLI tokens to an investor for a specific asset"""
    
    # Only allow the admin to allocate tokens
    assert_admin = Assert(
        Txn.sender() == asset_registry_app.state.admin_address.get(),
        comment="Only admin can allocate tokens"
    )
    
    # Check that operations are not paused
    assert_not_paused = Assert(
        asset_registry_app.state.operations_paused.get() == Int(0),
        comment="Registry operations are paused"
    )
    
    # Check that the asset exists
    asset_exists = asset_registry_app.state.assets[asset_id].exists()
    
    assert_asset_exists = Assert(
        asset_exists,
        comment="Asset does not exist"
    )
    
    # Get the asset mapping
    asset_mapping = asset_registry_app.state.assets[asset_id].get()
    
    # Check that the asset is in funding or active status
    is_funding_or_active = Or(
        asset_mapping.investment_status.get() == Bytes("funding"),
        asset_mapping.investment_status.get() == Bytes("active")
    )
    
    assert_correct_status = Assert(
        is_funding_or_active,
        comment="Asset is not in funding or active status"
    )
    
    # In a more complex implementation, you would check against
    # the available allocation for this asset and track investments
    # Here we'll just do a simple token transfer
    
    # Transfer tokens to the investor
    transfer_tokens = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.ApplicationCall,
            TxnField.application_id: asset_registry_app.state.boli_token_id.get(),
            TxnField.on_completion: OnComplete.NoOp,
            TxnField.application_args: [
                Bytes("transfer_tokens"),
                Itob(amount.get()),
                Global.current_application_address(),
                investor.get()
            ]
        }),
        InnerTxnBuilder.Submit()
    )
    
    return Seq([
        assert_admin,
        assert_not_paused,
        assert_asset_exists,
        assert_correct_status,
        transfer_tokens,
        output.set(Int(1))  # True
    ])

@asset_registry_app.external(read_only=True)
def get_asset_details(
    asset_id: abi.Uint64,
    *,
    output: abi.String
) -> Expr:
    """Get detailed information about an asset"""
    
    # Check if the asset exists
    asset_exists = asset_registry_app.state.assets[asset_id].exists()
    
    # Get asset information if it exists
    asset_mapping = asset_registry_app.state.assets[asset_id].get()
    
    # Build the asset information string
    asset_info = If(
        asset_exists,
        Concat(
            Bytes("Asset ID: "), Int2Str(asset_id.get()),
            Bytes(" | App ID: "), Int2Str(asset_mapping.app_id.get()),
            Bytes(" | Type: "), asset_mapping.asset_type.get(),
            Bytes(" | Name: "), asset_mapping.asset_name.get(),
            Bytes(" | Jurisdiction: "), asset_mapping.jurisdiction.get(),
            Bytes(" | Allocation: "), Int2Str(asset_mapping.boli_allocation.get()),
            Bytes(" | Status: "), asset_mapping.investment_status.get(),
            Bytes(" | Created: "), Int2Str(asset_mapping.creation_date.get())
        ),
        Bytes("Asset not found")
    )
    
    return output.set(asset_info)

@asset_registry_app.external(read_only=True)
def get_asset_id_by_app(
    app_id: abi.Uint64,
    *,
    output: abi.Uint64
) -> Expr:
    """Get the asset ID for a specific app ID"""
    
    # Check if the app ID is registered
    app_registered = asset_registry_app.state.app_to_asset[app_id].exists()
    
    # Get the asset ID if registered
    asset_id = asset_registry_app.state.app_to_asset[app_id].get()
    
    return If(
        app_registered,
        output.set(asset_id),
        output.set(Int(0))  # Return 0 if not found
    )

@asset_registry_app.external
def pause_registry_operations(
    pause_state: abi.Bool,
    *,
    output: abi.Bool
) -> Expr:
    """Pause or unpause registry operations"""
    
    # Only allow the admin to pause/unpause
    assert_admin = Assert(
        Txn.sender() == asset_registry_app.state.admin_address.get(),
        comment="Only admin can pause/unpause"
    )
    
    # Update pause state
    update_pause = asset_registry_app.state.operations_paused.set(
        If(pause_state.get(), Int(1), Int(0))
    )
    
    return Seq([
        assert_admin,
        update_pause,
        output.set(Int(1))  # True
    ])

@asset_registry_app.external
def change_admin(
    new_admin: abi.Address,
    *,
    output: abi.Bool
) -> Expr:
    """Change the admin address"""
    
    # Only allow the current admin to change admin
    assert_admin = Assert(
        Txn.sender() == asset_registry_app.state.admin_address.get(),
        comment="Only current admin can change admin"
    )
    
    # Update admin address
    update_admin = asset_registry_app.state.admin_address.set(new_admin.get())
    
    return Seq([
        assert_admin,
        update_admin,
        output.set(Int(1))  # True
    ])

# Helper function to convert integer to string
def Int2Str(i: Expr) -> Expr:
    """Convert an integer expression to a string expression using Itob."""
    return Extract(Itob(i), Int(0), Int(8))

if __name__ == "__main__":
    # Compile and export the app
    app_spec = asset_registry_app.build()
    app_spec.export("artifacts/asset_registry")