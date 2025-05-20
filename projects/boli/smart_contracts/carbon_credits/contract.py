# ~/Desktop/boli/projects/boli/smart_contracts/carbon_credits/contract.py

from pyteal import *
from beaker import *
from beaker.lib.storage import BoxMapping

from smart_contracts.contract_base import BaseState, ContractBase

# Implement a proper Int2Str function using Itob and other PyTeal operations
def Int2Str(i: Expr) -> Expr:
    """Convert an integer expression to a string expression using Itob."""
    # Convert int to bytes (big-endian) and extract only the needed part
    return Extract(Itob(i), Int(0), Int(8))

class CarbonCreditState(BaseState):
    """State class for Carbon Credit assets"""
    
    # Carbon credit specific state variables
    credit_type = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Type of carbon credit"
    )
    
    carbon_registry = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Carbon registry name"
    )
    
    registry_project_id = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Project ID in the registry"
    )
    
    vintage_start = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Start date of the vintage period"
    )
    
    vintage_end = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="End date of the vintage period"
    )
    
    total_carbon_offset = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Total carbon offset in tonnes CO2"
    )
    
    remaining_offset = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Remaining carbon offset in tonnes CO2"
    )
    
    verification_methodology = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Verification methodology used"
    )
    
    verifier = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Name of the verifier"
    )

carbon_credit_app = Application(
    "CarbonCreditContract",
    descr="Implements the Verified Carbon Unit (VCU) Framework for climate initiatives",
    state=CarbonCreditState()
)

@carbon_credit_app.create
def create():
    """Initialize the app - basic setup only"""
    return Approve()

# ADDED: BOLI configuration method
@carbon_credit_app.external
def configure_boli_integration(
    asset_registry_id: abi.Uint64,
    treasury_app_id: abi.Uint64,
    *,
    output: abi.Bool
) -> Expr:
    """Configure the contract with BOLI integration"""
    
    # Only allow the creator to configure
    assert_creator = ContractBase.assert_sender_is_creator(carbon_credit_app)
    
    # Store configuration
    store_config = Seq([
        carbon_credit_app.state.asset_registry_id.set(asset_registry_id.get()),
        carbon_credit_app.state.treasury_app_id.set(treasury_app_id.get())
    ])
    
    return Seq([
        assert_creator,
        store_config,
        output.set(Int(1))  # True
    ])

