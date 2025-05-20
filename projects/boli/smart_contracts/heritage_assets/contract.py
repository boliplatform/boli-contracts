# ~/Desktop/boli/projects/boli/smart_contracts/heritage_assets/contract.py


from pyteal import *
from beaker import *
from beaker.lib.storage import BoxMapping

from smart_contracts.contract_base import BaseState, ContractBase

# Implement a proper Int2Str function using Itob and other PyTeal operations
def Int2Str(i: Expr) -> Expr:
    """Convert an integer expression to a string expression using Itob."""
    # Convert int to bytes (big-endian) and extract only the needed part
    return Extract(Itob(i), Int(0), Int(8))

class HeritageAssetState(BaseState):
    """State class for Heritage Asset contracts"""
    
    # Heritage specific state variables
    heritage_type = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Type of heritage (archaeological, architectural, cultural, indigenous)"
    )
    
    cultural_significance = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Cultural significance description"
    )
    
    legal_status = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Legal status (protected, endangered, unesco, etc.)"
    )
    
    community_identifier = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Address of community/indigenous group with stewardship"
    )
    
    stewardship_model = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Stewardship model (community, split, custodial, etc.)"
    )
    
    restoration_required = GlobalStateValue(
        stack_type=TealType.uint64,  # 0 = false, 1 = true
        descr="Whether restoration is required"
    )
    
    conservation_status = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Conservation status"
    )
    
    # Project funding variables
    funding_pool = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Current funding pool"
    )
    
    funding_target = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Funding target"
    )
    
    project_deadline = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Project deadline timestamp"
    )
    
    project_phases = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Number of project phases"
    )
    
    current_phase = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Current project phase"
    )
    
    project_verifier = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Address of expert who verifies completion"
    )
    
    # Fractional ownership tracking
    ownership_token_id = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="ID of token representing fractional ownership"
    )
    
    has_ownership_tokens = GlobalStateValue(
        stack_type=TealType.uint64,  # 0 = false, 1 = true
        descr="Whether the asset has ownership tokens"
    )
    
    # Revenue distribution variables
    community_share = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Percentage for community in basis points (100 = 1%)"
    )
    
    investor_share = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Percentage for investors in basis points (100 = 1%)"
    )
    
    conservation_share = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Percentage for ongoing conservation in basis points (100 = 1%)"
    )

heritage_asset_app = Application(
    "HeritageAssetContract",
    descr="Manages tokenization, restoration funding, and cultural stewardship of heritage sites and artifacts",
    state=HeritageAssetState()
)

@heritage_asset_app.create
def create():
    """Initialize the app - basic setup only"""
    return Approve()

# ADDED: BOLI configuration method
@heritage_asset_app.external
def configure_boli_integration(
    asset_registry_id: abi.Uint64,
    treasury_app_id: abi.Uint64,
    *,
    output: abi.Bool
) -> Expr:
    """Configure the contract with BOLI integration"""
    
    # Only allow the creator to configure
    assert_creator = ContractBase.assert_sender_is_creator(heritage_asset_app)
    
    # Store configuration
    store_config = Seq([
        heritage_asset_app.state.asset_registry_id.set(asset_registry_id.get()),
        heritage_asset_app.state.treasury_app_id.set(treasury_app_id.get())
    ])
    
    return Seq([
        assert_creator,
        store_config,
        output.set(Int(1))  # True
    ])

