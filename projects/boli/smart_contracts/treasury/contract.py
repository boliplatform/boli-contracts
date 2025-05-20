# ~/Desktop/boli/projects/boli/smart_contracts/treasury/contract.py

from pyteal import *
from beaker import *
from beaker.lib.storage import BoxMapping

class TreasuryState:
    """State class for Treasury Management contract"""
    
    # Treasury configuration
    boli_token_id = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Asset ID of the BOLI token"
    )
    
    stablecoin_reserve_id = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Asset ID of the reserve stablecoin"
    )
    
    asset_registry_id = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="App ID of the asset registry"
    )
    
    # Treasury capacity
    total_capacity = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Total capacity of the treasury (e.g., 1 billion)"
    )
    
    current_allocated = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Current allocated amount from the treasury"
    )
    
    current_reserved = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Current reserved but not yet funded amount"
    )
    
    # Operations and security
    admin_address = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Address of the admin"
    )
    
    operations_paused = GlobalStateValue(
        stack_type=TealType.uint64,  # 0 = false, 1 = true
        descr="Whether treasury operations are paused"
    )
    
    # Stablecoin tracking information
    reserve_balance = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Current balance of stablecoins in reserve"
    )
    
    last_attestation_timestamp = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Timestamp of last reserve attestation"
    )
    
    # Asset allocations using BoxMapping
    asset_allocations = BoxMapping(
        key_type=abi.Uint64,  # Asset ID
        value_type=abi.Uint64,  # Allocation amount
        prefix=Bytes("alloc")
    )
    
    asset_status = BoxMapping(
        key_type=abi.Uint64,  # Asset ID
        value_type=abi.String,  # Status (reserved, funded, completed)
        prefix=Bytes("status")
    )

treasury_app = Application(
    "TreasuryManagement",
    descr="Treasury Management for BOLI Platform with $1B capacity",
    state=TreasuryState()
)

@treasury_app.create
def create():
    """Initialize the Treasury Management contract"""
    return Seq([
        treasury_app.state.admin_address.set(Global.creator_address()),
        treasury_app.state.operations_paused.set(Int(0)),  # Not paused initially
        treasury_app.state.total_capacity.set(Int(1000000000)),  # $1B capacity
        treasury_app.state.current_allocated.set(Int(0)),
        treasury_app.state.current_reserved.set(Int(0)),
        treasury_app.state.reserve_balance.set(Int(0)),
        treasury_app.state.last_attestation_timestamp.set(Global.latest_timestamp()),
        Approve()
    ])

@treasury_app.external
def configure_treasury(
    boli_token_id: abi.Uint64,
    stablecoin_reserve_id: abi.Uint64,
    asset_registry_id: abi.Uint64,
    *,
    output: abi.Bool
) -> Expr:
    """Configure the treasury with token and registry information"""
    
    # Only allow the admin to configure the treasury
    assert_admin = Assert(
        Txn.sender() == treasury_app.state.admin_address.get(),
        comment="Only admin can configure treasury"
    )
    
    # Store configuration
    store_config = Seq([
        treasury_app.state.boli_token_id.set(boli_token_id.get()),
        treasury_app.state.stablecoin_reserve_id.set(stablecoin_reserve_id.get()),
        treasury_app.state.asset_registry_id.set(asset_registry_id.get())
    ])
    
    return Seq([
        assert_admin,
        store_config,
        output.set(Int(1))  # True
    ])

