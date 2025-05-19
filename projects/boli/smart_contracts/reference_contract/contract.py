
# ~/Desktop/boli/projects/boli/smart_contracts/reference_contract/contract.py

from pyteal import *
from beaker import *

# Define the application
reference_app = Application("BoliPlatform")

@reference_app.external
def hello(name: abi.String, *, output: abi.String) -> Expr:
    """Say hello to the specified name"""
    return output.set(Concat(Bytes("Hello, "), name.get()))

# This makes the contract compatible with the rest of the project
if __name__ == "__main__":
    # Compile and export the app
    app_spec = reference_app.build()
    app_spec.export("artifacts/reference_contract")