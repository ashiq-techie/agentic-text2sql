# A2A SDK Installation Instructions

This document provides step-by-step instructions for installing the official A2A SDK from Google's repository.

## Prerequisites

- Python 3.8 or higher
- Git
- Virtual environment tool (venv, conda, or uv)

## Installation Steps

### 1. Clone the A2A Repository

```bash
# Clone the official A2A repository from Google
git clone [email protected]:google/A2A.git

# Alternative if you don't have SSH keys set up:
# git clone https://github.com/google/A2A.git
```

### 2. Navigate to the Python SDK Directory

```bash
cd A2A/a2a-python-sdk
```

### 3. Create and Activate Virtual Environment

```bash
# Using Python venv
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Or using uv (recommended for faster installation)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 4. Install the A2A SDK

```bash
# Install in development mode
pip install -e .

# Or using uv for faster installation
uv pip install -e .
```

### 5. Verify Installation

```bash
# Check if the SDK is installed
python -c "import a2a; print('A2A SDK installed successfully')"
```

## Project Structure

After installation, you'll have access to the following components:

```
A2A/a2a-python-sdk/
├── a2a/                    # Main SDK package
├── examples/               # Example implementations
│   └── helloworld/        # Basic hello world example
│       ├── __main__.py    # Main entry point
│       ├── agent_executor.py  # Agent executor
│       └── test_client.py # Test client
├── setup.py               # Package setup
└── README.md             # SDK documentation
```

## Testing the Installation

### 1. Run the Hello World Example

```bash
# Navigate to the example directory
cd examples/helloworld

# Run the A2A server
python __main__.py
```

This will start the A2A server on `http://localhost:9999`

### 2. Test with the Client

In a new terminal window:

```bash
# Activate the same virtual environment
source .venv/bin/activate

# Navigate to the example directory
cd A2A/a2a-python-sdk/examples/helloworld

# Run the test client
python test_client.py
```

You should see output similar to:
```
{'id': 'd220c3d7335e40478e1745d28d54155f', 'jsonrpc': '2.0', 'result': {'messageId': 'ac094ba7-f56c-41e3-85cf-a813406c65d4', 'parts': [{'text': 'Hello World', 'type': 'text'}], 'role': 'agent'}}
```

## Integration with Text-to-SQL Agent

Once the A2A SDK is installed, you can integrate it with your text-to-SQL agent by:

1. Creating an `agent_executor.py` file following the SDK patterns
2. Implementing the agent service configuration in `__main__.py`
3. Creating test clients for validation

## Troubleshooting

### Common Issues

1. **Import Error**: Ensure you're in the correct virtual environment
2. **Permission Error**: Make sure you have write permissions to the installation directory
3. **Network Issues**: If cloning fails, try using HTTPS instead of SSH

### Getting Help

- Check the [A2A Protocol Documentation](https://a2aprotocol.ai/docs/)
- Review the [official examples](https://github.com/a2aproject/a2a-samples)
- Visit the [A2A Protocol website](https://a2aprotocol.ai/)

## Next Steps

After successful installation, you can:

1. Study the hello world example to understand the SDK structure
2. Implement your own agent executor
3. Create custom agent services
4. Build multi-agent workflows

The SDK provides a standardized way to create A2A-compliant agents that can communicate with other agents in the ecosystem. 