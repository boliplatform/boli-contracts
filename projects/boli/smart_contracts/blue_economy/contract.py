# ~/Desktop/boli/projects/boli/smart_contracts/blue_economy/contract.py

from pyteal import *
from beaker import *
from beaker.lib.storage import BoxMapping

from smart_contracts.contract_base import BaseState, ContractBase

# Implement a proper Int2Str function using Itob and other PyTeal operations
def Int2Str(i: Expr) -> Expr:
    """Convert an integer expression to a string expression using Itob."""
    # Convert int to bytes (big-endian) and extract only the needed part
    return Extract(Itob(i), Int(0), Int(8))

class BlueEconomyState(BaseState):
    """State class for Blue Economy assets"""
    
    # Marine-specific state
    resource_type = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Type of marine resource"
    )
    
    marine_zone = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Marine zone location"
    )
    
    sustainability_rating = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Sustainability rating (1-100)"
    )
    
    expiration_date = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Expiration date of the right (0 means perpetual)"
    )

blue_economy_app = Application(
    "BlueEconomyContract",
    descr="Manages tokenization of sustainable marine resources, fishing rights, and coastal tourism concessions",
    state=BlueEconomyState()
)

@blue_economy_app.create
def create():
    """Initialize the app - basic setup only"""
    return Approve()

# ADDED: BOLI configuration method
@blue_economy_app.external
def configure_boli_integration(
    asset_registry_id: abi.Uint64,
    treasury_app_id: abi.Uint64,
    *,
    output: abi.Bool
) -> Expr:
    """Configure the contract with BOLI integration"""
    
    # Only allow the creator to configure
    assert_creator = ContractBase.assert_sender_is_creator(blue_economy_app)
    
    # Store configuration
    store_config = Seq([
        blue_economy_app.state.asset_registry_id.set(asset_registry_id.get()),
        blue_economy_app.state.treasury_app_id.set(treasury_app_id.get())
    ])
    
    return Seq([
        assert_creator,
        store_config,
        output.set(Int(1))  # True
    ])

