# ~/Desktop/boli/projects/boli/smart_contracts/investment_manager/contract.py

from pyteal import *
from beaker import *
from beaker.lib.storage import BoxMapping

class InvestmentManagerState:
    """State class for Investment Manager contract"""
    
    # Configuration
    boli_token_id = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Asset ID of the BOLI token"
    )
    
    treasury_app_id = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="App ID of the treasury management"
    )
    
    asset_registry_id = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="App ID of the asset registry"
    )
    
    stablecoin_id = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Asset ID of the stablecoin used for investments"
    )
    
    # Operations and security
    admin_address = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Address of the admin"
    )
    
    operations_paused = GlobalStateValue(
        stack_type=TealType.uint64,  # 0 = false, 1 = true
        descr="Whether investment operations are paused"
    )
    
    # Investment tracking
    class InvestmentInfo(abi.NamedTuple):
        investor: abi.Address
        asset_id: abi.Uint64
        amount: abi.Uint64
        timestamp: abi.Uint64
        status: abi.String
        transaction_id: abi.String
    
    # Track investments by ID
    investment_count = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Total number of investments processed"
    )
    
    investments = BoxMapping(
        key_type=abi.Uint64,  # Investment ID
        value_type=InvestmentInfo,
        prefix=Bytes("inv")
    )
    
    # Track investments by investor and asset
    investor_investments = BoxMapping(
        key_type=abi.Address,  # Investor address
        value_type=abi.DynamicArray[abi.Uint64],  # Array of investment IDs
        prefix=Bytes("usr")
    )
    
    asset_investments = BoxMapping(
        key_type=abi.Uint64,  # Asset ID
        value_type=abi.DynamicArray[abi.Uint64],  # Array of investment IDs
        prefix=Bytes("ast")
    )
    
    # Track asset funding progress
    asset_funding = BoxMapping(
        key_type=abi.Uint64,  # Asset ID
        value_type=abi.Uint64,  # Current funding amount
        prefix=Bytes("fund")
    )

investment_manager_app = Application(
    "InvestmentManager",
    descr="Manages investments in BOLI assets",
    state=InvestmentManagerState()
)

@investment_manager_app.create
def create():
    """Initialize the Investment Manager contract"""
    return Seq([
        investment_manager_app.state.admin_address.set(Global.creator_address()),
        investment_manager_app.state.operations_paused.set(Int(0)),  # Not paused initially
        investment_manager_app.state.investment_count.set(Int(0)),
        Approve()
    ])

@investment_manager_app.external
def configure_manager(
    boli_token_id: abi.Uint64,
    treasury_app_id: abi.Uint64,
    asset_registry_id: abi.Uint64,
    stablecoin_id: abi.Uint64,
    *,
    output: abi.Bool
) -> Expr:
    """Configure the investment manager with token and other app IDs"""
    
    # Only allow the admin to configure
    assert_admin = Assert(
        Txn.sender() == investment_manager_app.state.admin_address.get(),
        comment="Only admin can configure manager"
    )
    
    # Store configuration
    store_config = Seq([
        investment_manager_app.state.boli_token_id.set(boli_token_id.get()),
        investment_manager_app.state.treasury_app_id.set(treasury_app_id.get()),
        investment_manager_app.state.asset_registry_id.set(asset_registry_id.get()),
        investment_manager_app.state.stablecoin_id.set(stablecoin_id.get())
    ])
    
    return Seq([
        assert_admin,
        store_config,
        output.set(Int(1))  # True
    ])