@treasury_app.external
def reserve_allocation(
    asset_id: abi.Uint64,
    amount: abi.Uint64,
    *,
    output: abi.Bool
) -> Expr:
    """Reserve allocation from treasury for a specific asset"""
    
    # Verify the caller is authorized (admin or asset registry)
    is_authorized = Or(
        Txn.sender() == treasury_app.state.admin_address.get(),
        Txn.sender() == App.globalGet(treasury_app.state.asset_registry_id.get(), Bytes("admin"))
    )
    
    assert_authorized = Assert(
        is_authorized,
        comment="Only admin or asset registry can reserve allocation"
    )
    
    # Check that operations are not paused
    assert_not_paused = Assert(
        treasury_app.state.operations_paused.get() == Int(0),
        comment="Treasury operations are paused"
    )
    
    # Check if there's enough remaining capacity
    remaining_capacity = treasury_app.state.total_capacity.get() - (
        treasury_app.state.current_allocated.get() + treasury_app.state.current_reserved.get()
    )
    
    assert_enough_capacity = Assert(
        amount.get() <= remaining_capacity,
        comment="Not enough treasury capacity"
    )
    
    # Check that the asset doesn't already have an allocation
    asset_allocation_exists = treasury_app.state.asset_allocations[asset_id].exists()
    
    assert_no_existing_allocation = Assert(
        Not(asset_allocation_exists),
        comment="Asset already has an allocation"
    )
    
    # Store the allocation
    store_allocation = Seq([
        treasury_app.state.asset_allocations[asset_id].set(amount),
        treasury_app.state.asset_status[asset_id].set(Bytes("reserved")),
        treasury_app.state.current_reserved.set(
            treasury_app.state.current_reserved.get() + amount.get()
        )
    ])
    
    return Seq([
        assert_authorized,
        assert_not_paused,
        assert_enough_capacity,
        assert_no_existing_allocation,
        store_allocation,
        output.set(Int(1))  # True
    ])

@treasury_app.external
def process_stablecoin_deposit(
    amount: abi.Uint64,
    asset_id: abi.Uint64,
    deposit_txn_id: abi.String,
    *,
    output: abi.Bool
) -> Expr:
    """Process a stablecoin deposit for an asset and mint BOLI tokens"""
    
    # Only allow the admin to process deposits
    assert_admin = Assert(
        Txn.sender() == treasury_app.state.admin_address.get(),
        comment="Only admin can process deposits"
    )
    
    # Check that operations are not paused
    assert_not_paused = Assert(
        treasury_app.state.operations_paused.get() == Int(0),
        comment="Treasury operations are paused"
    )
    
    # Verify the asset has an allocation
    asset_allocation_exists = treasury_app.state.asset_allocations[asset_id].exists()
    
    assert_allocation_exists = Assert(
        asset_allocation_exists,
        comment="Asset has no allocation"
    )
    
    # Verify the asset is in "reserved" status
    asset_status = treasury_app.state.asset_status[asset_id].get()
    
    assert_correct_status = Assert(
        asset_status == Bytes("reserved"),
        comment="Asset is not in reserved status"
    )
    
    # Verify the amount doesn't exceed the allocation
    allocation_amount = treasury_app.state.asset_allocations[asset_id].get()
    
    assert_amount_valid = Assert(
        amount.get() <= allocation_amount,
        comment="Amount exceeds allocation"
    )
    
    # Update treasury tracking
    update_treasury = Seq([
        treasury_app.state.reserve_balance.set(
            treasury_app.state.reserve_balance.get() + amount.get()
        ),
        treasury_app.state.current_reserved.set(
            treasury_app.state.current_reserved.get() - amount.get()
        ),
        treasury_app.state.current_allocated.set(
            treasury_app.state.current_allocated.get() + amount.get()
        )
    ])
    
    # Update asset status if fully funded
    update_status = If(
        amount.get() == allocation_amount,
        treasury_app.state.asset_status[asset_id].set(Bytes("funded")),
        treasury_app.state.asset_status[asset_id].set(Bytes("partially_funded"))
    )
    
    # Mint BOLI tokens by calling the BOLI token contract
    mint_tokens = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.ApplicationCall,
            TxnField.application_id: treasury_app.state.boli_token_id.get(),
            TxnField.on_completion: OnComplete.NoOp,
            TxnField.application_args: [
                Bytes("mint_tokens"),
                Itob(amount.get()),
                Global.current_application_address(),
                deposit_txn_id.get()
            ]
        }),
        InnerTxnBuilder.Submit()
    )
    
    return Seq([
        assert_admin,
        assert_not_paused,
        assert_allocation_exists,
        assert_correct_status,
        assert_amount_valid,
        update_treasury,
        update_status,
        mint_tokens,
        output.set(Int(1))  # True
    ])