# MODIFIED: Added BOLI integration
@blue_economy_app.external
def create_marine_asset(
    resource_name: abi.String,
    resource_type: abi.String,
    marine_zone: abi.String,
    sustainability_rating: abi.Uint64,
    validity_period: abi.Uint64,
    documents_hash: abi.String,
    geo_boundary: abi.String,
    jurisdiction_code: abi.String,
    boli_allocation: abi.Uint64,  # NEW: BOLI allocation amount
    *,
    output: abi.Uint64,
) -> Expr:
    """Creates a tokenized marine resource or right with BOLI allocation"""
    
    # Only allow the creator to create marine assets
    assert_creator = ContractBase.assert_sender_is_creator(blue_economy_app)
    
    # Validate sustainability rating (1-100)
    assert_rating = Assert(
        And(
            sustainability_rating.get() >= Int(1),
            sustainability_rating.get() <= Int(100)
        ),
        comment="Sustainability rating must be between 1 and 100"
    )
    
    # Store marine resource information
    store_resource_type = blue_economy_app.state.resource_type.set(resource_type.get())
    store_marine_zone = blue_economy_app.state.marine_zone.set(marine_zone.get())
    store_sustainability = blue_economy_app.state.sustainability_rating.set(sustainability_rating.get())
    
    # Calculate expiration date (0 means perpetual)
    current_time = Global.latest_timestamp()
    calculate_exp = If(
        validity_period.get() > Int(0),
        blue_economy_app.state.expiration_date.set(current_time + validity_period.get()),
        blue_economy_app.state.expiration_date.set(Int(0))
    )
    
    # Generate asset name and unit
    asset_name = Concat(Bytes("BLUE-"), resource_name.get())
    unit_name = Bytes("BLUE")
    
    # Prepare note with additional metadata
    note = Concat(
        Bytes("Boli Blue Economy Asset: "),
        resource_type.get(),
        Bytes(" | Marine Zone: "),
        marine_zone.get(),
        Bytes(" | Sustainability: "),
        Int2Str(sustainability_rating.get()),
        Bytes("/100")
    )
    
    # Internal transaction to create the ASA
    create_token = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetConfig,
            TxnField.config_asset_total: Int(1000000),
            TxnField.config_asset_decimals: Int(3),
            TxnField.config_asset_default_frozen: Int(0),
            TxnField.config_asset_manager: Global.current_application_address(),
            TxnField.config_asset_reserve: Txn.sender(),
            TxnField.config_asset_freeze: Global.current_application_address(),
            TxnField.config_asset_clawback: Global.current_application_address(),
            TxnField.config_asset_unit_name: unit_name,
            TxnField.config_asset_name: asset_name,
            TxnField.config_asset_url: Concat(Bytes("ipfs://"), documents_hash.get()),
            TxnField.note: note
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Store the ASA ID
    asset_id = InnerTxn.created_asset_id()
    store_asset_id = blue_economy_app.state.asset_id.set(asset_id)
    
    # Store base asset information
    store_base_info = Seq([
        blue_economy_app.state.asset_creator.set(Txn.sender()),
        blue_economy_app.state.asset_type.set(Bytes("blue-economy")),
        blue_economy_app.state.geolocation.set(geo_boundary.get()),
        blue_economy_app.state.metadata.set(documents_hash.get()),
        blue_economy_app.state.jurisdiction_code.set(jurisdiction_code.get()),
        blue_economy_app.state.compliance_status.set(Bytes("authorized")),
        blue_economy_app.state.last_updated.set(Global.latest_timestamp())
    ])
    
    # NEW: Register with Asset Registry for BOLI allocation
    register_for_boli = ContractBase.register_with_asset_registry(
        blue_economy_app,
        resource_name.get(),
        Bytes("blue-economy"),
        jurisdiction_code.get(),
        boli_allocation.get()
    )
    
    return Seq([
        assert_creator,
        assert_rating,
        store_resource_type,
        store_marine_zone,
        store_sustainability,
        calculate_exp,
        create_token,
        store_asset_id,
        store_base_info,
        # Only register with BOLI if allocation amount is greater than 0
        If(
            boli_allocation.get() > Int(0),
            register_for_boli,
            Seq([])  # No-op if no BOLI allocation
        ),
        output.set(asset_id)
    ])

# ADDED: Update funding status method
@blue_economy_app.external
def update_funding_status(
    new_status: abi.String,
    *,
    output: abi.Bool
) -> Expr:
    """Updates the marine asset funding status"""
    
    # Only allow the creator to update status
    is_authorized = Txn.sender() == Global.creator_address()
    
    assert_authorized = Assert(
        is_authorized,
        comment="Only creator or Asset Registry can update status"
    )
    
    # Update the investment status
    update_status = ContractBase.update_investment_status(
        blue_economy_app,
        new_status.get()
    )
    
    return Seq([
        assert_authorized,
        update_status,
        output.set(Int(1))  # True
    ])

# ADDED: Marine revenue reporting method
@blue_economy_app.external
def report_marine_revenue(
    revenue_amount: abi.Uint64,
    activity_type: abi.String,
    period_start: abi.Uint64,
    period_end: abi.Uint64,
    *,
    output: abi.Bool
) -> Expr:
    """Reports marine resource revenue for distribution to token holders"""
    
    # Only allow the creator to report revenue
    assert_creator = ContractBase.assert_sender_is_creator(blue_economy_app)
    
    # Verify the asset is in active status
    assert_active = Assert(
        blue_economy_app.state.investment_status.get() == Bytes("active"),
        comment="Marine asset is not in active status"
    )
    
    # Create distribution note
    distribution_note = Concat(
        Bytes("Marine Revenue: "),
        Int2Str(revenue_amount.get()),
        Bytes(" | Activity: "),
        activity_type.get(),
        Bytes(" | Period: "),
        Int2Str(period_start.get()),
        Bytes("-"),
        Int2Str(period_end.get())
    )
    
    # Distribute revenue to token holders
    distribute = ContractBase.distribute_revenue(
        blue_economy_app,
        revenue_amount.get(),
        Bytes("marine-revenue"),
        distribution_note
    )
    
    return Seq([
        assert_creator,
        assert_active,
        distribute,
        output.set(Int(1))  # True
    ])

