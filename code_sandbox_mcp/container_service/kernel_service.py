"""
Containerized Jupyter Kernel Service
Runs in a Docker container and manages Jupyter kernels for code execution.
"""

import asyncio
import traceback
import logging
from typing import Dict, List, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from jupyter_client.manager import AsyncKernelManager
import uvicorn

from jupyter_imports import KERNEL_LIBRARIES

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ExecuteRequest(BaseModel):
    kernel_id: str
    code: str
    language: str  # "python" or "bash"

class ExecuteResponse(BaseModel):
    success: bool
    messages: List[Dict[str, Any]]
    error: str = None

class JupyterKernel:
    def __init__(self):
        self.km = AsyncKernelManager()
        self.kc = None
        self._execution_lock = asyncio.Lock()
    
    async def start(self, working_dir: str = "/workspace"):
        logger.info(f"Starting Jupyter kernel in {working_dir}")
        kwargs = {"cwd": working_dir}
        await self.km.start_kernel(**kwargs)
        self.kc = self.km.client()
        self.kc.start_channels()
        await self.kc.wait_for_ready()

    async def import_libraries(self, libraries: List[dict]):
        code = ""
        for library in libraries:
            if "pip" in library:
                code += f"!pip install {library['pip']}\n"
            code += f"import {library['name']} as {library['alias']}\n"
            if "matplotlib" in library['name']:
                code += "%matplotlib inline\n"
        
        # Execute the import code and collect messages but don't return them
        messages = []
        async for message in self.execute_raw(code):
            messages.append(message)
            logger.info(f"Import result: {message}")

    async def execute_raw(self, code: str):
        """Execute code and return raw Jupyter messages"""
        async with self._execution_lock:
            msg_id = self.kc.execute(code)
            logger.info(f"Executing with msg_id: {msg_id}")
            
            try:
                while True:
                    reply = await self.kc.get_iopub_msg()
                    msg_type = reply.get("msg_type")
                    logger.info(f"Received message type: {msg_type}")
                    
                    # Return raw message
                    yield reply
                    
                    # Break on status idle
                    if msg_type == "status" and reply["content"]["execution_state"] == "idle":
                        break
                        
            except asyncio.CancelledError:
                logger.info("Execution cancelled")
                pass

    async def shutdown(self):
        if self.kc:
            self.kc.stop_channels()
        if self.km:
            await self.km.shutdown_kernel()


class KernelManager:
    def __init__(self):
        self.kernels: Dict[str, JupyterKernel] = {}
        self._kernel_locks: Dict[str, asyncio.Lock] = {}
        self._lock = asyncio.Lock()

    async def get_kernel(self, kernel_id: str) -> JupyterKernel:
        async with self._lock:
            if kernel_id not in self._kernel_locks:
                self._kernel_locks[kernel_id] = asyncio.Lock()
            lock = self._kernel_locks[kernel_id]
        
        async with lock:
            if kernel_id not in self.kernels:
                logger.info(f"Creating new kernel for ID: {kernel_id}")
                kernel = JupyterKernel()
                await kernel.start()
                await kernel.import_libraries(KERNEL_LIBRARIES)
                self.kernels[kernel_id] = kernel
            return self.kernels[kernel_id]

    async def shutdown_kernel(self, kernel_id: str):
        if kernel_id in self.kernels:
            await self.kernels[kernel_id].shutdown()
            del self.kernels[kernel_id]
            if kernel_id in self._kernel_locks:
                del self._kernel_locks[kernel_id]

    async def shutdown_all(self):
        for kernel_id in list(self.kernels.keys()):
            await self.shutdown_kernel(kernel_id)


# Global kernel manager
kernel_manager = KernelManager()

# FastAPI app
app = FastAPI(title="Containerized Kernel Service")

@app.post("/execute", response_model=ExecuteResponse)
async def execute_code(request: ExecuteRequest):
    """Execute code in a Jupyter kernel or shell"""
    logger.info(f"Executing {request.language} code for kernel {request.kernel_id}")
    
    try:
        if request.language == "python":
            return await execute_python_code(request)
        elif request.language == "bash":
            return await execute_shell_code(request)
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported language: {request.language}")
    
    except Exception as e:
        logger.error(f"Error executing code: {traceback.format_exc()}")
        return ExecuteResponse(
            success=False,
            messages=[],
            error=str(traceback.format_exc())
        )

async def execute_python_code(request: ExecuteRequest) -> ExecuteResponse:
    """Execute Python code in Jupyter kernel"""
    kernel = await kernel_manager.get_kernel(request.kernel_id)
    messages = []
    
    async for message in kernel.execute_raw(request.code):
        messages.append(message)
    
    return ExecuteResponse(
        success=True,
        messages=messages
    )

async def execute_shell_code(request: ExecuteRequest) -> ExecuteResponse:
    """Execute shell code through Jupyter kernel"""
    kernel = await kernel_manager.get_kernel(request.kernel_id)
    messages = []
    
    # Convert bash code to Jupyter shell magic
    code = request.code.strip()
    
    # For multi-line commands, use %%bash magic
    if '\n' in code:
        jupyter_code = f"%%bash\n{code}"
    else:
        # For single commands, use ! magic
        jupyter_code = f"!{code}"
    
    # Execute through Jupyter kernel like Python code
    async for message in kernel.execute_raw(jupyter_code):
        messages.append(message)
    
    return ExecuteResponse(
        success=True,
        messages=messages
    )

@app.delete("/kernel/{kernel_id}")
async def shutdown_kernel(kernel_id: str):
    """Shutdown a specific kernel"""
    await kernel_manager.shutdown_kernel(kernel_id)
    return {"message": f"Kernel {kernel_id} shutdown"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await kernel_manager.shutdown_all()

if __name__ == "__main__":
    import os
    port = os.getenv("CONTAINER_SERVICE_PORT", "8060")
    uvicorn.run(app, host="0.0.0.0", port=int(port), log_level="info") 