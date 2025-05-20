# ~/Desktop/boli/projects/boli/smart_contracts/disaster_recovery/contract.py

from pyteal import *
from beaker import *
from beaker.lib.storage import BoxMapping

from smart_contracts.contract_base import BaseState, ContractBase

# Implement a proper Int2Str function using Itob and other PyTeal operations
def Int2Str(i: Expr) -> Expr:
    """Convert an integer expression to a string expression using Itob."""
    # Convert int to bytes (big-endian) and extract only the needed part
    return Extract(Itob(i), Int(0), Int(8))

class DisasterRecoveryState(BaseState):
    """State class for Disaster Recovery Bond assets"""
    
    # Bond specific state variables
    bond_name = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Name of the bond"
    )
    
    bond_type = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Type of disaster recovery bond"
    )
    
    trigger_type = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Type of trigger event (e.g., hurricane, flood)"
    )
    
    trigger_threshold = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Threshold value that triggers the bond payout"
    )
    
    coverage_amount = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Amount to be paid out when triggered"
    )
    
    maturity_date = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Maturity date of the bond"
    )
    
    interest_rate = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Interest rate in basis points (1/100 of a percent)"
    )
    
    issue_date = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Issuance date of the bond"
    )
    
    is_triggered = GlobalStateValue(
        stack_type=TealType.uint64,  # 0 = false, 1 = true
        descr="Whether the bond has been triggered"
    )
    
    oracle_provider = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Provider of the oracle data"
    )
    
    total_bond_value = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Total value of the bond"
    )
    
    bondholders_count = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Number of bondholders"
    )
    
    # Map to track bondholders and their investments
    # This will be implemented using BoxMapping
    # The key needs to be an address (bytes), and the value needs to be stored as bytes too
    # We'll convert uint64 to bytes when storing
    bondholders = BoxMapping(
        key_type=abi.Address,
        value_type=abi.Uint64,  # Using Uint64 ABI type
        prefix=Bytes("bondholders")
    )

disaster_recovery_app = Application(
    "DisasterRecoveryBondContract",
    descr="Implements climate event-triggered financing instruments for vulnerable regions",
    state=DisasterRecoveryState()
)

@disaster_recovery_app.create
def create():
    """Initialize the app - basic setup only"""
    return Approve()

# ADDED: BOLI configuration method
@disaster_recovery_app.external
def configure_boli_integration(
    asset_registry_id: abi.Uint64,
    treasury_app_id: abi.Uint64,
    *,
    output: abi.Bool
) -> Expr:
    """Configure the contract with BOLI integration"""
    
    # Only allow the creator to configure
    assert_creator = ContractBase.assert_sender_is_creator(disaster_recovery_app)
    
    # Store configuration
    store_config = Seq([
        disaster_recovery_app.state.asset_registry_id.set(asset_registry_id.get()),
        disaster_recovery_app.state.treasury_app_id.set(treasury_app_id.get())
    ])
    
    return Seq([
        assert_creator,
        store_config,
        output.set(Int(1))  # True
    ])

