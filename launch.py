#!/usr/bin/env python3
"""
Launch script for the Composed MCP Server
"""
import sys
import asyncio
import signal
import time
import multiprocessing


def run_server(server, port, path, middleware):
    """Function to run a server in a separate process"""
    print(f"🚀 Starting {server.name} server on port {port}...")
    try:
        server.run(
            transport="streamable-http",
            path=path,
            port=port,
            middleware=middleware,
        )
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"❌ Error in {server.name} server: {e}")

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    print(f"\n🛑 Received signal {signum}, shutting down MCP server...")
    
    # First try graceful shutdown with SIGTERM
    for p in multiprocessing.active_children():
        print(f"📡 Sending SIGTERM to {p.name} (PID: {p.pid})")
        try:
            p.terminate()  # Send SIGTERM
        except Exception as e:
            print(f"❌ Error terminating {p.name}: {e}")
    
    # Wait a bit for graceful shutdown
    time.sleep(2)
    
    # Force kill any remaining processes
    for p in multiprocessing.active_children():
        if p.is_alive():
            print(f"🔪 Force killing {p.name} (PID: {p.pid})")
            try:
                p.kill()  # Send SIGKILL
            except Exception as e:
                print(f"❌ Error killing {p.name}: {e}")
    
    # Wait for all processes to finish
    for p in multiprocessing.active_children():
        p.join(timeout=5)
        if p.is_alive():
            print(f"⚠️  Process {p.name} did not terminate")
    
    sys.exit(0)


def main():
    """Start the composed MCP server"""
    # Register signal handlers
    multiprocessing.set_start_method("fork")
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    print("🚀 Starting Composed MCP Server...")
    print(f"🐍 Python path: {sys.path[0]}")
    print("📚 Press Ctrl+C to stop the servers\n")

    try:
        # Import and setup the server
        from code_sandbox_mcp import code_sandbox_mcp, code_sandbox_setup
        from server_middleware import HookTagMiddleware, FastMCPMiddleware
        from starlette.middleware import Middleware
        
        print("⚙️ Setting up MCP server components...")
        asyncio.run(code_sandbox_setup([FastMCPMiddleware()]))
        
        print("✅ Setup complete! Starting servers...")
        
        servers = [
            (code_sandbox_mcp, 8008, "/mcp", [Middleware(HookTagMiddleware)]),
        ]
        
        processes = []
        for server, port, path, mw in servers:
            process = multiprocessing.Process(target=run_server, args=(server, port, path, mw))
            processes.append(process)
            process.start()

        for process in processes:
            process.join()

    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure all dependencies are installed and paths are correct")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()