# ~/Desktop/boli/projects/boli/smart_contracts/boli_token/contract.py

from pyteal import *
from beaker import *
from beaker.lib.storage import BoxMapping

class BOLITokenState:
    """State class for BOLI Token contract"""
    
    # Token information
    token_id = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Asset ID of the BOLI token"
    )
    
    total_supply = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Total supply of BOLI tokens"
    )
    
    circulating_supply = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Circulating supply of BOLI tokens"
    )
    
    # Treasury management
    stablecoin_reserve_id = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="Asset ID of the reserve stablecoin"
    )
    
    treasury_address = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Address of the treasury that holds stablecoin reserves"
    )
    
    asset_registry_id = GlobalStateValue(
        stack_type=TealType.uint64,
        descr="App ID of the asset registry"
    )
    
    # Security & management
    admin_address = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Address of the admin"
    )
    
    paused = GlobalStateValue(
        stack_type=TealType.uint64,  # 0 = false, 1 = true
        descr="Whether token operations are paused"
    )
    
    # Use BoxMapping for address opt-in tracking
    address_opted_in = BoxMapping(
        key_type=abi.Address,
        value_type=abi.Bool,
        prefix=Bytes("opt")
    )

boli_token_app = Application(
    "BOLIToken",
    descr="BOLI Stablecoin Token backed 1:1 by stablecoins",
    state=BOLITokenState()
)

@boli_token_app.create
def create():
    """Initialize the BOLI token contract"""
    return Seq([
        boli_token_app.state.admin_address.set(Global.creator_address()),
        boli_token_app.state.paused.set(Int(0)),  # Not paused initially
        boli_token_app.state.total_supply.set(Int(0)),
        boli_token_app.state.circulating_supply.set(Int(0)),
        Approve()
    ])

@boli_token_app.external
def create_token(
    token_name: abi.String,
    unit_name: abi.String,
    treasury_address: abi.Address,
    reserve_asset_id: abi.Uint64,
    asset_registry_id: abi.Uint64,
    *,
    output: abi.Uint64
) -> Expr:
    """Creates the BOLI token ASA"""
    
    # Only allow the admin to create the token
    assert_admin = Assert(
        Txn.sender() == boli_token_app.state.admin_address.get(),
        comment="Only admin can create the token"
    )
    
    # Verify the token hasn't been created yet
    assert_not_created = Assert(
        boli_token_app.state.token_id.get() == Int(0),
        comment="Token already created"
    )
    
    # Create note with token information
    note = Concat(
        Bytes("BOLI Token: Stablecoin backed 1:1 by reserves. Treasury: "),
        treasury_address.get()
    )
    
    # Create the BOLI token as an ASA
    create_token = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetConfig,
            TxnField.config_asset_total: Int(1000000000),  # 1 billion units (with decimals)
            TxnField.config_asset_decimals: Int(6),  # 6 decimal places
            TxnField.config_asset_default_frozen: Int(0),
            TxnField.config_asset_manager: Global.current_application_address(),
            TxnField.config_asset_reserve: treasury_address.get(),
            TxnField.config_asset_freeze: Global.current_application_address(),
            TxnField.config_asset_clawback: Global.current_application_address(),
            TxnField.config_asset_unit_name: unit_name.get(),
            TxnField.config_asset_name: token_name.get(),
            TxnField.note: note
        }),
        InnerTxnBuilder.Submit()
    )
    
    # Store the token information
    store_token_info = Seq([
        boli_token_app.state.token_id.set(InnerTxn.created_asset_id()),
        boli_token_app.state.treasury_address.set(treasury_address.get()),
        boli_token_app.state.stablecoin_reserve_id.set(reserve_asset_id.get()),
        boli_token_app.state.asset_registry_id.set(asset_registry_id.get())
    ])
    
    return Seq([
        assert_admin,
        assert_not_created,
        create_token,
        store_token_info,
        output.set(InnerTxn.created_asset_id())
    ])