@investment_manager_app.external
def process_investment(
    asset_id: abi.Uint64,
    investor: abi.Address,
    amount: abi.Uint64,
    stablecoin_txn_id: abi.String,
    *,
    output: abi.Uint64
) -> Expr:
    """Process an investment from an investor for a specific asset"""
    
    # Only allow the admin to process investments
    assert_admin = Assert(
        Txn.sender() == investment_manager_app.state.admin_address.get(),
        comment="Only admin can process investments"
    )
    
    # Check that operations are not paused
    assert_not_paused = Assert(
        investment_manager_app.state.operations_paused.get() == Int(0),
        comment="Investment operations are paused"
    )
    
    # Verify asset exists by calling the asset registry
    verify_asset = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.ApplicationCall,
            TxnField.application_id: investment_manager_app.state.asset_registry_id.get(),
            TxnField.on_completion: OnComplete.NoOp,
            TxnField.application_args: [
                Bytes("get_asset_details"),
                Itob(asset_id.get())
            ]
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Process stablecoin deposit with the treasury
    process_deposit = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.ApplicationCall,
            TxnField.application_id: investment_manager_app.state.treasury_app_id.get(),
            TxnField.on_completion: OnComplete.NoOp,
            TxnField.application_args: [
                Bytes("process_stablecoin_deposit"),
                Itob(amount.get()),
                Itob(asset_id.get()),
                stablecoin_txn_id.get()
            ]
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Allocate BOLI tokens to the investor
    allocate_tokens = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.ApplicationCall,
            TxnField.application_id: investment_manager_app.state.asset_registry_id.get(),
            TxnField.on_completion: OnComplete.NoOp,
            TxnField.application_args: [
                Bytes("allocate_tokens_to_investor"),
                Itob(asset_id.get()),
                investor.get(),
                Itob(amount.get())
            ]
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Update asset funding status
    update_funding = Seq([
        # If this is the first investment in this asset, initialize the funding amount
        If(
            Not(investment_manager_app.state.asset_funding[asset_id].exists()),
            investment_manager_app.state.asset_funding[asset_id].set(Int(0)),
            Seq([])  # No-op if already exists
        ),
        
        # Update the funding amount
        investment_manager_app.state.asset_funding[asset_id].set(
            investment_manager_app.state.asset_funding[asset_id].get() + amount.get()
        )
    ])
    
    # Get the next investment ID
    investment_id = investment_manager_app.state.investment_count.get() + Int(1)
    
    # Create the investment record
    investment_info = investment_manager_app.state.InvestmentInfo()
    set_investment_info = Seq([
        investment_info.investor.set(investor.get()),
        investment_info.asset_id.set(asset_id.get()),
        investment_info.amount.set(amount.get()),
        investment_info.timestamp.set(Global.latest_timestamp()),
        investment_info.status.set(Bytes("completed")),
        investment_info.transaction_id.set(stablecoin_txn_id.get())
    ])
    
    # Store the investment record
    store_investment = investment_manager_app.state.investments[Itob(investment_id)].set(investment_info)
    
    # Update investor investment tracking
    update_investor_investments = Seq([
        # If this is the first investment by this investor, initialize the array
        If(
            Not(investment_manager_app.state.investor_investments[investor].exists()),
            investment_manager_app.state.investor_investments[investor].set([]),
            Seq([])  # No-op if already exists
        ),
        
        # Add this investment ID to the investor's array
        investment_manager_app.state.investor_investments[investor].set(
            Concat(
                investment_manager_app.state.investor_investments[investor].get(),
                Itob(investment_id)
            )
        )
    ])
    
    # Update asset investment tracking
    update_asset_investments = Seq([
        # If this is the first investment in this asset, initialize the array
        If(
            Not(investment_manager_app.state.asset_investments[asset_id].exists()),
            investment_manager_app.state.asset_investments[asset_id].set([]),
            Seq([])  # No-op if already exists
        ),
        
        # Add this investment ID to the asset's array
        investment_manager_app.state.asset_investments[asset_id].set(
            Concat(
                investment_manager_app.state.asset_investments[asset_id].get(),
                Itob(investment_id)
            )
        )
    ])
    
    # Increment the investment count
    increment_count = investment_manager_app.state.investment_count.set(investment_id)
    
    # Check if asset is fully funded and update status if needed
    check_funding_complete = Seq([
        # In a production system, you would compare against the required funding amount
        # For this example, we'll use a fixed threshold of 1,000,000
        If(
            investment_manager_app.state.asset_funding[asset_id].get() >= Int(1000000),
            # Update the asset status to "funded"
            Seq(
                InnerTxnBuilder.Begin(),
                InnerTxnBuilder.SetFields({
                    TxnField.type_enum: TxnType.ApplicationCall,
                    TxnField.application_id: investment_manager_app.state.asset_registry_id.get(),
                    TxnField.on_completion: OnComplete.NoOp,
                    TxnField.application_args: [
                        Bytes("update_asset_status"),
                        Itob(asset_id.get()),
                        Bytes("funded")
                    ]
                }),
                InnerTxnBuilder.Submit()
            ),
            Seq([])  # No-op if not fully funded
        )
    ])
    
    return Seq([
        assert_admin,
        assert_not_paused,
        verify_asset,
        process_deposit,
        allocate_tokens,
        update_funding,
        set_investment_info,
        store_investment,
        update_investor_investments,
        update_asset_investments,
        increment_count,
        check_funding_complete,
        output.set(investment_id)
    ])

