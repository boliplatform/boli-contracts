# ~/Desktop/boli/projects/boli/smart_contracts/compliance/build_contract.py

import os
import json
import contract  # Import the local contract module

# Build the app
app_spec = contract.compliance_app.build()

# Create output directory if it doesn't exist
artifacts_dir = "artifacts"
os.makedirs(artifacts_dir, exist_ok=True)

# Export the application - this will create multiple files
# including application.json, approval.teal, and clear.teal
app_spec.export(artifacts_dir)

print(f"Contract built and exported to {artifacts_dir}")

# Also verify the content was properly written
app_json_path = f"{artifacts_dir}/application.json"
if os.path.exists(app_json_path):
    with open(app_json_path, "r") as f:
        content = f.read()
        print(f"application.json size: {len(content)} bytes")
else:
    print("Warning: application.json was not created")

approval_path = f"{artifacts_dir}/approval.teal"
if os.path.exists(approval_path):
    with open(approval_path, "r") as f:
        content = f.read()
        print(f"approval.teal size: {len(content)} bytes")
else:
    print("Warning: approval.teal was not created")