@treasury_app.external
def process_stablecoin_withdrawal(
    amount: abi.Uint64,
    recipient: abi.Address,
    *,
    output: abi.Bool
) -> Expr:
    """Process a stablecoin withdrawal (burning BOLI tokens)"""
    
    # Only allow the admin to process withdrawals
    assert_admin = Assert(
        Txn.sender() == treasury_app.state.admin_address.get(),
        comment="Only admin can process withdrawals"
    )
    
    # Check that operations are not paused
    assert_not_paused = Assert(
        treasury_app.state.operations_paused.get() == Int(0),
        comment="Treasury operations are paused"
    )
    
    # Verify there are enough stablecoins in reserve
    assert_enough_reserve = Assert(
        treasury_app.state.reserve_balance.get() >= amount.get(),
        comment="Not enough stablecoins in reserve"
    )
    
    # Update treasury tracking
    update_treasury = Seq([
        treasury_app.state.reserve_balance.set(
            treasury_app.state.reserve_balance.get() - amount.get()
        ),
        treasury_app.state.current_allocated.set(
            treasury_app.state.current_allocated.get() - amount.get()
        )
    ])
    
    # Burn BOLI tokens by calling the BOLI token contract
    burn_tokens = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.ApplicationCall,
            TxnField.application_id: treasury_app.state.boli_token_id.get(),
            TxnField.on_completion: OnComplete.NoOp,
            TxnField.application_args: [
                Bytes("burn_tokens"),
                Itob(amount.get()),
                recipient.get()
            ]
        }),
        InnerTxnBuilder.Submit()
    )
    
    return Seq([
        assert_admin,
        assert_not_paused,
        assert_enough_reserve,
        update_treasury,
        burn_tokens,
        output.set(Int(1))  # True
    ])

@treasury_app.external
def complete_asset_funding(
    asset_id: abi.Uint64,
    *,
    output: abi.Bool
) -> Expr:
    """Mark an asset as completed after funding process"""
    
    # Verify the caller is authorized (admin or asset registry)
    is_authorized = Or(
        Txn.sender() == treasury_app.state.admin_address.get(),
        Txn.sender() == App.globalGet(treasury_app.state.asset_registry_id.get(), Bytes("admin"))
    )
    
    assert_authorized = Assert(
        is_authorized,
        comment="Only admin or asset registry can complete asset funding"
    )
    
    # Verify the asset has an allocation
    asset_allocation_exists = treasury_app.state.asset_allocations[asset_id].exists()
    
    assert_allocation_exists = Assert(
        asset_allocation_exists,
        comment="Asset has no allocation"
    )
    
    # Verify the asset is in "funded" status
    asset_status = treasury_app.state.asset_status[asset_id].get()
    
    assert_correct_status = Assert(
        asset_status == Bytes("funded"),
        comment="Asset is not in funded status"
    )
    
    # Update asset status
    update_status = treasury_app.state.asset_status[asset_id].set(Bytes("completed"))
    
    return Seq([
        assert_authorized,
        assert_allocation_exists,
        assert_correct_status,
        update_status,
        output.set(Int(1))  # True
    ])

@treasury_app.external
def update_reserve_attestation(
    current_balance: abi.Uint64,
    *,
    output: abi.Bool
) -> Expr:
    """Update the stablecoin reserve attestation"""
    
    # Only allow the admin to update attestation
    assert_admin = Assert(
        Txn.sender() == treasury_app.state.admin_address.get(),
        comment="Only admin can update attestation"
    )
    
    # Update attestation information
    update_attestation = Seq([
        treasury_app.state.reserve_balance.set(current_balance.get()),
        treasury_app.state.last_attestation_timestamp.set(Global.latest_timestamp())
    ])
    
    return Seq([
        assert_admin,
        update_attestation,
        output.set(Int(1))  # True
    ])

