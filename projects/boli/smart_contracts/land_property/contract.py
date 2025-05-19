# ~/Desktop/boli/projects/boli/smart_contracts/land_property/contract.py

from pyteal import *
from beaker import *
from beaker.lib.storage import BoxMapping

from smart_contracts.contract_base import BaseState, ContractBase

# Implement a proper Int2Str function using Itob and other PyTeal operations
def Int2Str(i: Expr) -> Expr:
    """Convert an integer expression to a string expression using Itob."""
    # Convert int to bytes (big-endian) and extract only the needed part
    return Extract(Itob(i), Int(0), Int(8))

class LandPropertyState(BaseState):
    """State class for Land & Property assets"""
    
    # Land property specific state variables
    property_type = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Type of property (residential, commercial, agricultural, etc.)"
    )
    
    legal_identifier = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Legal identifier or registry number for the property"
    )
    
    valuation_amount = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Property valuation amount"
    )
    
    valuation_date = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Date of the last property valuation"
    )
    
    fractional_asset_id = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Asset ID for fractional ownership tokens"
    )
    
    fractionalized_status = GlobalStateValue(
        stack_type=TealType.uint64,  # 0 = false, 1 = true
        descr="Whether the property has been fractionalized"
    )

land_property_app = Application(
    "LandPropertyContract",
    descr="Handles tokenization of real estate with legal document integration",
    state=LandPropertyState()
)

@land_property_app.create
def create():
    """Initialize the app - basic setup only"""
    return Approve()

@land_property_app.external
def create_property(
    name: abi.String,
    unit_name: abi.String,
    property_type: abi.String,
    legal_identifier: abi.String,
    jurisdiction_code: abi.String,
    geolocation: abi.String,
    valuation_amount: abi.Uint64,
    legal_document_hash: abi.String,
    *,
    output: abi.Uint64
) -> Expr:
    """Creates a new tokenized property"""
    
    # Only allow the creator to create properties
    assert_creator = ContractBase.assert_sender_is_creator(land_property_app)
    
    # Prepare extended note with property details
    note = Concat(
        Bytes("Boli Property: "),
        property_type.get(),
        Bytes(" | Legal ID: "),
        legal_identifier.get(),
        Bytes(" | Jurisdiction: "),
        jurisdiction_code.get()
    )
    
    # Create the property as a non-fungible token (single unit)
    create_token = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetConfig,
            TxnField.config_asset_total: Int(1),  # NFT representing the property
            TxnField.config_asset_decimals: Int(0),
            TxnField.config_asset_default_frozen: Int(0),
            TxnField.config_asset_manager: Global.current_application_address(),
            TxnField.config_asset_reserve: Txn.sender(),
            TxnField.config_asset_freeze: Global.current_application_address(),
            TxnField.config_asset_clawback: Global.current_application_address(),
            TxnField.config_asset_unit_name: unit_name.get(),
            TxnField.config_asset_name: name.get(),
            TxnField.config_asset_url: Concat(Bytes("ipfs://"), legal_document_hash.get()),
            TxnField.note: note
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Store the ASA ID
    asset_id = InnerTxn.created_asset_id()
    store_asset_id = land_property_app.state.asset_id.set(asset_id)
    
    # Store base asset information
    store_base_info = Seq([
        land_property_app.state.asset_creator.set(Txn.sender()),
        land_property_app.state.asset_type.set(Bytes("land-property")),
        land_property_app.state.geolocation.set(geolocation.get()),
        land_property_app.state.metadata.set(legal_document_hash.get()),
        land_property_app.state.jurisdiction_code.set(jurisdiction_code.get()),
        land_property_app.state.compliance_status.set(Bytes("created")),
        land_property_app.state.last_updated.set(Global.latest_timestamp())
    ])
    
    # Store property-specific information
    store_property_info = Seq([
        land_property_app.state.property_type.set(property_type.get()),
        land_property_app.state.legal_identifier.set(legal_identifier.get()),
        land_property_app.state.valuation_amount.set(valuation_amount.get()),
        land_property_app.state.valuation_date.set(Global.latest_timestamp()),
        land_property_app.state.fractionalized_status.set(Int(0))  # False
    ])
    
    return Seq([
        assert_creator,
        create_token,
        store_asset_id,
        store_base_info,
        store_property_info,
        output.set(asset_id)
    ])

