# Code Sandbox MCP

A FastMCP-based code sandbox server with containerized code execution capabilities.

## Features

- Execute Python and Bash code in isolated containers
- FastMCP integration for tool-based interactions
- Asynchronous kernel management
- Support for data science libraries (pandas, numpy, matplotlib, seaborn)


### Installation

```bash
git clone github.com/cegersdoerfer/code-sandbox-mcp
cd code_sandbox_mcp
pip install -e .

pip install litellm # this is to test with a client only
```

## Usage

### Set up the code_sandbox

1. Create a dir where any files created by the agent should be placed
2. Set `CODE_SANDBOX_PATH` in `code_sandbox_mcp/.env` to the path you created


### As a Server

```bash
python3 launch.py
```

### Server with client
In one terminal window run:
```bash
python3 launch.py
```

In a separate terminal window run:
```bash
python3 -m client.test_client
```