@boli_token_app.external
def mint_tokens(
    amount: abi.Uint64,
    receiver: abi.Address,
    stablecoin_deposit_txn_id: abi.String,
    *,
    output: abi.Bool
) -> Expr:
    """Mint new BOLI tokens after stablecoin deposit confirmation"""
    
    # Only allow the admin or treasury to mint tokens
    is_authorized = Or(
        Txn.sender() == boli_token_app.state.admin_address.get(),
        Txn.sender() == boli_token_app.state.treasury_address.get()
    )
    
    assert_authorized = Assert(
        is_authorized,
        comment="Only admin or treasury can mint tokens"
    )
    
    # Check that token operations are not paused
    assert_not_paused = Assert(
        boli_token_app.state.paused.get() == Int(0),
        comment="Token operations are paused"
    )
    
    # Verify token is created
    assert_token_created = Assert(
        boli_token_app.state.token_id.get() != Int(0),
        comment="Token not created yet"
    )
    
    # Verify that receiver is opted in
    is_opted_in = boli_token_app.state.address_opted_in[receiver].exists()
    assert_opted_in = Assert(
        is_opted_in,
        comment="Receiver not opted in to BOLI token"
    )
    
    # Update supply tracking
    update_supply = Seq([
        boli_token_app.state.circulating_supply.set(
            boli_token_app.state.circulating_supply.get() + amount.get()
        )
    ])
    
    # Execute the token transfer via an inner transaction
    send_tokens = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: boli_token_app.state.token_id.get(),
            TxnField.asset_amount: amount.get(),
            TxnField.asset_receiver: receiver.get(),
            TxnField.note: Concat(
                Bytes("BOLI Token Mint - Stablecoin Deposit Txn: "),
                stablecoin_deposit_txn_id.get()
            )
        }),
        InnerTxnBuilder.Submit()
    )
    
    return Seq([
        assert_authorized,
        assert_not_paused,
        assert_token_created,
        assert_opted_in,
        update_supply,
        send_tokens,
        output.set(Int(1))  # True
    ])

@boli_token_app.external
def burn_tokens(
    amount: abi.Uint64,
    sender: abi.Address,
    *,
    output: abi.Bool
) -> Expr:
    """Burn BOLI tokens (when stablecoins are withdrawn)"""
    
    # Only allow the admin or treasury to burn tokens
    is_authorized = Or(
        Txn.sender() == boli_token_app.state.admin_address.get(),
        Txn.sender() == boli_token_app.state.treasury_address.get()
    )
    
    assert_authorized = Assert(
        is_authorized,
        comment="Only admin or treasury can burn tokens"
    )
    
    # Check that token operations are not paused
    assert_not_paused = Assert(
        boli_token_app.state.paused.get() == Int(0),
        comment="Token operations are paused"
    )
    
    # Verify token is created
    assert_token_created = Assert(
        boli_token_app.state.token_id.get() != Int(0),
        comment="Token not created yet"
    )
    
    # Update supply tracking
    update_supply = Seq([
        boli_token_app.state.circulating_supply.set(
            boli_token_app.state.circulating_supply.get() - amount.get()
        )
    ])
    
    # Execute the token burn via an inner transaction
    burn_tokens = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: boli_token_app.state.token_id.get(),
            TxnField.asset_amount: amount.get(),
            TxnField.asset_sender: sender.get(),
            TxnField.asset_receiver: Global.current_application_address(),
            TxnField.note: Bytes("BOLI Token Burn - Stablecoin Withdrawal")
        }),
        InnerTxnBuilder.Submit()
    )
    
    return Seq([
        assert_authorized,
        assert_not_paused,
        assert_token_created,
        update_supply,
        burn_tokens,
        output.set(Int(1))  # True
    ])

@boli_token_app.external
def opt_in_to_token(
    *,
    output: abi.Bool
) -> Expr:
    """Opt in to the BOLI token"""
    
    # Verify token is created
    assert_token_created = Assert(
        boli_token_app.state.token_id.get() != Int(0),
        comment="Token not created yet"
    )
    
    # Store opt-in status
    store_opt_in = boli_token_app.state.address_opted_in[Txn.sender()].set(True)
    
    # Execute the opt-in via an inner transaction
    opt_in_txn = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: boli_token_app.state.token_id.get(),
            TxnField.asset_amount: Int(0),
            TxnField.asset_receiver: Txn.sender(),
            TxnField.note: Bytes("BOLI Token Opt-In")
        }),
        InnerTxnBuilder.Submit()
    )
    
    return Seq([
        assert_token_created,
        store_opt_in,
        opt_in_txn,
        output.set(Int(1))  # True
    ])