# MODIFIED: Added BOLI integration
@disaster_recovery_app.external
def create_bond(
    name: abi.String,
    unit_name: abi.String,
    bond_type: abi.String,
    trigger_type: abi.String,
    trigger_threshold: abi.Uint64,
    coverage_amount: abi.Uint64,
    maturity_date: abi.Uint64,
    interest_rate: abi.Uint64,
    jurisdiction_code: abi.String,
    geolocation: abi.String,
    oracle_provider: abi.String,
    bond_document_hash: abi.String,
    total_bond_value: abi.Uint64,
    boli_allocation: abi.Uint64,  # NEW: BOLI allocation amount
    *,
    output: abi.Uint64
) -> Expr:
    """Creates a new disaster recovery bond with BOLI allocation"""
    
    # Only allow the creator to create bonds
    assert_creator = ContractBase.assert_sender_is_creator(disaster_recovery_app)
    
    # Validate inputs
    validate_maturity = Assert(
        maturity_date.get() > Global.latest_timestamp(),
        comment="Maturity date must be in the future"
    )
    
    validate_value = Assert(
        total_bond_value.get() >= coverage_amount.get(),
        comment="Bond value must cover trigger amount"
    )
    
    # Prepare note with bond details
    note = Concat(
        Bytes("Boli Disaster Recovery Bond: "),
        bond_type.get(),
        Bytes(" | Trigger: "),
        trigger_type.get(),
        Bytes(" | Oracle: "),
        oracle_provider.get()
    )
    
    # Create the bond tokens
    bond_supply = Int(1000000)  # 1 million units for divisibility
    create_token = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetConfig,
            TxnField.config_asset_total: bond_supply,
            TxnField.config_asset_decimals: Int(6),  # 6 decimal places for bond fractions
            TxnField.config_asset_default_frozen: Int(0),
            TxnField.config_asset_manager: Global.current_application_address(),
            TxnField.config_asset_reserve: Txn.sender(),
            TxnField.config_asset_freeze: Global.current_application_address(),
            TxnField.config_asset_clawback: Global.current_application_address(),
            TxnField.config_asset_unit_name: unit_name.get(),
            TxnField.config_asset_name: name.get(),
            TxnField.config_asset_url: Concat(Bytes("ipfs://"), bond_document_hash.get()),
            TxnField.note: note
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Store the ASA ID
    asset_id = InnerTxn.created_asset_id()
    store_asset_id = disaster_recovery_app.state.asset_id.set(asset_id)
    
    # Store base asset information
    store_base_info = Seq([
        disaster_recovery_app.state.asset_creator.set(Txn.sender()),
        disaster_recovery_app.state.asset_type.set(Bytes("disaster-bond")),
        disaster_recovery_app.state.geolocation.set(geolocation.get()),
        disaster_recovery_app.state.metadata.set(bond_document_hash.get()),
        disaster_recovery_app.state.jurisdiction_code.set(jurisdiction_code.get()),
        disaster_recovery_app.state.compliance_status.set(Bytes("active")),
        disaster_recovery_app.state.last_updated.set(Global.latest_timestamp())
    ])
    
    # Store bond specific information
    store_bond_info = Seq([
        disaster_recovery_app.state.bond_name.set(name.get()),
        disaster_recovery_app.state.bond_type.set(bond_type.get()),
        disaster_recovery_app.state.trigger_type.set(trigger_type.get()),
        disaster_recovery_app.state.trigger_threshold.set(trigger_threshold.get()),
        disaster_recovery_app.state.coverage_amount.set(coverage_amount.get()),
        disaster_recovery_app.state.maturity_date.set(maturity_date.get()),
        disaster_recovery_app.state.interest_rate.set(interest_rate.get()),
        disaster_recovery_app.state.issue_date.set(Global.latest_timestamp()),
        disaster_recovery_app.state.is_triggered.set(Int(0)),  # False
        disaster_recovery_app.state.oracle_provider.set(oracle_provider.get()),
        disaster_recovery_app.state.total_bond_value.set(total_bond_value.get()),
        disaster_recovery_app.state.bondholders_count.set(Int(0))
    ])
    
    # NEW: Register with Asset Registry for BOLI allocation
    register_for_boli = ContractBase.register_with_asset_registry(
        disaster_recovery_app,
        name.get(),
        Bytes("disaster-bond"),
        jurisdiction_code.get(),
        boli_allocation.get()
    )
    
    return Seq([
        assert_creator,
        validate_maturity,
        validate_value,
        create_token,
        store_asset_id,
        store_base_info,
        store_bond_info,
        # Only register with BOLI if allocation amount is greater than 0
        If(
            boli_allocation.get() > Int(0),
            register_for_boli,
            Seq([])  # No-op if no BOLI allocation
        ),
        output.set(asset_id)
    ])

# ADDED: Update funding status method
@disaster_recovery_app.external
def update_funding_status(
    new_status: abi.String,
    *,
    output: abi.Bool
) -> Expr:
    """Updates the bond funding status"""
    
    # Only allow the creator to update status
    is_authorized = Txn.sender() == Global.creator_address()
    
    assert_authorized = Assert(
        is_authorized,
        comment="Only creator or Asset Registry can update status"
    )
    
    # Update the investment status
    update_status = ContractBase.update_investment_status(
        disaster_recovery_app,
        new_status.get()
    )
    
    return Seq([
        assert_authorized,
        update_status,
        output.set(Int(1))  # True
    ])