# MODIFIED: Added BOLI integration
@carbon_credit_app.external
def create_carbon_project(
    name: abi.String,
    unit_name: abi.String,
    credit_type: abi.String,
    carbon_registry: abi.String,
    registry_project_id: abi.String,
    jurisdiction_code: abi.String,
    geolocation: abi.String,
    vintage_start: abi.Uint64,
    vintage_end: abi.Uint64,
    total_offset: abi.Uint64,
    verification_methodology: abi.String,
    monitoring_report_hash: abi.String,
    verifier: abi.String,
    boli_allocation: abi.Uint64,  # NEW: BOLI allocation amount
    *,
    output: abi.Uint64
) -> Expr:
    """Creates a new carbon credit project with BOLI allocation"""
    
    # Only allow the creator to create carbon credit projects
    assert_creator = ContractBase.assert_sender_is_creator(carbon_credit_app)
    
    # Validate inputs
    validate_vintage = Assert(
        vintage_start.get() < vintage_end.get(),
        comment="Invalid vintage period"
    )
    
    validate_offset = Assert(
        total_offset.get() > Int(0),
        comment="Total offset must be positive"
    )
    
    # Prepare note with carbon credit details
    note = Concat(
        Bytes("Boli Carbon Credit: "),
        credit_type.get(),
        Bytes(" | Registry: "),
        carbon_registry.get(),
        Bytes(" | Project ID: "),
        registry_project_id.get(),
        Bytes(" | Verified by: "),
        verifier.get()
    )
    
    # Create the carbon credit tokens (1 token = 1 tonne of CO2)
    # Fix inner transaction syntax by using Seq()
    create_token = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetConfig,
            TxnField.config_asset_total: total_offset.get(),
            TxnField.config_asset_decimals: Int(0),  # Non-divisible carbon credits
            TxnField.config_asset_default_frozen: Int(0),
            TxnField.config_asset_manager: Global.current_application_address(),
            TxnField.config_asset_reserve: Txn.sender(),
            TxnField.config_asset_freeze: Global.current_application_address(),
            TxnField.config_asset_clawback: Global.current_application_address(),
            TxnField.config_asset_unit_name: unit_name.get(),
            TxnField.config_asset_name: name.get(),
            TxnField.config_asset_url: Concat(Bytes("ipfs://"), monitoring_report_hash.get()),
            TxnField.note: note
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Store the ASA ID
    asset_id = InnerTxn.created_asset_id()
    store_asset_id = carbon_credit_app.state.asset_id.set(asset_id)
    
    # Store base asset information
    store_base_info = Seq([
        carbon_credit_app.state.asset_creator.set(Txn.sender()),
        carbon_credit_app.state.asset_type.set(Bytes("carbon-credit")),
        carbon_credit_app.state.geolocation.set(geolocation.get()),
        carbon_credit_app.state.metadata.set(monitoring_report_hash.get()),
        carbon_credit_app.state.jurisdiction_code.set(jurisdiction_code.get()),
        carbon_credit_app.state.compliance_status.set(Bytes("verified")),
        carbon_credit_app.state.last_updated.set(Global.latest_timestamp())
    ])
    
    # Store carbon credit specific information
    store_carbon_info = Seq([
        carbon_credit_app.state.credit_type.set(credit_type.get()),
        carbon_credit_app.state.carbon_registry.set(carbon_registry.get()),
        carbon_credit_app.state.registry_project_id.set(registry_project_id.get()),
        carbon_credit_app.state.vintage_start.set(vintage_start.get()),
        carbon_credit_app.state.vintage_end.set(vintage_end.get()),
        carbon_credit_app.state.total_carbon_offset.set(total_offset.get()),
        carbon_credit_app.state.remaining_offset.set(total_offset.get()),  # Initially all credits are available
        carbon_credit_app.state.verification_methodology.set(verification_methodology.get()),
        carbon_credit_app.state.verifier.set(verifier.get())
    ])
    
    # NEW: Register with Asset Registry for BOLI allocation
    register_for_boli = ContractBase.register_with_asset_registry(
        carbon_credit_app,
        name.get(),
        Bytes("carbon-credit"),
        jurisdiction_code.get(),
        boli_allocation.get()
    )
    
    return Seq([
        assert_creator,
        validate_vintage,
        validate_offset,
        create_token,
        store_asset_id,
        store_base_info,
        store_carbon_info,
        # Only register with BOLI if allocation amount is greater than 0
        If(
            boli_allocation.get() > Int(0),
            register_for_boli,
            Seq([])  # No-op if no BOLI allocation
        ),
        output.set(asset_id)
    ])

# ADDED: Update funding status method
@carbon_credit_app.external
def update_funding_status(
    new_status: abi.String,
    *,
    output: abi.Bool
) -> Expr:
    """Updates the carbon credit project funding status"""
    
    # Only allow the creator to update status
    is_authorized = Txn.sender() == Global.creator_address()
    
    assert_authorized = Assert(
        is_authorized,
        comment="Only creator or Asset Registry can update status"
    )
    
    # Update the investment status
    update_status = ContractBase.update_investment_status(
        carbon_credit_app,
        new_status.get()
    )
    
    return Seq([
        assert_authorized,
        update_status,
        output.set(Int(1))  # True
    ])

# ADDED: Revenue reporting method
@carbon_credit_app.external
def report_carbon_credit_revenue(
    revenue_amount: abi.Uint64,
    credit_sale_amount: abi.Uint64,
    buyer_type: abi.String,
    *,
    output: abi.Bool
) -> Expr:
    """Reports carbon credit sale revenue for distribution to token holders"""
    
    # Only allow the creator to report revenue
    assert_creator = ContractBase.assert_sender_is_creator(carbon_credit_app)
    
    # Verify the project is in active status
    assert_active = Assert(
        carbon_credit_app.state.investment_status.get() == Bytes("active"),
        comment="Carbon credit project is not in active status"
    )
    
    # Create distribution note
    distribution_note = Concat(
        Bytes("Carbon Credit Revenue: "),
        Int2Str(revenue_amount.get()),
        Bytes(" | Credits Sold: "),
        Int2Str(credit_sale_amount.get()),
        Bytes(" | Buyer Type: "),
        buyer_type.get()
    )
    
    # Distribute revenue to token holders
    distribute = ContractBase.distribute_revenue(
        carbon_credit_app,
        revenue_amount.get(),
        Bytes("carbon-credit-revenue"),
        distribution_note
    )
    
    return Seq([
        assert_creator,
        assert_active,
        distribute,
        output.set(Int(1))  # True
    ])

