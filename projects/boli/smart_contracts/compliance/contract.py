# ~/Desktop/boli/projects/boli/smart_contracts/compliance/contract.py

from pyteal import *
from beaker import *
from beaker.lib.storage import BoxMapping

# Define a class to hold state
class ComplianceState:
    # Main administrator addresses
    regulator = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Address of the main regulator"
    )
    
    kyc_provider = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Address of the KYC provider"
    )
    
    # Use BoxMapping for jurisdiction regulators
    jurisdiction_regulators = BoxMapping(
        key_type=abi.String,
        value_type=abi.Address,
        prefix=Bytes("jrs")
    )
    
    # Use BoxMapping for KYC status
    kyc_status = BoxMapping(
        key_type=abi.Address,
        value_type=abi.String,
        prefix=Bytes("kyc")
    )
    
    # Use BoxMapping for KYC expiration
    kyc_expiration = BoxMapping(
        key_type=abi.Address,
        value_type=abi.Uint64,
        prefix=Bytes("exp")
    )

# Create application with state
compliance_app = Application(
    "ComplianceContract",
    descr="Compliance Contract for Boli platform",
    state=ComplianceState()
)

# Initialize function to set up the contract
@compliance_app.create
def initialize(regulator_addr: abi.Address, kyc_provider_addr: abi.Address) -> Expr:
    """Initialize the contract with regulator and KYC provider addresses"""
    return Seq(
        compliance_app.state.regulator.set(regulator_addr.get()),
        compliance_app.state.kyc_provider.set(kyc_provider_addr.get()),
        Approve()
    )

# Register jurisdiction regulator
@compliance_app.external
def register_jurisdiction_regulator(jurisdiction_code: abi.String, regulator_address: abi.Address) -> Expr:
    """Registers a regulator for a specific jurisdiction"""
    return Seq(
        # Only allow the main regulator to register jurisdiction regulators
        Assert(
            Txn.sender() == compliance_app.state.regulator.get(),
            comment="Only the main regulator can register jurisdiction regulators"
        ),
        
        # Set the regulator for this jurisdiction
        compliance_app.state.jurisdiction_regulators[jurisdiction_code].set(regulator_address),
        
        Approve()
    )

# Set KYC status for an account
@compliance_app.external
def set_kyc_status(account_address: abi.Address, status: abi.String, expiration_timestamp: abi.Uint64) -> Expr:
    """Sets KYC status for an account"""
    return Seq(
        # Only allow the KYC provider or main regulator to set KYC status
        Assert(
            Or(
                Txn.sender() == compliance_app.state.kyc_provider.get(),
                Txn.sender() == compliance_app.state.regulator.get()
            ),
            comment="Only the KYC provider or main regulator can set KYC status"
        ),
        
        # Validate status (approved, pending, rejected)
        Assert(
            Or(
                status.get() == Bytes("approved"),
                status.get() == Bytes("pending"),
                status.get() == Bytes("rejected")
            ),
            comment="Invalid KYC status"
        ),
        
        # Store KYC status
        compliance_app.state.kyc_status[account_address].set(status),
        
        # Store expiration timestamp
        compliance_app.state.kyc_expiration[account_address].set(expiration_timestamp),
        
        Approve()
    )

# Get KYC status for an account
@compliance_app.external(read_only=True)
def get_kyc_status(account_address: abi.Address, *, output: abi.String) -> Expr:
    """Gets KYC status for an account"""
    # Variables to store exists check results (must convert to TealType.uint64)
    status_exists = ScratchVar(TealType.uint64)
    expiration_exists = ScratchVar(TealType.uint64)
    # Variable to store the expiration time if needed
    expiration = abi.Uint64()
    
    return Seq(
        # Check if KYC status exists and store result as uint64 (0/1)
        status_exists.store(
            If(compliance_app.state.kyc_status[account_address].exists(),
               Int(1),
               Int(0))
        ),
        
        # If status doesn't exist, return not_registered
        If(status_exists.load() == Int(0),
           # True branch - status doesn't exist
           output.set(Bytes("not_registered")),
           # False branch - status exists
           Seq(
               # Check if expiration exists and store result
               expiration_exists.store(
                   If(compliance_app.state.kyc_expiration[account_address].exists(),
                      Int(1),
                      Int(0))
               ),
               
               # If expiration exists, check if it's expired
               If(expiration_exists.load() == Int(1),
                  # True branch - expiration exists
                  Seq(
                      # Load expiration into ABI type
                      compliance_app.state.kyc_expiration[account_address].store_into(expiration),
                      
                      # Check if expired
                      If(And(
                          expiration.get() > Int(0),
                          Global.latest_timestamp() > expiration.get()
                      ),
                         # True branch - expired
                         output.set(Bytes("expired")),
                         # False branch - not expired, return status
                         output.set(compliance_app.state.kyc_status[account_address].get())
                      )
                  ),
                  # False branch - no expiration, return status
                  output.set(compliance_app.state.kyc_status[account_address].get())
               )
           )
        )
    )

# Get the regulator address
@compliance_app.external(read_only=True)
def get_regulator(*, output: abi.Address) -> Expr:
    """Get the regulator address"""
    return output.set(compliance_app.state.regulator.get())

# Get the KYC provider address
@compliance_app.external(read_only=True)
def get_kyc_provider(*, output: abi.Address) -> Expr:
    """Get the KYC provider address"""
    return output.set(compliance_app.state.kyc_provider.get())

print("Module loaded successfully")