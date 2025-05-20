# ~/Desktop/boli/projects/boli/smart_contracts/revenue_distribution/contract.py

from pyteal import *
from beaker import *
from beaker.lib.storage import BoxMapping

class RevenueDistributionState:
    """State class for Revenue Distribution contract"""
    
    # Configuration
    boli_token_id = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Asset ID of the BOLI token"
    )
    
    asset_registry_id = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="App ID of the asset registry"
    )
    
    # Operations and security
    admin_address = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Address of the admin"
    )
    
    operations_paused = GlobalStateValue(
        stack_type=TealType.uint64,  # 0 = false, 1 = true
        descr="Whether distribution operations are paused"
    )
    
    # Revenue tracking
    distribution_count = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Total number of distributions processed"
    )
    
    class DistributionInfo(abi.NamedTuple):
        asset_id: abi.Uint64
        total_amount: abi.Uint64
        distribution_date: abi.Uint64
        status: abi.String
        distribution_type: abi.String
        note: abi.String
    
    # Store distributions by ID
    distributions = BoxMapping(
        key_type=abi.Uint64,  # Distribution ID
        value_type=DistributionInfo,
        prefix=Bytes("dist")
    )
    
    # Track distributions by asset
    asset_distributions = BoxMapping(
        key_type=abi.Uint64,  # Asset ID
        value_type=abi.DynamicArray[abi.Uint64],  # Array of distribution IDs
        prefix=Bytes("adist")
    )
    
    # Track investor token balances for an asset
    investor_balances = BoxMapping(
        key_type=abi.Tuple2[abi.Address, abi.Uint64],  # (Investor, Asset ID)
        value_type=abi.Uint64,  # Token balance
        prefix=Bytes("bal")
    )
    
    # Store total tokens allocated for each asset
    asset_total_tokens = BoxMapping(
        key_type=abi.Uint64,  # Asset ID
        value_type=abi.Uint64,  # Total tokens
        prefix=Bytes("total")
    )

revenue_distribution_app = Application(
    "RevenueDistribution",
    descr="Manages revenue distribution for BOLI assets",
    state=RevenueDistributionState()
)

@revenue_distribution_app.create
def create():
    """Initialize the Revenue Distribution contract"""
    return Seq([
        revenue_distribution_app.state.admin_address.set(Global.creator_address()),
        revenue_distribution_app.state.operations_paused.set(Int(0)),  # Not paused initially
        revenue_distribution_app.state.distribution_count.set(Int(0)),
        Approve()
    ])

@revenue_distribution_app.external
def configure_distribution(
    boli_token_id: abi.Uint64,
    asset_registry_id: abi.Uint64,
    *,
    output: abi.Bool
) -> Expr:
    """Configure the revenue distribution with token and registry information"""
    
    # Only allow the admin to configure
    assert_admin = Assert(
        Txn.sender() == revenue_distribution_app.state.admin_address.get(),
        comment="Only admin can configure distribution"
    )
    
    # Store configuration
    store_config = Seq([
        revenue_distribution_app.state.boli_token_id.set(boli_token_id.get()),
        revenue_distribution_app.state.asset_registry_id.set(asset_registry_id.get())
    ])
    
    return Seq([
        assert_admin,
        store_config,
        output.set(Int(1))  # True
    ])