# ADDED: Revenue reporting method (for interest payments on non-triggered bonds)
@disaster_recovery_app.external
def report_bond_interest(
    bond_asset_id: abi.Uint64,
    interest_amount: abi.Uint64,
    interest_period: abi.String,
    *,
    output: abi.Bool
) -> Expr:
    """Reports bond interest for distribution to bondholders"""
    
    # Only allow the creator to report interest
    assert_creator = ContractBase.assert_sender_is_creator(disaster_recovery_app)
    
    # Verify the bond is in active status and not triggered
    is_active_not_triggered = And(
        disaster_recovery_app.state.investment_status.get() == Bytes("active"),
        disaster_recovery_app.state.is_triggered.get() == Int(0)
    )
    
    assert_active = Assert(
        is_active_not_triggered,
        comment="Bond is not in active status or has been triggered"
    )
    
    # Create distribution note
    distribution_note = Concat(
        Bytes("Bond Interest: "),
        Int2Str(interest_amount.get()),
        Bytes(" | Period: "),
        interest_period.get()
    )
    
    # Distribute interest to bondholders
    distribute = ContractBase.distribute_revenue(
        disaster_recovery_app,
        interest_amount.get(),
        Bytes("bond-interest"),
        distribution_note
    )
    
    return Seq([
        assert_creator,
        assert_active,
        distribute,
        output.set(Int(1))  # True
    ])

@disaster_recovery_app.external
def invest_in_bond(
    bond_asset_id: abi.Uint64,
    investment_amount: abi.Uint64
) -> Expr:
    """Invest in a bond"""
    
    # Ensure the bond exists and matches our records
    asset_id_check = Assert(
        disaster_recovery_app.state.asset_id.get() == bond_asset_id.get(),
        comment="Bond ID mismatch"
    )
    
    # Check bond status
    check_active = Assert(
        disaster_recovery_app.state.compliance_status.get() == Bytes("active"),
        comment="Bond is not active"
    )
    
    check_not_triggered = Assert(
        disaster_recovery_app.state.is_triggered.get() == Int(0),
        comment="Bond has been triggered"
    )
    
    check_maturity = Assert(
        Global.latest_timestamp() < disaster_recovery_app.state.maturity_date.get(),
        comment="Bond has matured"
    )
    
    # Get investor address
    investor = Txn.sender()
    
    # Calculate bond tokens to issue based on investment amount
    # Formula: (investment / totalBondValue) * totalSupply
    total_supply = Int(1000000 * 1000000)  # 1M tokens with 6 decimal places
    ratio = Div(
        Mul(investment_amount.get(), Int(1000000)),
        disaster_recovery_app.state.total_bond_value.get()
    )
    tokens_to_issue = Div(
        Mul(ratio, total_supply),
        Int(1000000)
    )
    
    # Issue bond tokens to investor
    asset_transfer = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: bond_asset_id.get(),
            TxnField.asset_amount: tokens_to_issue,
            TxnField.asset_receiver: investor,
            TxnField.asset_sender: disaster_recovery_app.state.asset_creator.get()
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Record bondholder and investment
    update_bondholder_count = If(
        Not(disaster_recovery_app.state.bondholders[investor].exists()),
        disaster_recovery_app.state.bondholders_count.set(
            disaster_recovery_app.state.bondholders_count.get() + Int(1)
        ),
        Seq([])  # No-op if bondholder already exists
    )
    
    # Create a Uint64 ABI value to store the investment amount
    investment_abi = abi.Uint64()
    
    # Handle updating the investment amount using ABI compatible value
    handle_investment = Seq([
        # Set the ABI value to the investment amount
        investment_abi.set(investment_amount.get()),
        
        # Update the bondholder's investment using ABI format
        disaster_recovery_app.state.bondholders[investor].set(investment_abi)
    ])
    
    return Seq([
        asset_id_check,
        check_active,
        check_not_triggered,
        check_maturity,
        asset_transfer,
        update_bondholder_count,
        handle_investment
    ])