# MODIFIED: Added BOLI integration
@heritage_asset_app.external
def create_heritage_asset(
    name: abi.String,
    unit_name: abi.String,
    heritage_type: abi.String,
    cultural_significance: abi.String,
    legal_status: abi.String,
    jurisdiction_code: abi.String,
    geolocation: abi.String,
    community_identifier: abi.Address,
    stewardship_model: abi.String,
    documentation_hash: abi.String,
    boli_allocation: abi.Uint64,  # NEW: BOLI allocation amount
    *,
    output: abi.Uint64
) -> Expr:
    """Creates a new heritage asset with BOLI allocation"""
    
    # Only allow the creator to create heritage assets
    assert_creator = ContractBase.assert_sender_is_creator(heritage_asset_app)
    
    # Prepare note with heritage details
    note = Concat(
        Bytes("Boli Heritage Asset: "),
        heritage_type.get(),
        Bytes(" | Significance: "),
        cultural_significance.get(),
        Bytes(" | Status: "),
        legal_status.get()
    )
    
    # Create the heritage asset as a non-fungible token (single unit)
    create_token = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetConfig,
            TxnField.config_asset_total: Int(1),  # NFT representing the heritage asset
            TxnField.config_asset_decimals: Int(0),
            TxnField.config_asset_default_frozen: Int(0),
            TxnField.config_asset_manager: Global.current_application_address(),
            TxnField.config_asset_reserve: Txn.sender(),
            TxnField.config_asset_freeze: Global.current_application_address(),
            TxnField.config_asset_clawback: Global.current_application_address(),
            TxnField.config_asset_unit_name: unit_name.get(),
            TxnField.config_asset_name: name.get(),
            TxnField.config_asset_url: Concat(Bytes("ipfs://"), documentation_hash.get()),
            TxnField.note: note
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Store the ASA ID
    asset_id = InnerTxn.created_asset_id()
    store_asset_id = heritage_asset_app.state.asset_id.set(asset_id)
    
    # Store base asset information
    store_base_info = Seq([
        heritage_asset_app.state.asset_creator.set(Txn.sender()),
        heritage_asset_app.state.asset_type.set(Bytes("heritage-asset")),
        heritage_asset_app.state.geolocation.set(geolocation.get()),
        heritage_asset_app.state.metadata.set(documentation_hash.get()),
        heritage_asset_app.state.jurisdiction_code.set(jurisdiction_code.get()),
        heritage_asset_app.state.compliance_status.set(Bytes("registered")),
        heritage_asset_app.state.last_updated.set(Global.latest_timestamp())
    ])
    
    # Store heritage-specific information
    store_heritage_info = Seq([
        heritage_asset_app.state.heritage_type.set(heritage_type.get()),
        heritage_asset_app.state.cultural_significance.set(cultural_significance.get()),
        heritage_asset_app.state.legal_status.set(legal_status.get()),
        heritage_asset_app.state.community_identifier.set(community_identifier.get()),
        heritage_asset_app.state.stewardship_model.set(stewardship_model.get()),
        heritage_asset_app.state.restoration_required.set(Int(0)),  # False
        heritage_asset_app.state.conservation_status.set(Bytes("documented"))
    ])
    
    # Initialize funding variables
    init_funding = Seq([
        heritage_asset_app.state.funding_pool.set(Int(0)),
        heritage_asset_app.state.funding_target.set(Int(0)),
        heritage_asset_app.state.project_phases.set(Int(0)),
        heritage_asset_app.state.current_phase.set(Int(0))
    ])
    
    # Initialize revenue sharing model with defaults
    # Default: 60% community, 30% investors, 10% conservation
    init_revenue_sharing = Seq([
        heritage_asset_app.state.community_share.set(Int(6000)),  # 60.00% (stored as basis points)
        heritage_asset_app.state.investor_share.set(Int(3000)),   # 30.00%
        heritage_asset_app.state.conservation_share.set(Int(1000)) # 10.00%
    ])
    
    # Initialize ownership token status
    init_ownership_tokens = Seq([
        heritage_asset_app.state.has_ownership_tokens.set(Int(0))  # False
    ])
    
    # NEW: Register with Asset Registry for BOLI allocation
    register_for_boli = ContractBase.register_with_asset_registry(
        heritage_asset_app,
        name.get(),
        Bytes("heritage-asset"),
        jurisdiction_code.get(),
        boli_allocation.get()
    )
    
    return Seq([
        assert_creator,
        create_token,
        store_asset_id,
        store_base_info,
        store_heritage_info,
        init_funding,
        init_revenue_sharing,
        init_ownership_tokens,
        # Only register with BOLI if allocation amount is greater than 0
        If(
            boli_allocation.get() > Int(0),
            register_for_boli,
            Seq([])  # No-op if no BOLI allocation
        ),
        output.set(asset_id)
    ])

# ADDED: Update funding status method
@heritage_asset_app.external
def update_funding_status(
    new_status: abi.String,
    *,
    output: abi.Bool
) -> Expr:
    """Updates the heritage asset funding status"""
    
    # Only allow the creator to update status
    is_authorized = Txn.sender() == Global.creator_address()
    
    assert_authorized = Assert(
        is_authorized,
        comment="Only creator or Asset Registry can update status"
    )
    
    # Update the investment status
    update_status = ContractBase.update_investment_status(
        heritage_asset_app,
        new_status.get()
    )
    
    return Seq([
        assert_authorized,
        update_status,
        output.set(Int(1))  # True
    ])

