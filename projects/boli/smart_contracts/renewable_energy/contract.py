# ~/Desktop/boli/projects/boli/smart_contracts/renewable_energy/contract.py

from pyteal import *
from beaker import *
from beaker.lib.storage import BoxMapping

from smart_contracts.contract_base import BaseState, ContractBase

# Implement a proper Int2Str function using Itob and other PyTeal operations
def Int2Str(i: Expr) -> Expr:
    """Convert an integer expression to a string expression using Itob."""
    # Convert int to bytes (big-endian) and extract only the needed part
    return Extract(Itob(i), Int(0), Int(8))

class RenewableEnergyState(BaseState):
    """State class for Renewable Energy assets"""
    
    # Energy project specific state
    energy_type = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Type of renewable energy (solar, wind, hydro, etc.)"
    )
    
    installed_capacity = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Installed capacity in watts"
    )
    
    estimated_annual_output = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Estimated annual output in kilowatt-hours"
    )
    
    project_lifespan = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Project lifespan in seconds"
    )
    
    installation_date = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Installation date timestamp"
    )

renewable_energy_app = Application(
    "RenewableEnergyContract",
    descr="Handles tokenization of renewable energy projects and their output",
    state=RenewableEnergyState()
)

@renewable_energy_app.create
def create():
    """Initialize the app - basic setup only"""
    return Approve()

@renewable_energy_app.external
def create_energy_project(
    project_name: abi.String,
    energy_type: abi.String,
    installed_capacity: abi.Uint64,
    estimated_annual_output: abi.Uint64,
    project_lifespan: abi.Uint64,
    location: abi.String,
    fractionalize: abi.Bool,
    fraction_count: abi.Uint64,
    technical_specs_hash: abi.String,
    jurisdiction_code: abi.String,
    *,
    output: abi.Uint64
) -> Expr:
    """Creates a renewable energy infrastructure asset"""
    
    # Only allow the creator to create energy projects
    assert_creator = ContractBase.assert_sender_is_creator(renewable_energy_app)
    
    # Store renewable energy project information
    store_energy_info = Seq([
        renewable_energy_app.state.energy_type.set(energy_type.get()),
        renewable_energy_app.state.installed_capacity.set(installed_capacity.get()),
        renewable_energy_app.state.estimated_annual_output.set(estimated_annual_output.get()),
        renewable_energy_app.state.project_lifespan.set(project_lifespan.get()),
        renewable_energy_app.state.installation_date.set(Global.latest_timestamp())
    ])
    
    # Generate asset name and unit
    asset_name = Concat(Bytes("ENERGY-"), project_name.get())
    unit_name = Bytes("ENRG")
    
    # Prepare note with additional metadata
    note = Concat(
        Bytes("Boli Renewable Energy Project: "),
        energy_type.get(),
        Bytes(" | Capacity: "),
        Int2Str(installed_capacity.get()),
        Bytes("W | Est. Output: "),
        Int2Str(estimated_annual_output.get()),
        Bytes("kWh")
    )
    
    # Determine token supply based on fractionalization choice
    total_supply = If(
        fractionalize.get(),
        fraction_count.get(),
        Int(1)
    )
    
    decimals = If(
        fractionalize.get(),
        Int(6),
        Int(0)
    )
    
    # Fix inner transaction syntax - wrap in Seq() instead of using commas
    create_token = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetConfig,
            TxnField.config_asset_total: total_supply,
            TxnField.config_asset_decimals: decimals,
            TxnField.config_asset_default_frozen: Int(0),
            TxnField.config_asset_manager: Global.current_application_address(),
            TxnField.config_asset_reserve: Txn.sender(),
            TxnField.config_asset_freeze: Global.current_application_address(),
            TxnField.config_asset_clawback: Global.current_application_address(),
            TxnField.config_asset_unit_name: unit_name,
            TxnField.config_asset_name: asset_name,
            TxnField.config_asset_url: Concat(Bytes("ipfs://"), technical_specs_hash.get()),
            TxnField.note: note
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Store the ASA ID
    asset_id = InnerTxn.created_asset_id()
    store_asset_id = renewable_energy_app.state.asset_id.set(asset_id)
    
    # Store base asset information
    store_base_info = Seq([
        renewable_energy_app.state.asset_creator.set(Txn.sender()),
        renewable_energy_app.state.asset_type.set(Bytes("renewable-energy")),
        renewable_energy_app.state.geolocation.set(location.get()),
        renewable_energy_app.state.metadata.set(technical_specs_hash.get()),
        renewable_energy_app.state.jurisdiction_code.set(jurisdiction_code.get()),
        renewable_energy_app.state.compliance_status.set(Bytes("authorized")),
        renewable_energy_app.state.last_updated.set(Global.latest_timestamp())
    ])
    
    return Seq([
        assert_creator,
        store_energy_info,
        create_token,
        store_asset_id,
        store_base_info,
        output.set(asset_id)
    ])