@revenue_distribution_app.external
def register_investor_balance(
    investor: abi.Address,
    asset_id: abi.Uint64,
    token_balance: abi.Uint64,
    *,
    output: abi.Bool
) -> Expr:
    """Register an investor's token balance for a specific asset"""
    
    # Only allow the admin to register balances
    assert_admin = Assert(
        Txn.sender() == revenue_distribution_app.state.admin_address.get(),
        comment="Only admin can register balances"
    )
    
    # Check that operations are not paused
    assert_not_paused = Assert(
        revenue_distribution_app.state.operations_paused.get() == Int(0),
        comment="Distribution operations are paused"
    )
    
    # Create the investor-asset key
    investor_asset_key = (investor.get(), asset_id.get())
    
    # Store the balance
    store_balance = revenue_distribution_app.state.investor_balances[investor_asset_key].set(token_balance.get())
    
    # Update total tokens for the asset
    update_total = Seq([
        # If this is the first balance for this asset, initialize the total
        If(
            Not(revenue_distribution_app.state.asset_total_tokens[asset_id].exists()),
            revenue_distribution_app.state.asset_total_tokens[asset_id].set(Int(0)),
            Seq([])  # No-op if already exists
        ),
        
        # If the investor already has a balance, subtract it from the total before adding the new one
        If(
            revenue_distribution_app.state.investor_balances[investor_asset_key].exists(),
            revenue_distribution_app.state.asset_total_tokens[asset_id].set(
                revenue_distribution_app.state.asset_total_tokens[asset_id].get() - 
                revenue_distribution_app.state.investor_balances[investor_asset_key].get() +
                token_balance.get()
            ),
            # If this is a new balance, just add it to the total
            revenue_distribution_app.state.asset_total_tokens[asset_id].set(
                revenue_distribution_app.state.asset_total_tokens[asset_id].get() + token_balance.get()
            )
        )
    ])
    
    return Seq([
        assert_admin,
        assert_not_paused,
        store_balance,
        update_total,
        output.set(Int(1))  # True
    ])

@revenue_distribution_app.external
def create_distribution(
    asset_id: abi.Uint64,
    total_amount: abi.Uint64,
    distribution_type: abi.String,
    note: abi.String,
    *,
    output: abi.Uint64
) -> Expr:
    """Create a new revenue distribution for an asset"""
    
    # Only allow the admin to create distributions
    assert_admin = Assert(
        Txn.sender() == revenue_distribution_app.state.admin_address.get(),
        comment="Only admin can create distributions"
    )
    
    # Check that operations are not paused
    assert_not_paused = Assert(
        revenue_distribution_app.state.operations_paused.get() == Int(0),
        comment="Distribution operations are paused"
    )
    
    # Verify the asset exists
    verify_asset = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.ApplicationCall,
            TxnField.application_id: revenue_distribution_app.state.asset_registry_id.get(),
            TxnField.on_completion: OnComplete.NoOp,
            TxnField.application_args: [
                Bytes("get_asset_details"),
                Itob(asset_id.get())
            ]
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Verify that there are tokens allocated for this asset
    assert_has_tokens = Assert(
        And(
            revenue_distribution_app.state.asset_total_tokens[asset_id].exists(),
            revenue_distribution_app.state.asset_total_tokens[asset_id].get() > Int(0)
        ),
        comment="Asset has no token allocations"
    )
    
    # Get the next distribution ID
    distribution_id = revenue_distribution_app.state.distribution_count.get() + Int(1)
    
    # Create the distribution record
    distribution_info = revenue_distribution_app.state.DistributionInfo()
    set_distribution_info = Seq([
        distribution_info.asset_id.set(asset_id.get()),
        distribution_info.total_amount.set(total_amount.get()),
        distribution_info.distribution_date.set(Global.latest_timestamp()),
        distribution_info.status.set(Bytes("created")),
        distribution_info.distribution_type.set(distribution_type.get()),
        distribution_info.note.set(note.get())
    ])
    
    # Store the distribution record
    store_distribution = revenue_distribution_app.state.distributions[Itob(distribution_id)].set(distribution_info)
    
    # Update asset distribution tracking
    update_asset_distributions = Seq([
        # If this is the first distribution for this asset, initialize the array
        If(
            Not(revenue_distribution_app.state.asset_distributions[asset_id].exists()),
            revenue_distribution_app.state.asset_distributions[asset_id].set([]),
            Seq([])  # No-op if already exists
        ),
        
        # Add this distribution ID to the asset's array
        revenue_distribution_app.state.asset_distributions[asset_id].set(
            Concat(
                revenue_distribution_app.state.asset_distributions[asset_id].get(),
                Itob(distribution_id)
            )
        )
    ])
    
    # Increment the distribution count
    increment_count = revenue_distribution_app.state.distribution_count.set(distribution_id)
    
    return Seq([
        assert_admin,
        assert_not_paused,
        verify_asset,
        assert_has_tokens,
        set_distribution_info,
        store_distribution,
        update_asset_distributions,
        increment_count,
        output.set(distribution_id)
    ])

