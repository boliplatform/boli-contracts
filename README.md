# Boli - Algorand Smart Contract Suite

Boli is a comprehensive suite of Algorand smart contracts designed for tokenizing real-world assets with a focus on sustainable and impact-driven financial solutions.

## Overview

This repository contains a collection of Algorand smart contracts that enable the creation and management of various tokenized assets:

- **Renewable Energy**: Tokenization of renewable energy infrastructure and production certificates
- **Land Property**: Real estate tokenization with fractional ownership capabilities
- **Heritage Assets**: Management of cultural heritage assets with community stewardship
- **Disaster Recovery**: Climate event-triggered financing instruments for vulnerable regions
- **Carbon Credits**: Implementation of the Verified Carbon Unit (VCU) Framework
- **Blue Economy**: Sustainable marine resources and coastal asset tokenization
- **Compliance**: KYC and regulatory compliance management for all assets

## Repository Structure

```
boli/
├── projects/
│   └── boli/
│       ├── smart_contracts/         # Smart contract source code (PyTeal)
│       │   ├── renewable_energy/
│       │   ├── land_property/
│       │   ├── ...
│       │   └── contract_base.py     # Shared base contract functionality
│       ├── artifacts/               # Compiled contract artifacts
│       │   ├── renewable_energy/
│       │   ├── land_property/
│       │   └── ...
│       ├── build_all_contracts.py   # Script to build all contracts
│       └── deploy_contracts.py      # Script to deploy contracts
└── frontend/                        # React/TypeScript frontend (in development)
```

## Smart Contract Features

These contracts implement a range of functionality crucial for real-world asset tokenization:

- Asset creation and lifecycle management
- Fractional ownership
- Regulatory compliance integration
- Sustainable impact measurement
- Cross-asset interoperability
- Oracle integration for real-world data

## Getting Started

### Prerequisites

- Python 3.12+
- [AlgoKit](https://github.com/algorandfoundation/algokit-cli)
- Poetry (for dependency management)

### Installation

1. Clone the repository
   ```bash
   git clone https://github.com/yourusername/boli.git
   cd boli
   ```

2. Set up the Python environment
   ```bash
   cd projects/boli
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

### Building Contracts

To build all smart contracts:

```bash
python build_all_contracts.py
```

This will generate compiled TEAL files and ABI specifications in the `artifacts` directory.

### Deploying Contracts

To deploy a specific contract:

```bash
python deploy_contracts.py --contract [contract_name]
```

To deploy all contracts:

```bash
python deploy_contracts.py
```

## Frontend Integration

The smart contract artifacts can be integrated with a TypeScript/React frontend using:

1. AlgoKit client generator
   ```bash
   algokit generate client path/to/artifacts/[contract]/application.json --output src/contracts/clients
   ```

2. Import the generated clients in your React components
   ```typescript
   import { RenewableEnergyClient } from '../contracts/clients/RenewableEnergyClient';
   
   // Create client instance
   const client = new RenewableEnergyClient(
     { appId: deployedAppId },
     algodClient,
     { signer: wallet.signer }
   );
   
   // Call contract methods
   const result = await client.createEnergyProject({...});
   ```

## Development

This project uses:

- PyTeal for smart contract development
- Beaker for application framework
- AlgoKit for development tooling
- TypeScript/React for frontend (in development)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the Apache 2.0 License - see the LICENSE file for details.

## Acknowledgments

- Algorand Foundation for blockchain infrastructure
- AlgoKit team for development tools
- PyTeal contributors for smart contract language support

---

*Boli: Empowering sustainable development through blockchain technology*