@land_property_app.external
def fractionalize_property(
    property_asset_id: abi.Uint64,
    fraction_name: abi.String,
    fraction_unit_name: abi.String,
    fraction_count: abi.Uint64,
    fraction_decimals: abi.Uint64,
    *,
    output: abi.Uint64
) -> Expr:
    """Fractionalize a property into multiple tokens for shared ownership"""
    
    # Ensure the property exists and matches our records
    asset_id_check = Assert(
        land_property_app.state.asset_id.get() == property_asset_id.get(),
        comment="Property ID mismatch"
    )
    
    # Only allow the contract creator or property owner to fractionalize
    assert_creator = ContractBase.assert_sender_is_creator(land_property_app)
    
    # Check that property isn't already fractionalized
    check_not_fractionalized = Assert(
        land_property_app.state.fractionalized_status.get() == Int(0),
        comment="Property is already fractionalized"
    )
    
    # Prepare note for fractional tokens
    note = Concat(
        Bytes("Boli Fractionalized Property: "),
        land_property_app.state.property_type.get(),
        Bytes(" | Original Asset ID: "),
        Int2Str(property_asset_id.get()),
        Bytes(" | Legal ID: "),
        land_property_app.state.legal_identifier.get()
    )
    
    # Create fractional tokens
    create_token = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetConfig,
            TxnField.config_asset_total: fraction_count.get(),
            TxnField.config_asset_decimals: fraction_decimals.get(),
            TxnField.config_asset_default_frozen: Int(0),
            TxnField.config_asset_manager: Global.current_application_address(),
            TxnField.config_asset_reserve: Txn.sender(),
            TxnField.config_asset_freeze: Global.current_application_address(),
            TxnField.config_asset_clawback: Global.current_application_address(),
            TxnField.config_asset_unit_name: fraction_unit_name.get(),
            TxnField.config_asset_name: fraction_name.get(),
            TxnField.config_asset_url: Concat(Bytes("ipfs://"), land_property_app.state.metadata.get()),
            TxnField.note: note
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Store the fractional ASA ID
    fractional_asset_id = InnerTxn.created_asset_id()
    
    # Update property status to fractionalized
    update_status = Seq([
        land_property_app.state.fractionalized_status.set(Int(1)),  # True
        land_property_app.state.fractional_asset_id.set(fractional_asset_id),
        land_property_app.state.last_updated.set(Global.latest_timestamp())
    ])
    
    return Seq([
        asset_id_check,
        assert_creator,
        check_not_fractionalized,
        create_token,
        update_status,
        output.set(fractional_asset_id)
    ])

@land_property_app.external
def update_valuation(
    property_asset_id: abi.Uint64,
    new_valuation: abi.Uint64,
    appraisal_document_hash: abi.String
) -> Expr:
    """Updates property valuation"""
    
    # Ensure the property exists and matches our records
    asset_id_check = Assert(
        land_property_app.state.asset_id.get() == property_asset_id.get(),
        comment="Property ID mismatch"
    )
    
    # Only allow the contract creator or authorized appraiser to update valuation
    assert_creator = ContractBase.assert_sender_is_creator(land_property_app)
    
    # Update valuation information
    update_valuation = Seq([
        land_property_app.state.valuation_amount.set(new_valuation.get()),
        land_property_app.state.valuation_date.set(Global.latest_timestamp())
    ])
    
    # Store appraisal document reference
    updated_metadata = Concat(
        land_property_app.state.metadata.get(),
        Bytes("|appraisal:"),
        appraisal_document_hash.get()
    )
    
    return Seq([
        asset_id_check,
        assert_creator,
        update_valuation,
        land_property_app.state.metadata.set(updated_metadata)
    ])