# MODIFIED: Enhanced asset revenue registration to distribute to token holders
@heritage_asset_app.external
def register_asset_revenue(
    asset_id: abi.Uint64,
    revenue_amount: abi.Uint64,
    revenue_source: abi.String,
    *,
    output: abi.Bool
) -> Expr:
    """Register revenue generated by the heritage asset and distribute to token holders"""
    
    # Ensure the asset exists and matches our records
    asset_id_check = Assert(
        heritage_asset_app.state.asset_id.get() == asset_id.get(),
        comment="Asset ID mismatch"
    )
    
    # Verify the sender is authorized
    auth_check = Assert(
        Or(
            Txn.sender() == Global.creator_address(),
            Txn.sender() == heritage_asset_app.state.community_identifier.get()
        ),
        comment="Only the creator or community steward can register revenue"
    )
    
    # Update metadata with revenue information
    updated_metadata = Concat(
        heritage_asset_app.state.metadata.get(),
        Bytes("|revenue:"),
        Int2Str(revenue_amount.get()),
        Bytes(":"),
        revenue_source.get(),
        Bytes(":"),
        Int2Str(Global.latest_timestamp())
    )
    
    # Create distribution note
    distribution_note = Concat(
        Bytes("Heritage Revenue: "),
        Int2Str(revenue_amount.get()),
        Bytes(" | Source: "),
        revenue_source.get()
    )
    
    # Distribute revenue to token holders
    distribute = ContractBase.distribute_revenue(
        heritage_asset_app,
        revenue_amount.get(),
        Bytes("heritage-revenue"),
        distribution_note
    )
    
    return Seq([
        asset_id_check,
        auth_check,
        heritage_asset_app.state.metadata.set(updated_metadata),
        heritage_asset_app.state.last_updated.set(Global.latest_timestamp()),
        # Only distribute if the asset is in active status
        If(
            heritage_asset_app.state.investment_status.get() == Bytes("active"),
            distribute,
            Seq([])  # No-op if not active
        ),
        output.set(Int(1))  # True
    ])

@heritage_asset_app.external
def update_heritage_documentation(
    asset_id: abi.Uint64,
    new_documentation_hash: abi.String,
    document_type: abi.String,
    new_conservation_status: abi.String
) -> Expr:
    """Update heritage asset documentation and status"""
    
    # Ensure the heritage asset exists and matches our records
    asset_id_check = Assert(
        heritage_asset_app.state.asset_id.get() == asset_id.get(),
        comment="Asset ID mismatch"
    )
    
    # Check authorization - only creator or community can update
    auth_check = Assert(
        Or(
            Txn.sender() == Global.creator_address(),
            Txn.sender() == heritage_asset_app.state.community_identifier.get()
        ),
        comment="Only the creator or community steward can update documentation"
    )
    
    # Update document reference
    updated_metadata = Concat(
        heritage_asset_app.state.metadata.get(),
        Bytes("|"),
        document_type.get(),
        Bytes(":"),
        new_documentation_hash.get()
    )
    
    # Update conservation status if provided
    update_status = If(
        Len(new_conservation_status.get()) > Int(0),
        heritage_asset_app.state.conservation_status.set(new_conservation_status.get()),
        Seq([])  # No-op if empty
    )
    
    return Seq([
        asset_id_check,
        auth_check,
        heritage_asset_app.state.metadata.set(updated_metadata),
        update_status,
        heritage_asset_app.state.last_updated.set(Global.latest_timestamp())
    ])