@disaster_recovery_app.external
def process_trigger_event(
    bond_asset_id: abi.Uint64,
    oracle_data_hash: abi.String,
    oracle_value: abi.Uint64,
    oracle_timestamp: abi.Uint64,
    *,
    output: abi.Bool
) -> Expr:
    """Process oracle data to determine if bond trigger conditions are met"""
    
    # Ensure the bond exists and matches our records
    asset_id_check = Assert(
        disaster_recovery_app.state.asset_id.get() == bond_asset_id.get(),
        comment="Bond ID mismatch"
    )
    
    # Only allow the contract creator or authorized oracle to trigger
    assert_creator = ContractBase.assert_sender_is_creator(disaster_recovery_app)
    
    # Check that bond hasn't already been triggered
    check_not_triggered = Assert(
        disaster_recovery_app.state.is_triggered.get() == Int(0),
        comment="Bond already triggered"
    )
    
    check_active = Assert(
        disaster_recovery_app.state.compliance_status.get() == Bytes("active"),
        comment="Bond is not active"
    )
    
    # Check if measured value exceeds threshold
    update_triggered = If(
        oracle_value.get() >= disaster_recovery_app.state.trigger_threshold.get(),
        Seq([
            # Trigger the bond
            disaster_recovery_app.state.is_triggered.set(Int(1)),  # True
            disaster_recovery_app.state.last_updated.set(Global.latest_timestamp()),
            
            # Update metadata with oracle data
            disaster_recovery_app.state.metadata.set(
                Concat(
                    disaster_recovery_app.state.metadata.get(),
                    Bytes("|trigger:"),
                    oracle_data_hash.get(),
                    Bytes("|value:"),
                    Int2Str(oracle_value.get()),
                    Bytes("|time:"),
                    Int2Str(oracle_timestamp.get())
                )
            ),
            
            output.set(Int(1))  # True
        ]),
        output.set(Int(0))  # False
    )
    
    return Seq([
        asset_id_check,
        assert_creator,
        check_not_triggered,
        check_active,
        update_triggered
    ])

@disaster_recovery_app.external
def process_bond_payout(
    bond_asset_id: abi.Uint64,
    beneficiary: abi.Address
) -> Expr:
    """Process payout for a triggered bond"""
    
    # Ensure the bond exists and matches our records
    asset_id_check = Assert(
        disaster_recovery_app.state.asset_id.get() == bond_asset_id.get(),
        comment="Bond ID mismatch"
    )
    
    # Check that bond has been triggered
    check_triggered = Assert(
        disaster_recovery_app.state.is_triggered.get() == Int(1),
        comment="Bond not triggered"
    )
    
    # Only allow the contract creator to process payouts
    assert_creator = ContractBase.assert_sender_is_creator(disaster_recovery_app)
    
    # Send payout to beneficiary
    send_payout = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.Payment,
            TxnField.amount: disaster_recovery_app.state.coverage_amount.get(),
            TxnField.receiver: beneficiary.get(),
            TxnField.sender: Global.current_application_address()
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Mark bond as paid
    update_status = disaster_recovery_app.state.compliance_status.set(Bytes("paid"))
    update_timestamp = disaster_recovery_app.state.last_updated.set(Global.latest_timestamp())
    
    return Seq([
        asset_id_check,
        check_triggered,
        assert_creator,
        send_payout,
        update_status,
        update_timestamp
    ])

@disaster_recovery_app.external
def process_bond_maturity(
    bond_asset_id: abi.Uint64
) -> Expr:
    """Process bond maturity payment"""
    
    # Ensure the bond exists and matches our records
    asset_id_check = Assert(
        disaster_recovery_app.state.asset_id.get() == bond_asset_id.get(),
        comment="Bond ID mismatch"
    )
    
    # Check if bond has matured
    check_maturity = Assert(
        Global.latest_timestamp() >= disaster_recovery_app.state.maturity_date.get(),
        comment="Bond has not matured yet"
    )
    
    # Only allow the contract creator to process maturity
    assert_creator = ContractBase.assert_sender_is_creator(disaster_recovery_app)
    
    # Update bond status
    update_status = If(
        disaster_recovery_app.state.is_triggered.get() == Int(1),
        # Bond was already triggered and paid out
        disaster_recovery_app.state.compliance_status.set(Bytes("completed")),
        # Bond matured without trigger - return principal with interest to bondholders
        disaster_recovery_app.state.compliance_status.set(Bytes("matured"))
    )
    
    update_timestamp = disaster_recovery_app.state.last_updated.set(Global.latest_timestamp())
    
    return Seq([
        asset_id_check,
        check_maturity,
        assert_creator,
        update_status,
        update_timestamp
    ])