@renewable_energy_app.external
def create_energy_production_certificates(
    project_asset_id: abi.Uint64,
    production_period_start: abi.Uint64,
    production_period_end: abi.Uint64,
    energy_produced: abi.Uint64,
    meter_reading_hash: abi.String,
    *,
    output: abi.Uint64
) -> Expr:
    """Creates energy production certificates (similar to RECs)"""
    
    # Ensure the project asset exists and matches our records
    asset_id_check = Assert(
        renewable_energy_app.state.asset_id.get() == project_asset_id.get(),
        comment="Project Asset ID mismatch"
    )
    
    # Only allow the creator to issue certificates
    assert_creator = ContractBase.assert_sender_is_creator(renewable_energy_app)
    
    # Validate time period
    validate_period = Assert(
        production_period_start.get() < production_period_end.get(),
        comment="Invalid production period"
    )
    
    # Get project details
    energy_type = renewable_energy_app.state.energy_type.get()
    
    # Format period end date for certificate name
    end_date_string = Int2Str(production_period_end.get())
    
    # Generate certificate name
    asset_name = Concat(
        Bytes("REC-"),
        energy_type,
        Bytes("-"),
        Int2Str(project_asset_id.get()),
        Bytes("-"),
        end_date_string
    )
    unit_name = Bytes("REC")
    
    # Prepare note with additional metadata
    note = Concat(
        Bytes("Renewable Energy Certificate | Project: "),
        Int2Str(project_asset_id.get()),
        Bytes(" | Period: "),
        Int2Str(production_period_start.get()),
        Bytes("-"),
        Int2Str(production_period_end.get()),
        Bytes(" | Energy: "),
        Int2Str(energy_produced.get()),
        Bytes("kWh")
    )
    
    # Create one certificate per megawatt-hour of renewable energy
    total_certificates = Div(energy_produced.get(), Int(1000))  # Convert kWh to MWh
    
    # Fix inner transaction syntax
    create_token = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetConfig,
            TxnField.config_asset_total: total_certificates,
            TxnField.config_asset_decimals: Int(0),  # Non-divisible certificates
            TxnField.config_asset_default_frozen: Int(0),
            TxnField.config_asset_manager: Global.current_application_address(),
            TxnField.config_asset_reserve: Txn.sender(),
            TxnField.config_asset_freeze: Global.current_application_address(),
            TxnField.config_asset_clawback: Global.current_application_address(),
            TxnField.config_asset_unit_name: unit_name,
            TxnField.config_asset_name: asset_name,
            TxnField.config_asset_url: Concat(Bytes("ipfs://"), meter_reading_hash.get()),
            TxnField.note: note
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Get certificate asset ID
    certificate_asset_id = InnerTxn.created_asset_id()
    
    return Seq([
        asset_id_check,
        assert_creator,
        validate_period,
        create_token,
        output.set(certificate_asset_id)
    ])