@investment_manager_app.external(read_only=True)
def get_investment_details(
    investment_id: abi.Uint64,
    *,
    output: abi.String
) -> Expr:
    """Get detailed information about an investment"""
    
    # Check if the investment exists
    investment_exists = investment_manager_app.state.investments[Itob(investment_id)].exists()
    
    # Get investment information if it exists
    investment_info = investment_manager_app.state.investments[Itob(investment_id)].get()
    
    # Build the investment information string
    investment_details = If(
        investment_exists,
        Concat(
            Bytes("Investment ID: "), Int2Str(investment_id.get()),
            Bytes(" | Investor: "), investment_info.investor.get(),
            Bytes(" | Asset ID: "), Int2Str(investment_info.asset_id.get()),
            Bytes(" | Amount: "), Int2Str(investment_info.amount.get()),
            Bytes(" | Timestamp: "), Int2Str(investment_info.timestamp.get()),
            Bytes(" | Status: "), investment_info.status.get()
        ),
        Bytes("Investment not found")
    )
    
    return output.set(investment_details)

@investment_manager_app.external(read_only=True)
def get_asset_funding_status(
    asset_id: abi.Uint64,
    *,
    output: abi.String
) -> Expr:
    """Get the funding status of an asset"""
    
    # Check if the asset has any funding
    funding_exists = investment_manager_app.state.asset_funding[asset_id].exists()
    
    # Get the funding amount if it exists
    funding_amount = investment_manager_app.state.asset_funding[asset_id].get()
    
    # Build the funding status string
    funding_status = If(
        funding_exists,
        Concat(
            Bytes("Asset ID: "), Int2Str(asset_id.get()),
            Bytes(" | Current Funding: "), Int2Str(funding_amount),
            # In a production system, you would compare against the required funding amount
            # For this example, we'll use a fixed threshold of 1,000,000
            Bytes(" | Progress: "), Int2Str(
                Div(
                    Mul(funding_amount, Int(100)),
                    Int(1000000)
                )
            ),
            Bytes("%")
        ),
        Bytes("Asset has no funding recorded")
    )
    
    return output.set(funding_status)

@investment_manager_app.external(read_only=True)
def get_investor_investments(
    investor: abi.Address,
    *,
    output: abi.String
) -> Expr:
    """Get all investments made by an investor"""
    
    # Check if the investor has any investments
    investments_exist = investment_manager_app.state.investor_investments[investor].exists()
    
    # Build the investments list
    investments_list = If(
        investments_exist,
        Concat(
            Bytes("Investor: "), investor.get(),
            Bytes(" | Investment IDs: "), investment_manager_app.state.investor_investments[investor].get()
            # In a production system, you would decode and format each investment ID
        ),
        Bytes("Investor has no recorded investments")
    )
    
    return output.set(investments_list)

@investment_manager_app.external
def pause_investment_operations(
    pause_state: abi.Bool,
    *,
    output: abi.Bool
) -> Expr:
    """Pause or unpause investment operations"""
    
    # Only allow the admin to pause/unpause
    assert_admin = Assert(
        Txn.sender() == investment_manager_app.state.admin_address.get(),
        comment="Only admin can pause/unpause"
    )
    
    # Update pause state
    update_pause = investment_manager_app.state.operations_paused.set(
        If(pause_state.get(), Int(1), Int(0))
    )
    
    return Seq([
        assert_admin,
        update_pause,
        output.set(Int(1))  # True
    ])

@investment_manager_app.external
def change_admin(
    new_admin: abi.Address,
    *,
    output: abi.Bool
) -> Expr:
    """Change the admin address"""
    
    # Only allow the current admin to change admin
    assert_admin = Assert(
        Txn.sender() == investment_manager_app.state.admin_address.get(),
        comment="Only current admin can change admin"
    )
    
    # Update admin address
    update_admin = investment_manager_app.state.admin_address.set(new_admin.get())
    
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
    app_spec = investment_manager_app.build()
    app_spec.export("artifacts/investment_manager")