@blue_economy_app.external(read_only=True)
def is_marine_right_valid(
    asset_id: abi.Uint64,
    *,
    output: abi.Bool
) -> Expr:
    """Check if a marine right is still valid (not expired)"""
    
    asset_id_check = Assert(
        blue_economy_app.state.asset_id.get() == asset_id.get(),
        comment="Asset ID mismatch"
    )
    
    expiration_timestamp = blue_economy_app.state.expiration_date.get()
    
    return Seq([
        asset_id_check,
        If(
            # If expiration is 0, it's perpetual
            expiration_timestamp == Int(0),
            output.set(Int(1)),  # True
            # Otherwise, check against current time
            output.set(Global.latest_timestamp() < expiration_timestamp)
        )
    ])

@blue_economy_app.external
def update_sustainability_rating(
    asset_id: abi.Uint64,
    new_rating: abi.Uint64,
    assessment_hash: abi.String,
    *,
    output: abi.Bool
) -> Expr:
    """Update sustainability rating based on environmental assessment"""
    
    # Ensure the asset exists and matches our records
    asset_id_check = Assert(
        blue_economy_app.state.asset_id.get() == asset_id.get(),
        comment="Asset ID mismatch"
    )
    
    # Only allow the creator to update ratings
    assert_creator = ContractBase.assert_sender_is_creator(blue_economy_app)
    
    # Validate rating is within accepted range
    validate_rating = Assert(
        And(
            new_rating.get() >= Int(1),
            new_rating.get() <= Int(100)
        ),
        comment="Rating must be between 1 and 100"
    )
    
    # Update sustainability rating
    update_rating = blue_economy_app.state.sustainability_rating.set(new_rating.get())
    
    # Update metadata with assessment document
    updated_metadata = Concat(
        blue_economy_app.state.metadata.get(),
        Bytes("|assessment:"),
        assessment_hash.get()
    )
    
    return Seq([
        asset_id_check,
        assert_creator,
        validate_rating,
        update_rating,
        blue_economy_app.state.metadata.set(updated_metadata),
        blue_economy_app.state.last_updated.set(Global.latest_timestamp()),
        output.set(Int(1))  # True
    ])

@blue_economy_app.external
def extend_validity_period(
    asset_id: abi.Uint64,
    extension_period: abi.Uint64,
    *,
    output: abi.Bool
) -> Expr:
    """Extend the validity period of a marine right"""
    
    # Ensure the asset exists and matches our records
    asset_id_check = Assert(
        blue_economy_app.state.asset_id.get() == asset_id.get(),
        comment="Asset ID mismatch"
    )
    
    # Only allow the creator to extend validity
    assert_creator = ContractBase.assert_sender_is_creator(blue_economy_app)
    
    # Get current expiration
    current_expiration = blue_economy_app.state.expiration_date.get()
    
    # Handle extension logic
    handle_extension = If(
        # If perpetual, remain perpetual
        current_expiration == Int(0),
        Seq([
            # No change needed for perpetual rights
            blue_economy_app.state.last_updated.set(Global.latest_timestamp()),
            output.set(Int(1))  # True
        ]),
        Seq([
            # Extend period
            blue_economy_app.state.expiration_date.set(current_expiration + extension_period.get()),
            blue_economy_app.state.last_updated.set(Global.latest_timestamp()),
            output.set(Int(1))  # True
        ])
    )
    
    return Seq([
        asset_id_check,
        assert_creator,
        handle_extension
    ])