@carbon_credit_app.external
def issue_credits(
    credit_asset_id: abi.Uint64,
    recipient: abi.Address,
    amount: abi.Uint64
) -> Expr:
    """Issues carbon credits to a recipient"""
    
    # Ensure the carbon credit exists and matches our records
    asset_id_check = Assert(
        carbon_credit_app.state.asset_id.get() == credit_asset_id.get(),
        comment="Credit ID mismatch"
    )
    
    # Only allow the contract creator to issue credits
    assert_creator = ContractBase.assert_sender_is_creator(carbon_credit_app)
    
    # Check available credits
    check_credits = Assert(
        carbon_credit_app.state.remaining_offset.get() >= amount.get(),
        comment="Insufficient credits remaining"
    )
    
    # Execute the transfer from reserve
    asset_transfer = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: credit_asset_id.get(),
            TxnField.asset_amount: amount.get(),
            TxnField.asset_receiver: recipient.get(),
            TxnField.asset_sender: carbon_credit_app.state.asset_creator.get()
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Update remaining credits
    update_remaining = carbon_credit_app.state.remaining_offset.set(
        carbon_credit_app.state.remaining_offset.get() - amount.get()
    )
    
    update_timestamp = carbon_credit_app.state.last_updated.set(Global.latest_timestamp())
    
    return Seq([
        asset_id_check,
        assert_creator,
        check_credits,
        asset_transfer,
        update_remaining,
        update_timestamp
    ])

@carbon_credit_app.external
def retire_credits(
    credit_asset_id: abi.Uint64,
    amount: abi.Uint64,
    retirement_beneficiary: abi.String,
    retirement_reason: abi.String
) -> Expr:
    """Retires carbon credits (permanently removing them from circulation)"""
    
    # Ensure the carbon credit exists and matches our records
    asset_id_check = Assert(
        carbon_credit_app.state.asset_id.get() == credit_asset_id.get(),
        comment="Credit ID mismatch"
    )
    
    # Create retirement note
    retirement_note = Concat(
        Bytes("Retired: "),
        retirement_reason.get(),
        Bytes(" | Beneficiary: "),
        retirement_beneficiary.get(),
        Bytes(" | Date: "),
        Int2Str(Global.latest_timestamp())
    )
    
    # Execute the retirement by transferring to the contract address (used as retirement address)
    asset_transfer = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: credit_asset_id.get(),
            TxnField.asset_amount: amount.get(),
            TxnField.asset_receiver: Global.current_application_address(),
            TxnField.asset_sender: Txn.sender(),
            TxnField.note: retirement_note
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Update metadata with retirement information
    updated_metadata = Concat(
        carbon_credit_app.state.metadata.get(),
        Bytes("|retirement:"),
        retirement_beneficiary.get(),
        Bytes(":"),
        Int2Str(amount.get()),
        Bytes(":"),
        Int2Str(Global.latest_timestamp())
    )
    
    return Seq([
        asset_id_check,
        asset_transfer,
        carbon_credit_app.state.metadata.set(updated_metadata)
    ])

@carbon_credit_app.external
def add_verification_document(
    credit_asset_id: abi.Uint64,
    verifier_name: abi.String,
    verification_date: abi.Uint64,
    document_hash: abi.String
) -> Expr:
    """Adds verification document to existing carbon credits"""
    
    # Ensure the carbon credit exists and matches our records
    asset_id_check = Assert(
        carbon_credit_app.state.asset_id.get() == credit_asset_id.get(),
        comment="Credit ID mismatch"
    )
    
    # Only allow the contract creator to add documents
    assert_creator = ContractBase.assert_sender_is_creator(carbon_credit_app)
    
    # Update verifier information
    update_verifier = carbon_credit_app.state.verifier.set(verifier_name.get())
    
    # Update document reference
    updated_metadata = Concat(
        carbon_credit_app.state.metadata.get(),
        Bytes("|verification:"),
        document_hash.get(),
        Bytes(":"),
        Int2Str(verification_date.get())
    )
    
    return Seq([
        asset_id_check,
        assert_creator,
        update_verifier,
        carbon_credit_app.state.metadata.set(updated_metadata),
        carbon_credit_app.state.last_updated.set(Global.latest_timestamp())
    ])

