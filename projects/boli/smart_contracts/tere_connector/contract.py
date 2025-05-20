# ~/Desktop/boli/projects/boli/smart_contracts/tere_connector/contract.py

from pyteal import *
from beaker import *
from beaker.lib.storage import BoxMapping

class TEREConnectorState:
    """State for TERE Connector"""
    
    # Admin control
    admin_address = GlobalStateValue(
        stack_type=TealType.bytes,
        descr="Address of the admin"
    )
    
    # Execution registry
    execution_registry = BoxMapping(
        key_type=abi.String,  # Execution ID
        value_type=abi.String,  # Execution type and metadata
        prefix=Bytes("exec")
    )
    
    # Result registry
    result_registry = BoxMapping(
        key_type=abi.String,  # Execution ID
        value_type=abi.String,  # Result data as string
        prefix=Bytes("result")
    )
    
    # Trusted executors - storing "true" or "false" as strings
    trusted_executors = BoxMapping(
        key_type=abi.Address,  # Executor address
        value_type=abi.String,  # Is trusted as string
        prefix=Bytes("executor")
    )

tere_connector = Application(
    "TEREConnector",
    descr="Connector for TERE Trustless External Resource Executor",
    state=TEREConnectorState()
)

@tere_connector.create
def create():
    """Initialize the connector"""
    return Seq([
        tere_connector.state.admin_address.set(Global.creator_address()),
        Approve()
    ])

@tere_connector.external
def add_trusted_executor(
    executor_address: abi.Address,
    *,
    output: abi.Bool
) -> Expr:
    """Add a trusted TERE executor"""
    return Seq([
        Assert(
            Txn.sender() == tere_connector.state.admin_address.get(),
            comment="Only admin can add executors"
        ),
        
        # Store "true" as a string
        tere_connector.state.trusted_executors[executor_address].set(Bytes("true")),
        
        output.set(Int(1))
    ])

@tere_connector.external
def register_execution(
    execution_id: abi.String,
    execution_type: abi.String,
    execution_metadata: abi.String,
    *,
    output: abi.Bool
) -> Expr:
    """Register a TERE execution"""
    return Seq([
        # Store the execution info
        tere_connector.state.execution_registry[execution_id].set(
            Concat(
                execution_type.get(),
                Bytes(":"),
                execution_metadata.get()
            )
        ),
        
        output.set(Int(1))
    ])

@tere_connector.external
def submit_execution_result(
    execution_id: abi.String,
    result_data: abi.String,
    *,
    output: abi.Bool
) -> Expr:
    """Submit result from a TERE execution"""
    return Seq([
        # Ensure execution is registered
        Assert(
            tere_connector.state.execution_registry[execution_id].exists(),
            comment="Execution not registered"
        ),
        
        # Ensure caller is a trusted executor
        Assert(
            And(
                tere_connector.state.trusted_executors[Txn.sender()].exists(),
                tere_connector.state.trusted_executors[Txn.sender()].get() == Bytes("true")
            ),
            comment="Not a trusted executor"
        ),
        
        # Store the result
        tere_connector.state.result_registry[execution_id].set(result_data.get()),
        
        output.set(Int(1))
    ])

@tere_connector.external(read_only=True)
def get_execution_result(
    execution_id: abi.String,
    *,
    output: abi.String
) -> Expr:
    """Get the result of a TERE execution"""
    return Seq([
        Assert(
            tere_connector.state.result_registry[execution_id].exists(),
            comment="No result for this execution"
        ),
        
        output.set(tere_connector.state.result_registry[execution_id].get())
    ])

@tere_connector.external(read_only=True)
def verify_execution(
    execution_id: abi.String,
    expected_type: abi.String,
    *,
    output: abi.Bool
) -> Expr:
    """Verify an execution is of the expected type"""
    
    execution_info = ScratchVar(TealType.bytes)
    
    return Seq([
        Assert(
            tere_connector.state.execution_registry[execution_id].exists(),
            comment="Execution not registered"
        ),
        
        execution_info.store(tere_connector.state.execution_registry[execution_id].get()),
        
        # Check if execution_info starts with the expected type
        output.set(
            Substring(
                execution_info.load(),
                Int(0),
                Len(expected_type.get())
            ) == expected_type.get()
        )
    ])

if __name__ == "__main__":
    # Compile and export the app
    app_spec = tere_connector.build()
    app_spec.export("artifacts/tere_connector")