@heritage_asset_app.external
def create_restoration_project(
    asset_id: abi.Uint64,
    funding_target: abi.Uint64,
    project_deadline: abi.Uint64,
    project_phases_count: abi.Uint64,
    project_verifier: abi.Address,
    project_details_hash: abi.String
) -> Expr:
    """Create a restoration/conservation project for the heritage asset"""
    
    # Ensure the asset exists and matches our records
    asset_id_check = Assert(
        heritage_asset_app.state.asset_id.get() == asset_id.get(),
        comment="Asset ID mismatch"
    )
    
    # Only allow the creator or community to create projects
    auth_check = Assert(
        Or(
            Txn.sender() == Global.creator_address(),
            Txn.sender() == heritage_asset_app.state.community_identifier.get()
        ),
        comment="Only the creator or community steward can create restoration projects"
    )
    
    # Verify parameters
    verify_phases = Assert(project_phases_count.get() > Int(0), comment="Project must have at least one phase")
    verify_deadline = Assert(project_deadline.get() > Global.latest_timestamp(), comment="Project deadline must be in the future")
    verify_funding = Assert(funding_target.get() > Int(0), comment="Funding target must be positive")
    
    # Set project parameters
    set_project_params = Seq([
        heritage_asset_app.state.funding_target.set(funding_target.get()),
        heritage_asset_app.state.project_deadline.set(project_deadline.get()),
        heritage_asset_app.state.project_phases.set(project_phases_count.get()),
        heritage_asset_app.state.current_phase.set(Int(1)),  # Start at phase 1
        heritage_asset_app.state.project_verifier.set(project_verifier.get()),
        heritage_asset_app.state.restoration_required.set(Int(1))  # True
    ])
    
    # Update metadata with project details
    updated_metadata = Concat(
        heritage_asset_app.state.metadata.get(),
        Bytes("|project:"),
        project_details_hash.get()
    )
    
    # Set conservation status to "restoration-planned"
    set_conservation_status = heritage_asset_app.state.conservation_status.set(Bytes("restoration-planned"))
    
    return Seq([
        asset_id_check,
        auth_check,
        verify_phases,
        verify_deadline,
        verify_funding,
        set_project_params,
        heritage_asset_app.state.metadata.set(updated_metadata),
        set_conservation_status,
        heritage_asset_app.state.last_updated.set(Global.latest_timestamp())
    ])

@heritage_asset_app.external
def contribute_to_project(
    asset_id: abi.Uint64,
    contribution_amount: abi.Uint64
) -> Expr:
    """Contribute funds to a heritage restoration project"""
    
    # Ensure the asset exists and matches our records
    asset_id_check = Assert(
        heritage_asset_app.state.asset_id.get() == asset_id.get(),
        comment="Asset ID mismatch"
    )
    
    # Verify the project is active
    verify_active = Assert(
        heritage_asset_app.state.restoration_required.get() == Int(1),
        comment="No active restoration project"
    )
    
    verify_deadline = Assert(
        Global.latest_timestamp() < heritage_asset_app.state.project_deadline.get(),
        comment="Project deadline has passed"
    )
    
    # Check contribution amount
    verify_amount = Assert(
        contribution_amount.get() > Int(0),
        comment="Contribution must be positive"
    )
    
    # Update funding pool
    update_funding = heritage_asset_app.state.funding_pool.set(
        heritage_asset_app.state.funding_pool.get() + contribution_amount.get()
    )
    
    # Note: In a full implementation, you would track individual contributions
    # This would require using a BoxMapping for contributors, similar to the bond contract
    
    # For now, we'll just track the total funding pool
    return Seq([
        asset_id_check,
        verify_active,
        verify_deadline,
        verify_amount,
        update_funding,
        heritage_asset_app.state.last_updated.set(Global.latest_timestamp())
    ])

@heritage_asset_app.external
def issue_ownership_tokens(
    asset_id: abi.Uint64,
    token_name: abi.String,
    token_unit_name: abi.String,
    *,
    output: abi.Uint64
) -> Expr:
    """Issue ownership tokens for contributors based on their contribution"""
    
    # Ensure the asset exists and matches our records
    asset_id_check = Assert(
        heritage_asset_app.state.asset_id.get() == asset_id.get(),
        comment="Asset ID mismatch"
    )
    
    # Only creator or community steward can issue tokens
    auth_check = Assert(
        Or(
            Txn.sender() == Global.creator_address(),
            Txn.sender() == heritage_asset_app.state.community_identifier.get()
        ),
        comment="Only the creator or community steward can issue ownership tokens"
    )
    
    # Check that tokens haven't already been issued
    check_not_issued = Assert(
        heritage_asset_app.state.has_ownership_tokens.get() == Int(0),
        comment="Ownership tokens already issued"
    )
    
    # Check that funding reached the target
    check_funding = Assert(
        heritage_asset_app.state.funding_pool.get() >= heritage_asset_app.state.funding_target.get(),
        comment="Funding target not reached"
    )
    
    # Create note for token
    note = Concat(
        Bytes("Boli Heritage Ownership Token for asset: "),
        Int2Str(asset_id.get())
    )
    
    # Create ownership tokens (1 million tokens for fine-grained distribution)
    create_token = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetConfig,
            TxnField.config_asset_total: Int(1000000),
            TxnField.config_asset_decimals: Int(0),
            TxnField.config_asset_default_frozen: Int(0),
            TxnField.config_asset_manager: Global.current_application_address(),
            TxnField.config_asset_reserve: Global.current_application_address(),
            TxnField.config_asset_freeze: Global.current_application_address(),
            TxnField.config_asset_clawback: Global.current_application_address(),
            TxnField.config_asset_unit_name: token_unit_name.get(),
            TxnField.config_asset_name: token_name.get(),
            TxnField.config_asset_url: Concat(Bytes("ipfs://"), heritage_asset_app.state.metadata.get()),
            TxnField.note: note
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Store token ID
    token_id = InnerTxn.created_asset_id()
    store_token_id = heritage_asset_app.state.ownership_token_id.set(token_id)
    
    # Mark tokens as issued
    mark_issued = heritage_asset_app.state.has_ownership_tokens.set(Int(1))  # True
    
    return Seq([
        asset_id_check,
        auth_check,
        check_not_issued,
        check_funding,
        create_token,
        store_token_id,
        mark_issued,
        heritage_asset_app.state.last_updated.set(Global.latest_timestamp()),
        output.set(token_id)
    ])

