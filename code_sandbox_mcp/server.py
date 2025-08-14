from starlette.middleware import Middleware
import asyncio
import aiohttp
import json
import os
import subprocess
from dotenv import load_dotenv
import time
from typing import List, Optional
from fastmcp import FastMCP, Context
from fastmcp.server.middleware import Middleware as FastMCPMiddleware

from .code_sandbox_types import KernelOutput, Language

# env file is in the same directory as this file
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path)

# Configuration
CONTAINER_SERVICE_PORT = os.getenv("CONTAINER_SERVICE_PORT", "8060")
CONTAINER_SERVICE_URL = f"http://localhost:{CONTAINER_SERVICE_PORT}"
print(f"Container service URL: {CONTAINER_SERVICE_URL}")

code_sandbox_mcp = FastMCP(name="CodeSandbox")
#mcp_logger = MCPLogger()
#server_logger = mcp_logger.register_mcp_server(code_sandbox_mcp, code_sandbox_mcp.name)

# Global variables for container management
container_process = None

class ContainerKernelClient:
    def __init__(self, base_url: str = CONTAINER_SERVICE_URL):
        self.base_url = base_url
        self.session = None
    
    async def _get_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def execute_code(self, kernel_id: str, code: str, language: str) -> List[KernelOutput]:
        """Execute code in the containerized service"""
        session = await self._get_session()
        
        payload = {
            "kernel_id": kernel_id,
            "code": code,
            "language": language
        }
        
        try:
            async with session.post(f"{self.base_url}/execute", json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Container service error: {error_text}")
                
                result = await response.json()
                
                if not result["success"]:
                    raise Exception(f"Execution failed: {result.get('error', 'Unknown error')}")
                
                # Process the raw messages into ExecutionResult objects
                return self._process_messages(result["messages"])
        
        except aiohttp.ClientError as e:
            #server_logger.error(f"Failed to connect to container service: {traceback.format_exc()}")
            raise Exception(f"Failed to connect to container service: {str(e)}")
        
    
    def _process_messages(self, messages: List[dict]) -> List[KernelOutput]:
        """Convert raw Jupyter messages to ExecutionResult objects"""
        results = []
        
        for message in messages:
            msg_type = message.get("msg_type")
            
            if msg_type == 'stream':
                results.append(KernelOutput(
                    mime_type="text/plain",
                    content=message["content"]["text"],
                    is_error=False
                ))
            
            elif msg_type == 'display_data' or msg_type == 'execute_result':
                data = message['content']['data']
                mime_types = list(data.keys())
                if any("image" in mime_type for mime_type in mime_types):
                    mime_type = [mt for mt in mime_types if "image" in mt][0]
                    results.append(KernelOutput(
                        mime_type=mime_type,
                        content=data[mime_type],
                        is_error=False
                        ))
                elif "text/markdown" in mime_types:
                    results.append(KernelOutput(
                        mime_type="text/markdown",
                        content=data["text/markdown"],
                        is_error=False
                    ))
                elif "text/html" in mime_types:
                    results.append(KernelOutput(
                        mime_type="text/html",
                        content=data["text/html"],
                        is_error=False
                    ))
                elif "application/json" in mime_types:
                    results.append(KernelOutput(
                        mime_type="application/json",
                        content=json.dumps(data["application/json"]),
                        is_error=False
                    ))
                else:
                    results.append(KernelOutput(
                        mime_type="text/plain",
                        content=data["text/plain"],
                        is_error=False
                    ))
            
            elif msg_type == "error":
                results.append(KernelOutput(
                    mime_type="text/plain",
                    content="\n".join(message['content']['traceback']),
                    is_error=True
                ))
            else:
                #log unknown message type
                pass
        return results
    
    async def shutdown_kernel(self, kernel_id: str):
        """Shutdown a specific kernel in the container"""
        session = await self._get_session()
        try:
            async with session.delete(f"{self.base_url}/kernel/{kernel_id}"):
                pass
        except aiohttp.ClientError as e:
            pass
            #server_logger.warning(f"Failed to shutdown kernel {kernel_id}: {e}")
    
    async def close(self):
        """Close the HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def health_check(self, timeout: int = 60) -> bool:
        """Check if the container service is healthy"""
        start_time = time.time()
        session = await self._get_session()
        
        while time.time() - start_time < timeout:
            try:
                async with session.get(f"{self.base_url}/health", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        return True
            except (aiohttp.ClientError, asyncio.TimeoutError):
                pass
            await asyncio.sleep(1)
        
        return False

# Global client instance
container_client = ContainerKernelClient()

async def start_docker_container():
    """Start the Docker container using docker-compose"""
    global container_process
    
    try:
        print("Stopping any existing containers...")
        # First stop any existing containers
        stop_process = subprocess.Popen(
            ["docker-compose", "down"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stop_process.communicate()
        
        print("Starting Docker container...")
        
        # Start the container using docker-compose
        container_process = subprocess.Popen(
            ["docker-compose", "up", "-d"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for the process to complete
        stdout, stderr = container_process.communicate()
        
        if container_process.returncode != 0:
            raise Exception(f"Failed to start container: {stderr.decode()}")
        
        print("Docker container started successfully")
        
        # Wait for the service to be healthy
        print("Waiting for container service to be ready...")
        if await container_client.health_check():
            print("Container service is healthy and ready")
        else:
            raise Exception("Container service failed to become healthy")
            
    except Exception as e:
        print(f"Error starting Docker container: {e}")
        raise

async def stop_docker_container():
    """Stop the Docker container"""
    try:
        print("Stopping Docker container...")
        process = subprocess.Popen(
            ["docker-compose", "down"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            print("Docker container stopped successfully")
        else:
            print(f"Warning: Error stopping container: {stderr.decode()}")
    except Exception as e:
        print(f"Error stopping Docker container: {e}")

@code_sandbox_mcp.tool(
    description="Execute code in a containerized Jupyter kernel environment",
    tags={}
)
async def execute_code(language: Language, code: str, ctx: Context) -> List[KernelOutput]:
    #server_logger.info(f"Executing code: \n {code} \n with language: {language} \n and context: {ctx}")

    kernel_id = ctx.context_id
    print(f"Executing code with kernel_id: {kernel_id}")
    
    results = await container_client.execute_code(
        kernel_id=kernel_id,
        code=code,
        language=language.value
    )
    
    #server_logger.info(f"Execution results: {results}")
    return results

async def setup(middleware: Optional[List[FastMCPMiddleware]] = None):
    """Setup the MCP server and Docker container"""
    # Start the Docker container first
    await start_docker_container()
    
    # Close the session so it gets recreated in the new event loop
    await container_client.close()
    
    # Add middleware
    if middleware:
        for m in middleware:
            code_sandbox_mcp.add_middleware(m)

# Cleanup on shutdown
async def cleanup():
    """Cleanup resources"""
    await container_client.close()
    await stop_docker_container()