@renewable_energy_app.external
def update_project_performance(
    project_asset_id: abi.Uint64,
    actual_output: abi.Uint64,
    performance_rating: abi.Uint64,
    maintenance_status: abi.String,
    *,
    output: abi.Bool
) -> Expr:
    """Updates project performance metrics"""
    
    # Ensure the project asset exists and matches our records
    asset_id_check = Assert(
        renewable_energy_app.state.asset_id.get() == project_asset_id.get(),
        comment="Project Asset ID mismatch"
    )
    
    # Only allow the creator to update project performance
    assert_creator = ContractBase.assert_sender_is_creator(renewable_energy_app)
    
    # Validate performance rating (1-100)
    validate_rating = Assert(
        And(
            performance_rating.get() >= Int(1),
            performance_rating.get() <= Int(100)
        ),
        comment="Performance rating must be between 1 and 100"
    )
    
    # Update project metrics in additional metadata
    updated_metadata = Concat(
        renewable_energy_app.state.metadata.get(),
        Bytes("|performance:"),
        Int2Str(performance_rating.get()),
        Bytes("|maintenance:"),
        maintenance_status.get(),
        Bytes("|actualOutput:"),
        Int2Str(actual_output.get())
    )
    
    return Seq([
        asset_id_check,
        assert_creator,
        validate_rating,
        renewable_energy_app.state.metadata.set(updated_metadata),
        renewable_energy_app.state.last_updated.set(Global.latest_timestamp()),
        output.set(Int(1))  # True
    ])

@renewable_energy_app.external(read_only=True)
def get_energy_project_details(
    project_asset_id: abi.Uint64,
    *,
    output: abi.String
) -> Expr:
    """Get detailed energy project information"""
    
    # Ensure the project asset exists and matches our records
    asset_id_check = Assert(
        renewable_energy_app.state.asset_id.get() == project_asset_id.get(),
        comment="Project Asset ID mismatch"
    )
    
    # Build the project information string
    details = Concat(
        Bytes("Energy Project ID: "), Int2Str(renewable_energy_app.state.asset_id.get()),
        Bytes(" | Type: "), renewable_energy_app.state.energy_type.get(),
        Bytes(" | Capacity: "), Int2Str(renewable_energy_app.state.installed_capacity.get()), Bytes("W"),
        Bytes(" | Est. Annual Output: "), Int2Str(renewable_energy_app.state.estimated_annual_output.get()), Bytes("kWh"),
        Bytes(" | Installation Date: "), Int2Str(renewable_energy_app.state.installation_date.get()),
        Bytes(" | Project Lifespan: "), Int2Str(renewable_energy_app.state.project_lifespan.get()), Bytes(" seconds"),
        Bytes(" | Jurisdiction: "), renewable_energy_app.state.jurisdiction_code.get(),
        Bytes(" | Location: "), renewable_energy_app.state.geolocation.get()
    )
    
    return Seq([
        asset_id_check,
        output.set(details)
    ])

@renewable_energy_app.external
def transfer_energy_project(
    project_asset_id: abi.Uint64,
    from_address: abi.Address,
    to_address: abi.Address,
    amount: abi.Uint64
) -> Expr:
    """Transfer ownership of the energy project"""
    
    # Ensure the asset exists and matches our records
    asset_id_check = Assert(
        renewable_energy_app.state.asset_id.get() == project_asset_id.get(),
        comment="Project Asset ID mismatch"
    )
    
    # Check compliance status
    check_compliance = Assert(
        renewable_energy_app.state.compliance_status.get() != Bytes("suspended"),
        comment="Project transfers suspended"
    )
    
    # Check authorization - caller must be the sender
    auth_check = Assert(
        Txn.sender() == from_address.get(),
        comment="Sender must be the asset owner"
    )
    
    # Fix inner transaction syntax
    asset_transfer = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: project_asset_id.get(),
            TxnField.asset_amount: amount.get(),
            TxnField.asset_receiver: to_address.get(),
            TxnField.asset_sender: from_address.get()
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Update records
    update_timestamp = renewable_energy_app.state.last_updated.set(Global.latest_timestamp())
    
    return Seq([
        asset_id_check,
        check_compliance,
        auth_check,
        asset_transfer,
        update_timestamp
    ])

if __name__ == "__main__":
    # Compile and export the app
    app_spec = renewable_energy_app.build()
    app_spec.export("artifacts/renewable_energy")