@heritage_asset_app.external
def distribute_community_tokens(
    asset_id: abi.Uint64
) -> Expr:
    """Distribute ownership tokens to the community steward"""
    
    # Ensure the asset exists and matches our records
    asset_id_check = Assert(
        heritage_asset_app.state.asset_id.get() == asset_id.get(),
        comment="Asset ID mismatch"
    )
    
    # Check that tokens have been issued
    check_issued = Assert(
        heritage_asset_app.state.has_ownership_tokens.get() == Int(1),
        comment="Ownership tokens not yet issued"
    )
    
    # Only creator or community steward can distribute tokens
    auth_check = Assert(
        Or(
            Txn.sender() == Global.creator_address(),
            Txn.sender() == heritage_asset_app.state.community_identifier.get()
        ),
        comment="Only the creator or community steward can distribute tokens"
    )
    
    # Calculate community's portion (stored in basis points)
    # 1,000,000 tokens * (community_share / 10000)
    community_tokens = Div(
        Mul(Int(1000000), heritage_asset_app.state.community_share.get()),
        Int(10000)
    )
    
    # Transfer tokens to community steward
    send_tokens = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: heritage_asset_app.state.ownership_token_id.get(),
            TxnField.asset_amount: community_tokens,
            TxnField.asset_receiver: heritage_asset_app.state.community_identifier.get(),
            TxnField.asset_sender: Global.current_application_address()
        }),
        InnerTxnBuilder.Submit()
    )
    
    return Seq([
        asset_id_check,
        check_issued,
        auth_check,
        send_tokens,
        heritage_asset_app.state.last_updated.set(Global.latest_timestamp())
    ])

@heritage_asset_app.external
def verify_phase_completion(
    asset_id: abi.Uint64,
    phase_number: abi.Uint64,
    verification_documentation: abi.String
) -> Expr:
    """Verify completion of a project phase"""
    
    # Ensure the asset exists and matches our records
    asset_id_check = Assert(
        heritage_asset_app.state.asset_id.get() == asset_id.get(),
        comment="Asset ID mismatch"
    )
    
    # Only the designated verifier can verify phase completion
    auth_check = Assert(
        Txn.sender() == heritage_asset_app.state.project_verifier.get(),
        comment="Only the project verifier can verify completion"
    )
    
    # Verify phase is valid
    verify_phase = Assert(
        And(
            phase_number.get() > Int(0),
            phase_number.get() <= heritage_asset_app.state.project_phases.get()
        ),
        comment="Invalid phase number"
    )
    
    # Verify current phase matches
    verify_current_phase = Assert(
        heritage_asset_app.state.current_phase.get() == phase_number.get(),
        comment="This is not the current phase"
    )
    
    # Update metadata with verification documentation
    updated_metadata = Concat(
        heritage_asset_app.state.metadata.get(),
        Bytes("|phase"),
        Int2Str(phase_number.get()),
        Bytes(":"),
        verification_documentation.get()
    )
    
    # Check if this is the final phase
    is_final_phase = phase_number.get() == heritage_asset_app.state.project_phases.get()
    
    # If final phase, mark project as completed, otherwise advance to next phase
    handle_completion = If(
        is_final_phase,
        Seq([
            # This was the final phase, mark project as completed
            heritage_asset_app.state.restoration_required.set(Int(0)),  # False
            heritage_asset_app.state.conservation_status.set(Bytes("restored"))
        ]),
        Seq([
            # Advance to next phase
            heritage_asset_app.state.current_phase.set(phase_number.get() + Int(1))
        ])
    )
    
    return Seq([
        asset_id_check,
        auth_check,
        verify_phase,
        verify_current_phase,
        heritage_asset_app.state.metadata.set(updated_metadata),
        handle_completion,
        heritage_asset_app.state.last_updated.set(Global.latest_timestamp())
    ])