@disaster_recovery_app.external(read_only=True)
def get_bond_status(
    bond_asset_id: abi.Uint64,
    *,
    output: abi.String
) -> Expr:
    """Get bond status information"""
    
    # Ensure the bond exists and matches our records
    asset_id_check = Assert(
        disaster_recovery_app.state.asset_id.get() == bond_asset_id.get(),
        comment="Bond ID mismatch"
    )
    
    # Build the status string
    status = Concat(
        Bytes("Bond ID: "), Int2Str(disaster_recovery_app.state.asset_id.get()),
        Bytes(" | Name: "), disaster_recovery_app.state.bond_name.get(),
        Bytes(" | Type: "), disaster_recovery_app.state.bond_type.get(),
        Bytes(" | Status: "), disaster_recovery_app.state.compliance_status.get(),
        Bytes(" | Triggered: "), If(
            disaster_recovery_app.state.is_triggered.get() == Int(1),
            Bytes("Yes"),
            Bytes("No")
        ),
        Bytes(" | Maturity: "), Int2Str(disaster_recovery_app.state.maturity_date.get()),
        Bytes(" | Investors: "), Int2Str(disaster_recovery_app.state.bondholders_count.get()),
        Bytes(" | Total Value: "), Int2Str(disaster_recovery_app.state.total_bond_value.get()),
        Bytes(" | Coverage: "), Int2Str(disaster_recovery_app.state.coverage_amount.get()),
        Bytes(" | Investment Status: "), disaster_recovery_app.state.investment_status.get()
    )
    
    return Seq([
        asset_id_check,
        output.set(status)
    ])

@disaster_recovery_app.external
def claim_bond_value(
    bond_asset_id: abi.Uint64,
    *,
    output: abi.Uint64
) -> Expr:
    """Allow bondholder to claim matured bond value with interest"""
    
    # Ensure the bond exists and matches our records
    asset_id_check = Assert(
        disaster_recovery_app.state.asset_id.get() == bond_asset_id.get(),
        comment="Bond ID mismatch"
    )
    
    # Check bond status
    check_matured = Assert(
        disaster_recovery_app.state.compliance_status.get() == Bytes("matured"),
        comment="Bond is not matured or has been paid"
    )
    
    check_not_triggered = Assert(
        disaster_recovery_app.state.is_triggered.get() == Int(0),
        comment="Triggered bonds are paid to beneficiary"
    )
    
    # Get investor address
    investor = Txn.sender()
    
    # Check if investor is a bondholder
    check_bondholder = Assert(
        disaster_recovery_app.state.bondholders[investor].exists(),
        comment="Not a bondholder"
    )
    
    # Create a temporary ABI value to hold the investment
    investment_abi = abi.Uint64()
    
    # Get the investment amount from box storage
    get_investment = disaster_recovery_app.state.bondholders[investor].store_into(investment_abi)
    
    # Calculate interest based on holding period and interest rate
    # interestRate is in basis points (1/100 of a percent)
    holding_period_seconds = disaster_recovery_app.state.maturity_date.get() - disaster_recovery_app.state.issue_date.get()
    
    # Convert to years (approximating 1 year = 31536000 seconds)
    # Using a scaled calculation for precision
    holding_period_years_scaled = Div(
        Mul(holding_period_seconds, Int(10000)),
        Int(31536000)
    )
    
    interest_rate_decimal = Div(
        disaster_recovery_app.state.interest_rate.get(),
        Int(10000)
    )
    
    # Calculate interest: principal * rate * time
    # Using scaled calculations for precision
    interest_amount = Div(
        Mul(
            Mul(
                Mul(investment_abi.get(), interest_rate_decimal),
                holding_period_years_scaled
            ),
            Int(10000)
        ),
        Int(10000)
    )
    
    # Calculate total payout
    total_payout = investment_abi.get() + interest_amount
    
    # Send principal plus interest to investor
    send_payout = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.Payment,
            TxnField.amount: total_payout,
            TxnField.receiver: investor,
            TxnField.sender: Global.current_application_address()
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Remove bondholder from records - use Pop to discard the return value from delete()
    remove_bondholder = Pop(disaster_recovery_app.state.bondholders[investor].delete())
    update_bondholder_count = disaster_recovery_app.state.bondholders_count.set(
        disaster_recovery_app.state.bondholders_count.get() - Int(1)
    )
    
    return Seq([
        asset_id_check,
        check_matured,
        check_not_triggered,
        check_bondholder,
        get_investment,
        send_payout,
        remove_bondholder,
        update_bondholder_count,
        output.set(total_payout)
    ])

if __name__ == "__main__":
    # Compile and export the app
    app_spec = disaster_recovery_app.build()
    app_spec.export("artifacts/disaster_recovery")