@land_property_app.external
def update_legal_documentation(
    property_asset_id: abi.Uint64,
    new_legal_document_hash: abi.String,
    document_type: abi.String
) -> Expr:
    """Updates property legal documentation"""
    
    # Ensure the property exists and matches our records
    asset_id_check = Assert(
        land_property_app.state.asset_id.get() == property_asset_id.get(),
        comment="Property ID mismatch"
    )
    
    # Only allow the contract creator or property owner to update documents
    assert_creator = ContractBase.assert_sender_is_creator(land_property_app)
    
    # Update document reference
    updated_metadata = Concat(
        land_property_app.state.metadata.get(),
        Bytes("|"),
        document_type.get(),
        Bytes(":"),
        new_legal_document_hash.get()
    )
    
    # Update asset if this property is fractionalized
    update_fractional_asset = If(
        land_property_app.state.fractionalized_status.get() == Int(1),
        # Update the fractional asset config
        Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.AssetConfig,
                TxnField.config_asset: land_property_app.state.fractional_asset_id.get(),
                TxnField.config_asset_manager: Global.current_application_address(),
                TxnField.config_asset_reserve: Txn.sender(),
                TxnField.config_asset_freeze: Global.current_application_address(),
                TxnField.config_asset_clawback: Global.current_application_address()
            }),
            InnerTxnBuilder.Submit()
        ),
        Seq([])  # No-op if not fractionalized
    )
    
    return Seq([
        asset_id_check,
        assert_creator,
        land_property_app.state.metadata.set(updated_metadata),
        land_property_app.state.last_updated.set(Global.latest_timestamp()),
        update_fractional_asset
    ])

@land_property_app.external(read_only=True)
def get_property_details(
    property_asset_id: abi.Uint64,
    *,
    output: abi.String
) -> Expr:
    """Get detailed property information"""
    
    # Ensure the property exists and matches our records
    asset_id_check = Assert(
        land_property_app.state.asset_id.get() == property_asset_id.get(),
        comment="Property ID mismatch"
    )
    
    # Build the property information string
    main_details = Concat(
        Bytes("Property ID: "), Int2Str(land_property_app.state.asset_id.get()),
        Bytes(" | Type: "), land_property_app.state.property_type.get(),
        Bytes(" | Legal ID: "), land_property_app.state.legal_identifier.get(),
        Bytes(" | Jurisdiction: "), land_property_app.state.jurisdiction_code.get(),
        Bytes(" | Valuation: "), Int2Str(land_property_app.state.valuation_amount.get()),
        Bytes(" | Fractionalized: "), If(
            land_property_app.state.fractionalized_status.get() == Int(1),
            Bytes("Yes"),
            Bytes("No")
        )
    )
    
    # Add fractional asset ID if fractionalized
    fractional_info = If(
        land_property_app.state.fractionalized_status.get() == Int(1),
        Concat(
            Bytes(" | Fraction Asset ID: "),
            Int2Str(land_property_app.state.fractional_asset_id.get())
        ),
        Bytes("")  # Empty string if not fractionalized
    )
    
    # Combine all details
    details = Concat(main_details, fractional_info)
    
    return Seq([
        asset_id_check,
        output.set(details)
    ])

@land_property_app.external
def transfer_property(
    property_asset_id: abi.Uint64,
    from_address: abi.Address,
    to_address: abi.Address
) -> Expr:
    """Transfer ownership of the property"""
    
    # Ensure the property exists and matches our records
    asset_id_check = Assert(
        land_property_app.state.asset_id.get() == property_asset_id.get(),
        comment="Property ID mismatch"
    )
    
    # Check compliance status - only allow transfers for compliant properties
    check_compliance = Assert(
        land_property_app.state.compliance_status.get() != Bytes("suspended"),
        comment="Property transfers suspended"
    )
    
    # Check that property isn't fractionalized
    check_not_fractionalized = Assert(
        land_property_app.state.fractionalized_status.get() == Int(0),
        comment="Property is fractionalized, transfer fractional tokens instead"
    )
    
    # Check authorization - caller must be the property owner
    auth_check = Assert(
        Txn.sender() == from_address.get(),
        comment="Sender must be the property owner"
    )
    
    # Execute the transfer (NFT - amount is always 1)
    asset_transfer = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: property_asset_id.get(),
            TxnField.asset_amount: Int(1),
            TxnField.asset_receiver: to_address.get(),
            TxnField.asset_sender: from_address.get()
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Update ownership records
    update_timestamp = land_property_app.state.last_updated.set(Global.latest_timestamp())
    
    return Seq([
        asset_id_check,
        check_compliance,
        check_not_fractionalized,
        auth_check,
        asset_transfer,
        update_timestamp
    ])

if __name__ == "__main__":
    # Compile and export the app
    app_spec = land_property_app.build()
    app_spec.export("artifacts/land_property")