@boli_token_app.external
def transfer_tokens(
    amount: abi.Uint64,
    sender: abi.Address,
    receiver: abi.Address,
    *,
    output: abi.Bool
) -> Expr:
    """Transfer BOLI tokens between accounts"""
    
    # Check authorization - sender must be the transaction sender
    assert_sender = Assert(
        Txn.sender() == sender.get(),
        comment="Sender must be calling the transfer"
    )
    
    # Check that token operations are not paused
    assert_not_paused = Assert(
        boli_token_app.state.paused.get() == Int(0),
        comment="Token operations are paused"
    )
    
    # Verify token is created
    assert_token_created = Assert(
        boli_token_app.state.token_id.get() != Int(0),
        comment="Token not created yet"
    )
    
    # Verify that receiver is opted in
    is_opted_in = boli_token_app.state.address_opted_in[receiver].exists()
    assert_opted_in = Assert(
        is_opted_in,
        comment="Receiver not opted in to BOLI token"
    )
    
    # Execute the token transfer via an inner transaction
    transfer_tokens = Seq(
        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.SetFields({
            TxnField.type_enum: TxnType.AssetTransfer,
            TxnField.xfer_asset: boli_token_app.state.token_id.get(),
            TxnField.asset_amount: amount.get(),
            TxnField.asset_sender: sender.get(),
            TxnField.asset_receiver: receiver.get(),
            TxnField.note: Bytes("BOLI Token Transfer")
        }),
        InnerTxnBuilder.Submit()
    )
    
    return Seq([
        assert_sender,
        assert_not_paused,
        assert_token_created,
        assert_opted_in,
        transfer_tokens,
        output.set(Int(1))  # True
    ])

@boli_token_app.external
def pause_token_operations(
    pause_state: abi.Bool,
    *,
    output: abi.Bool
) -> Expr:
    """Pause or unpause token operations"""
    
    # Only allow the admin to pause/unpause
    assert_admin = Assert(
        Txn.sender() == boli_token_app.state.admin_address.get(),
        comment="Only admin can pause/unpause"
    )
    
    # Update pause state
    update_pause = boli_token_app.state.paused.set(
        If(pause_state.get(), Int(1), Int(0))
    )
    
    return Seq([
        assert_admin,
        update_pause,
        output.set(Int(1))  # True
    ])

@boli_token_app.external
def change_admin(
    new_admin: abi.Address,
    *,
    output: abi.Bool
) -> Expr:
    """Change the admin address"""
    
    # Only allow the current admin to change admin
    assert_admin = Assert(
        Txn.sender() == boli_token_app.state.admin_address.get(),
        comment="Only current admin can change admin"
    )
    
    # Update admin address
    update_admin = boli_token_app.state.admin_address.set(new_admin.get())
    
    return Seq([
        assert_admin,
        update_admin,
        output.set(Int(1))  # True
    ])

@boli_token_app.external(read_only=True)
def get_token_info(
    *,
    output: abi.String
) -> Expr:
    """Get BOLI token information"""
    
    # Build the token information string
    token_info = Concat(
        Bytes("BOLI Token ID: "), Int2Str(boli_token_app.state.token_id.get()),
        Bytes(" | Circulating Supply: "), Int2Str(boli_token_app.state.circulating_supply.get()),
        Bytes(" | Treasury: "), boli_token_app.state.treasury_address.get(),
        Bytes(" | Status: "), If(
            boli_token_app.state.paused.get() == Int(1),
            Bytes("Paused"),
            Bytes("Active")
        )
    )
    
    return output.set(token_info)

# Helper function to convert integer to string
def Int2Str(i: Expr) -> Expr:
    """Convert an integer expression to a string expression using Itob."""
    return Extract(Itob(i), Int(0), Int(8))

if __name__ == "__main__":
    # Compile and export the app
    app_spec = boli_token_app.build()
    app_spec.export("artifacts/boli_token")