# ~/Desktop/boli/projects/boli/smart_contracts/pillars_connector/contract.py

from pyteal import *
from beaker import *
from beaker.lib.storage import BoxMapping

class PillarsStorageState:
    """State for Pillars Storage Connector"""
    
    # Admin control
    admin_address = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Address of the admin"
    )
    
    # Registry of verified data
    hash_registry = BoxMapping(
        key_type=abi.String,  # Content identifier
        value_type=abi.String,  # Pillars storage location
        prefix=Bytes("hash")
    )
    
    # Verification status - storing "true" or "false" as strings
    verification_status = BoxMapping(
        key_type=abi.String,  # Content identifier
        value_type=abi.String,  # Whether it's been verified as string
        prefix=Bytes("verified")
    )

pillars_connector = Application(
    "PillarsStorageConnector",
    descr="Connector for Pillars Verifiable Storage",
    state=PillarsStorageState()
)

@pillars_connector.create
def create():
    """Initialize the connector"""
    return Seq([
        pillars_connector.state.admin_address.set(Global.creator_address()),
        Approve()
    ])

@pillars_connector.external
def register_content(
    content_id: abi.String, 
    pillars_location: abi.String,
    content_hash: abi.String,
    *,
    output: abi.Bool
) -> Expr:
    """Register content stored in Pillars"""
    return Seq([
        # Only allow authorized parties to register content
        Assert(
            Or(
                Txn.sender() == pillars_connector.state.admin_address.get(),
                # Add other authorized addresses as needed
            ),
            comment="Unauthorized sender"
        ),
        
        # Store the Pillars location
        pillars_connector.state.hash_registry[content_id].set(pillars_location.get()),
        
        # Mark as unverified initially
        pillars_connector.state.verification_status[content_id].set(Bytes("false")),
        
        output.set(Int(1))
    ])

@pillars_connector.external
def verify_content(
    content_id: abi.String,
    verification_proof: abi.String,
    *,
    output: abi.Bool
) -> Expr:
    """Verify content against proof from Pillars"""
    return Seq([
        # Ensure content is registered
        Assert(
            pillars_connector.state.hash_registry[content_id].exists(),
            comment="Content not registered"
        ),
        
        # Here you would validate the verification proof
        # This is a simplified placeholder - actual verification would depend on Pillars API
        pillars_connector.state.verification_status[content_id].set(Bytes("true")),
        
        output.set(Int(1))
    ])

@pillars_connector.external(read_only=True)
def get_content_location(
    content_id: abi.String,
    *,
    output: abi.String
) -> Expr:
    """Get the Pillars location for registered content"""
    return Seq([
        Assert(
            pillars_connector.state.hash_registry[content_id].exists(),
            comment="Content not registered"
        ),
        
        output.set(pillars_connector.state.hash_registry[content_id].get())
    ])

@pillars_connector.external(read_only=True)
def is_content_verified(
    content_id: abi.String,
    *,
    output: abi.Bool
) -> Expr:
    """Check if content has been verified"""
    return Seq([
        If(pillars_connector.state.verification_status[content_id].exists(),
           # Check if the status is "true"
           output.set(pillars_connector.state.verification_status[content_id].get() == Bytes("true")),
           output.set(Int(0))
        )
    ])

if __name__ == "__main__":
    # Compile and export the app
    app_spec = pillars_connector.build()
    app_spec.export("artifacts/pillars_connector")