@revenue_distribution_app.external
def process_distribution(
    distribution_id: abi.Uint64,
    *,
    output: abi.Bool
) -> Expr:
    """Process a revenue distribution, calculating and sending payments to investors"""
    
    # Only allow the admin to process distributions
    assert_admin = Assert(
        Txn.sender() == revenue_distribution_app.state.admin_address.get(),
        comment="Only admin can process distributions"
    )
    
    # Check that operations are not paused
    assert_not_paused = Assert(
        revenue_distribution_app.state.operations_paused.get() == Int(0),
        comment="Distribution operations are paused"
    )
    
    # Verify the distribution exists
    distribution_exists = revenue_distribution_app.state.distributions[Itob(distribution_id)].exists()
    assert_distribution_exists = Assert(
        distribution_exists,
        comment="Distribution does not exist"
    )
    
    # Get the distribution info
    distribution_info = revenue_distribution_app.state.distributions[Itob(distribution_id)].get()
    
    # Verify the distribution is in "created" status
    assert_correct_status = Assert(
        distribution_info.status.get() == Bytes("created"),
        comment="Distribution is not in created status"
    )
    
    # Update distribution status to "processing"
    distribution_info.status.set(Bytes("processing"))
    store_updated_distribution = revenue_distribution_app.state.distributions[Itob(distribution_id)].set(distribution_info)
    
    # In a real implementation, you would iterate through all investors with balance
    # and calculate their share of the distribution. Since PyTeal doesn't support
    # iteration over box storage, you would need to handle this differently,
    # potentially through batched operations or client-side processing.
    
    # For this example, we'll just mark the distribution as completed
    distribution_info.status.set(Bytes("completed"))
    complete_distribution = revenue_distribution_app.state.distributions[Itob(distribution_id)].set(distribution_info)
    
    # Note: In a production system, you would implement logic to:
    # 1. Identify all investors for the asset
    # 2. Calculate each investor's share based on their token balance
    # 3. Transfer the appropriate amount to each investor
    # 4. Update the distribution status as each step completes
    
    return Seq([
        assert_admin,
        assert_not_paused,
        assert_distribution_exists,
        assert_correct_status,
        store_updated_distribution,
        complete_distribution,
        output.set(Int(1))  # True
    ])

@revenue_distribution_app.external
def calculate_investor_share(
    distribution_id: abi.Uint64,
    investor: abi.Address,
    *,
    output: abi.Uint64
) -> Expr:
    """Calculate an investor's share of a distribution"""
    
    # Verify the distribution exists
    distribution_exists = revenue_distribution_app.state.distributions[Itob(distribution_id)].exists()
    assert_distribution_exists = Assert(
        distribution_exists,
        comment="Distribution does not exist"
    )
    
    # Get the distribution info
    distribution_info = revenue_distribution_app.state.distributions[Itob(distribution_id)].get()
    
    # Get the asset ID from the distribution
    asset_id = distribution_info.asset_id.get()
    
    # Create the investor-asset key
    investor_asset_key = (investor.get(), asset_id)
    
    # Verify the investor has a balance for this asset
    investor_has_balance = revenue_distribution_app.state.investor_balances[investor_asset_key].exists()
    assert_investor_has_balance = Assert(
        investor_has_balance,
        comment="Investor has no balance for this asset"
    )
    
    # Get the investor's balance and total tokens for the asset
    investor_balance = revenue_distribution_app.state.investor_balances[investor_asset_key].get()
    asset_total = revenue_distribution_app.state.asset_total_tokens[asset_id].get()
    
    # Calculate the investor's share
    # Formula: (investor_balance / asset_total) * total_distribution_amount
    # We multiply by 1,000,000 for precision, then divide at the end
    investor_share = Div(
        Mul(
            Mul(investor_balance, distribution_info.total_amount.get()),
            Int(1000000)
        ),
        Mul(asset_total, Int(1000000))
    )
    
    return Seq([
        assert_distribution_exists,
        assert_investor_has_balance,
        output.set(investor_share)
    ])