@blue_economy_app.external(read_only=True)
def get_marine_asset_details(
    asset_id: abi.Uint64,
    *,
    output: abi.String
) -> Expr:
    """Get detailed marine asset information"""
    
    # Ensure the asset exists and matches our records
    asset_id_check = Assert(
        blue_economy_app.state.asset_id.get() == asset_id.get(),
        comment="Asset ID mismatch"
    )
    
    # Check if marine right is valid
    is_valid = ScratchVar(TealType.uint64)
    validity_check = Seq([
        # Call is_marine_right_valid logic directly here since we can't call methods internally
        If(
            blue_economy_app.state.expiration_date.get() == Int(0),
            is_valid.store(Int(1)),  # True if perpetual
            is_valid.store(If(Global.latest_timestamp() < blue_economy_app.state.expiration_date.get(), Int(1), Int(0)))
        )
    ])
    
    # Build the main part of the details string
    main_details = Concat(
        Bytes("Marine Asset ID: "), Int2Str(blue_economy_app.state.asset_id.get()),
        Bytes(" | Type: "), blue_economy_app.state.resource_type.get(),
        Bytes(" | Marine Zone: "), blue_economy_app.state.marine_zone.get(),
        Bytes(" | Jurisdiction: "), blue_economy_app.state.jurisdiction_code.get(),
        Bytes(" | Sustainability Rating: "), Int2Str(blue_economy_app.state.sustainability_rating.get()), Bytes("/100"),
        Bytes(" | Investment Status: "), blue_economy_app.state.investment_status.get()
    )
    
    # Add expiration info
    expiration_info = If(
        blue_economy_app.state.expiration_date.get() == Int(0),
        Bytes(" | Validity: Perpetual"),
        Concat(
            Bytes(" | Expires: "), Int2Str(blue_economy_app.state.expiration_date.get()),
            Bytes(" | Status: "), If(is_valid.load(), Bytes("Valid"), Bytes("Expired"))
        )
    )
    
    # Combine all details
    details = Concat(main_details, expiration_info)
    
    return Seq([
        asset_id_check,
        validity_check,
        output.set(details)
    ])

@blue_economy_app.external
def transfer_marine_asset(
    asset_id: abi.Uint64,
    from_address: abi.Address,
    to_address: abi.Address,
    amount: abi.Uint64
) -> Expr:
    """Transfer rights to the marine asset"""
    
    # Ensure the asset exists and matches our records
    asset_id_check = Assert(
        blue_economy_app.state.asset_id.get() == asset_id.get(),
        comment="Asset ID mismatch"
    )
    
    # Check that asset is valid using the same logic as in is_marine_right_valid
    is_valid = ScratchVar(TealType.uint64)
    validity_check = Seq([
        If(
            blue_economy_app.state.expiration_date.get() == Int(0),
            is_valid.store(Int(1)),  # True if perpetual
            is_valid.store(If(Global.latest_timestamp() < blue_economy_app.state.expiration_date.get(), Int(1), Int(0)))
        ),
        Assert(
            is_valid.load() == Int(1),
            comment="Cannot transfer expired marine rights"
        )
    ])
    
    # Check compliance status
    compliance_check = Assert(
        blue_economy_app.state.compliance_status.get() == Bytes("authorized"),
        comment="Asset is not authorized for transfer"
    )
    
    # Check authorization - caller must be the sender
    auth_check = Assert(
        Txn.sender() == from_address.get(),
        comment="Sender must be the asset owner"
    )
    
    # Execute the transfer via an inner transaction
    asset_transfer = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: asset_id.get(),
            TxnField.asset_amount: amount.get(),
            TxnField.asset_receiver: to_address.get(),
            TxnField.asset_sender: from_address.get()
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Update records
    update_timestamp = blue_economy_app.state.last_updated.set(Global.latest_timestamp())
    
    return Seq([
        asset_id_check,
        validity_check,
        compliance_check,
        auth_check,
        asset_transfer,
        update_timestamp
    ])

if __name__ == "__main__":
    # Compile and export the app
    app_spec = blue_economy_app.build()
    app_spec.export("artifacts/blue_economy")