@treasury_app.external
def pause_treasury_operations(
    pause_state: abi.Bool,
    *,
    output: abi.Bool
) -> Expr:
    """Pause or unpause treasury operations"""
    
    # Only allow the admin to pause/unpause
    assert_admin = Assert(
        Txn.sender() == treasury_app.state.admin_address.get(),
        comment="Only admin can pause/unpause"
    )
    
    # Update pause state
    update_pause = treasury_app.state.operations_paused.set(
        If(pause_state.get(), Int(1), Int(0))
    )
    
    return Seq([
        assert_admin,
        update_pause,
        output.set(Int(1))  # True
    ])

@treasury_app.external
def change_admin(
    new_admin: abi.Address,
    *,
    output: abi.Bool
) -> Expr:
    """Change the admin address"""
    
    # Only allow the current admin to change admin
    assert_admin = Assert(
        Txn.sender() == treasury_app.state.admin_address.get(),
        comment="Only current admin can change admin"
    )
    
    # Update admin address
    update_admin = treasury_app.state.admin_address.set(new_admin.get())
    
    return Seq([
        assert_admin,
        update_admin,
        output.set(Int(1))  # True
    ])

@treasury_app.external(read_only=True)
def get_treasury_info(
    *,
    output: abi.String
) -> Expr:
    """Get treasury information"""
    
    # Calculate remaining capacity
    remaining_capacity = treasury_app.state.total_capacity.get() - (
        treasury_app.state.current_allocated.get() + treasury_app.state.current_reserved.get()
    )
    
    # Build the treasury information string
    treasury_info = Concat(
        Bytes("Treasury Capacity: "), Int2Str(treasury_app.state.total_capacity.get()),
        Bytes(" | Allocated: "), Int2Str(treasury_app.state.current_allocated.get()),
        Bytes(" | Reserved: "), Int2Str(treasury_app.state.current_reserved.get()),
        Bytes(" | Remaining: "), Int2Str(remaining_capacity),
        Bytes(" | Reserve Balance: "), Int2Str(treasury_app.state.reserve_balance.get()),
        Bytes(" | Last Attestation: "), Int2Str(treasury_app.state.last_attestation_timestamp.get()),
        Bytes(" | Status: "), If(
            treasury_app.state.operations_paused.get() == Int(1),
            Bytes("Paused"),
            Bytes("Active")
        )
    )
    
    return output.set(treasury_info)

@treasury_app.external(read_only=True)
def get_asset_allocation(
    asset_id: abi.Uint64,
    *,
    output: abi.String
) -> Expr:
    """Get allocation information for a specific asset"""
    
    # Check if the asset has an allocation
    allocation_exists = treasury_app.state.asset_allocations[asset_id].exists()
    
    # Get allocation amount and status if exists
    allocation_amount = treasury_app.state.asset_allocations[asset_id].get()
    asset_status = treasury_app.state.asset_status[asset_id].get()
    
    # Build the allocation information string
    allocation_info = If(
        allocation_exists,
        Concat(
            Bytes("Asset ID: "), Int2Str(asset_id.get()),
            Bytes(" | Allocation: "), Int2Str(allocation_amount),
            Bytes(" | Status: "), asset_status
        ),
        Bytes("No allocation found for this asset")
    )
    
    return output.set(allocation_info)

# Helper function to convert integer to string
def Int2Str(i: Expr) -> Expr:
    """Convert an integer expression to a string expression using Itob."""
    return Extract(Itob(i), Int(0), Int(8))

if __name__ == "__main__":
    # Compile and export the app
    app_spec = treasury_app.build()
    app_spec.export("artifacts/treasury")