@revenue_distribution_app.external(read_only=True)
def get_distribution_details(
    distribution_id: abi.Uint64,
    *,
    output: abi.String
) -> Expr:
    """Get detailed information about a distribution"""
    
    # Check if the distribution exists
    distribution_exists = revenue_distribution_app.state.distributions[Itob(distribution_id)].exists()
    
    # Get distribution information if it exists
    distribution_info = revenue_distribution_app.state.distributions[Itob(distribution_id)].get()
    
    # Build the distribution information string
    distribution_details = If(
        distribution_exists,
        Concat(
            Bytes("Distribution ID: "), Int2Str(distribution_id.get()),
            Bytes(" | Asset ID: "), Int2Str(distribution_info.asset_id.get()),
            Bytes(" | Amount: "), Int2Str(distribution_info.total_amount.get()),
            Bytes(" | Date: "), Int2Str(distribution_info.distribution_date.get()),
            Bytes(" | Status: "), distribution_info.status.get(),
            Bytes(" | Type: "), distribution_info.distribution_type.get(),
            Bytes(" | Note: "), distribution_info.note.get()
        ),
        Bytes("Distribution not found")
    )
    
    return output.set(distribution_details)

@revenue_distribution_app.external(read_only=True)
def get_asset_distributions(
    asset_id: abi.Uint64,
    *,
    output: abi.String
) -> Expr:
    """Get all distributions for a specific asset"""
    
    # Check if the asset has any distributions
    distributions_exist = revenue_distribution_app.state.asset_distributions[asset_id].exists()
    
    # Build the distributions list
    distributions_list = If(
        distributions_exist,
        Concat(
            Bytes("Asset ID: "), Int2Str(asset_id.get()),
            Bytes(" | Distribution IDs: "), revenue_distribution_app.state.asset_distributions[asset_id].get()
            # In a production system, you would decode and format each distribution ID
        ),
        Bytes("Asset has no recorded distributions")
    )
    
    return output.set(distributions_list)

@revenue_distribution_app.external(read_only=True)
def get_investor_balance(
    investor: abi.Address,
    asset_id: abi.Uint64,
    *,
    output: abi.Uint64
) -> Expr:
    """Get an investor's token balance for a specific asset"""
    
    # Create the investor-asset key
    investor_asset_key = (investor.get(), asset_id.get())
    
    # Check if the investor has a balance for this asset
    balance_exists = revenue_distribution_app.state.investor_balances[investor_asset_key].exists()
    
    # Return the balance if it exists, otherwise 0
    return If(
        balance_exists,
        output.set(revenue_distribution_app.state.investor_balances[investor_asset_key].get()),
        output.set(Int(0))
    )

@revenue_distribution_app.external
def pause_distribution_operations(
    pause_state: abi.Bool,
    *,
    output: abi.Bool
) -> Expr:
    """Pause or unpause distribution operations"""
    
    # Only allow the admin to pause/unpause
    assert_admin = Assert(
        Txn.sender() == revenue_distribution_app.state.admin_address.get(),
        comment="Only admin can pause/unpause"
    )
    
    # Update pause state
    update_pause = revenue_distribution_app.state.operations_paused.set(
        If(pause_state.get(), Int(1), Int(0))
    )
    
    return Seq([
        assert_admin,
        update_pause,
        output.set(Int(1))  # True
    ])

@revenue_distribution_app.external
def change_admin(
    new_admin: abi.Address,
    *,
    output: abi.Bool
) -> Expr:
    """Change the admin address"""
    
    # Only allow the current admin to change admin
    assert_admin = Assert(
        Txn.sender() == revenue_distribution_app.state.admin_address.get(),
        comment="Only current admin can change admin"
    )
    
    # Update admin address
    update_admin = revenue_distribution_app.state.admin_address.set(new_admin.get())
    
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
    app_spec = revenue_distribution_app.build()
    app_spec.export("artifacts/revenue_distribution")