@heritage_asset_app.external
def update_revenue_shares(
    asset_id: abi.Uint64,
    new_community_share: abi.Uint64,
    new_investor_share: abi.Uint64,
    new_conservation_share: abi.Uint64
) -> Expr:
    """Update revenue distribution shares"""
    
    # Ensure the asset exists and matches our records
    asset_id_check = Assert(
        heritage_asset_app.state.asset_id.get() == asset_id.get(),
        comment="Asset ID mismatch"
    )
    
    # Only creator or community steward can update shares
    auth_check = Assert(
        Or(
            Txn.sender() == Global.creator_address(),
            Txn.sender() == heritage_asset_app.state.community_identifier.get()
        ),
        comment="Only the creator or community steward can update shares"
    )
    
    # Verify total is 100% (10000 basis points)
    verify_total = Assert(
        new_community_share.get() + new_investor_share.get() + new_conservation_share.get() == Int(10000),
        comment="Shares must total 100% (10000 basis points)"
    )
    
    # Update shares
    update_shares = Seq([
        heritage_asset_app.state.community_share.set(new_community_share.get()),
        heritage_asset_app.state.investor_share.set(new_investor_share.get()),
        heritage_asset_app.state.conservation_share.set(new_conservation_share.get())
    ])
    
    return Seq([
        asset_id_check,
        auth_check,
        verify_total,
        update_shares,
        heritage_asset_app.state.last_updated.set(Global.latest_timestamp())
    ])

@heritage_asset_app.external(read_only=True)
def get_heritage_asset_details(
    asset_id: abi.Uint64,
    *,
    output: abi.String
) -> Expr:
    """Get detailed heritage asset information"""
    
    # Ensure the asset exists and matches our records
    asset_id_check = Assert(
        heritage_asset_app.state.asset_id.get() == asset_id.get(),
        comment="Asset ID mismatch"
    )
    
    # Build the main information
    main_info = Concat(
        Bytes("Heritage Asset ID: "), Int2Str(heritage_asset_app.state.asset_id.get()),
        Bytes(" | Type: "), heritage_asset_app.state.heritage_type.get(),
        Bytes(" | Significance: "), heritage_asset_app.state.cultural_significance.get(),
        Bytes(" | Legal Status: "), heritage_asset_app.state.legal_status.get(),
        Bytes(" | Conservation: "), heritage_asset_app.state.conservation_status.get(),
        Bytes(" | Jurisdiction: "), heritage_asset_app.state.jurisdiction_code.get(),
        Bytes(" | Stewardship: "), heritage_asset_app.state.stewardship_model.get(),
        Bytes(" | Investment Status: "), heritage_asset_app.state.investment_status.get()
    )
    
    # Add restoration project info if active
    restoration_info = If(
        heritage_asset_app.state.restoration_required.get() == Int(1),
        Concat(
            Bytes(" | Restoration: Active (Phase "),
            Int2Str(heritage_asset_app.state.current_phase.get()),
            Bytes(" of "),
            Int2Str(heritage_asset_app.state.project_phases.get()),
            Bytes(")"),
            Bytes(" | Funding: "),
            Int2Str(heritage_asset_app.state.funding_pool.get()),
            Bytes(" / "),
            Int2Str(heritage_asset_app.state.funding_target.get())
        ),
        Bytes("")  # Empty if no restoration project
    )
    
    # Add ownership token info if issued
    token_info = If(
        heritage_asset_app.state.has_ownership_tokens.get() == Int(1),
        Concat(
            Bytes(" | Ownership Token: "),
            Int2Str(heritage_asset_app.state.ownership_token_id.get())
        ),
        Bytes("")  # Empty if no ownership tokens
    )
    
    # Combine all details
    details = Concat(main_info, restoration_info, token_info)
    
    return Seq([
        asset_id_check,
        output.set(details)
    ])

if __name__ == "__main__":
    # Compile and export the app
    app_spec = heritage_asset_app.build()
    app_spec.export("artifacts/heritage_asset")