@carbon_credit_app.external(read_only=True)
def get_carbon_credit_details(
    credit_asset_id: abi.Uint64,
    *,
    output: abi.String
) -> Expr:
    """Get detailed carbon credit information"""
    
    # Ensure the carbon credit exists and matches our records
    asset_id_check = Assert(
        carbon_credit_app.state.asset_id.get() == credit_asset_id.get(),
        comment="Credit ID mismatch"
    )
    
    # Build the carbon credit information string
    details = Concat(
        Bytes("Carbon Credit ID: "), Int2Str(carbon_credit_app.state.asset_id.get()),
        Bytes(" | Type: "), carbon_credit_app.state.credit_type.get(),
        Bytes(" | Registry: "), carbon_credit_app.state.carbon_registry.get(),
        Bytes(" | Project ID: "), carbon_credit_app.state.registry_project_id.get(),
        Bytes(" | Vintage: "), Int2Str(carbon_credit_app.state.vintage_start.get()),
        Bytes("-"), Int2Str(carbon_credit_app.state.vintage_end.get()),
        Bytes(" | Total Offset: "), Int2Str(carbon_credit_app.state.total_carbon_offset.get()),
        Bytes(" | Remaining: "), Int2Str(carbon_credit_app.state.remaining_offset.get()),
        Bytes(" | Verified by: "), carbon_credit_app.state.verifier.get(),
        Bytes(" | Jurisdiction: "), carbon_credit_app.state.jurisdiction_code.get(),
        Bytes(" | Investment Status: "), carbon_credit_app.state.investment_status.get()
    )
    
    return Seq([
        asset_id_check,
        output.set(details)
    ])

@carbon_credit_app.external(read_only=True)
def verify_carbon_credit(
    credit_asset_id: abi.Uint64,
    *,
    output: abi.Bool
) -> Expr:
    """Verify the authenticity of carbon credit"""
    
    # Ensure the carbon credit exists and matches our records
    asset_id_check = Assert(
        carbon_credit_app.state.asset_id.get() == credit_asset_id.get(),
        comment="Credit ID mismatch"
    )
    
    # Check if the compliance status is verified
    check_status = carbon_credit_app.state.compliance_status.get() == Bytes("verified")
    
    return Seq([
        asset_id_check,
        output.set(check_status)
    ])

@carbon_credit_app.external
def transfer_credits(
    credit_asset_id: abi.Uint64,
    from_address: abi.Address,
    to_address: abi.Address,
    amount: abi.Uint64
) -> Expr:
    """Transfer carbon credits between accounts"""
    
    # Ensure the carbon credit exists and matches our records
    asset_id_check = Assert(
        carbon_credit_app.state.asset_id.get() == credit_asset_id.get(),
        comment="Credit ID mismatch"
    )
    
    # Check compliance status - only allow transfers for verified credits
    compliance_check = Assert(
        carbon_credit_app.state.compliance_status.get() == Bytes("verified"),
        comment="Credits are not verified"
    )
    
    # Check authorization - caller must be the credit owner
    auth_check = Assert(
        Txn.sender() == from_address.get(),
        comment="Sender must be the credit owner"
    )
    
    # Execute the transfer
    asset_transfer = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: credit_asset_id.get(),
            TxnField.asset_amount: amount.get(),
            TxnField.asset_receiver: to_address.get(),
            TxnField.asset_sender: from_address.get()
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Update timestamp
    update_timestamp = carbon_credit_app.state.last_updated.set(Global.latest_timestamp())
    
    return Seq([
        asset_id_check,
        compliance_check,
        auth_check,
        asset_transfer,
        update_timestamp
    ])

if __name__ == "__main__":
    # Compile and export the app
    app_spec = carbon_credit_app.build()
    app_spec.export("artifacts/carbon_credit")