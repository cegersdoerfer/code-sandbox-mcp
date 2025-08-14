from fastmcp import Client
from fastmcp.client.client import CallToolResult
from litellm import Router
from litellm.experimental_mcp_client.tools import (
    transform_mcp_tool_to_openai_tool,
    transform_openai_tool_call_request_to_mcp_tool_call_request,
)
import json
import asyncio
import uuid

ROUTER_CONFIG = [{
            "model_name": "gpt-5-nano",
            "litellm_params": {
                "model": "gpt-5-nano",
                "tpm": 150000000,
                "rpm": 30000
            }
        }]

MCP_SERVER_CONFIG = {
    "mcpServers": {
        "code_sandbox_server": {
            "url": "http://127.0.0.1:8008/mcp",
            "sse_read_timeout": 6000
        }
    }
}

SYSTEM_PROMPT = """
You are a helpful assistant that can use the following tools to help the user:

<tools>
{mcp_tools}
</tools>
"""

def code_execution_parser(tool_result: CallToolResult):
    # code execution results are a list of kernel outputs
    kernel_outputs = tool_result.structured_content["result"]
    output_str = ""
    for kernel_output in kernel_outputs:
        if "image" in kernel_output["mime_type"]:
            output_str += "Image generated but redacted from response\n"
        else:
            output_str += f"{kernel_output['mime_type']}:\n{kernel_output['content']}\n"
    return output_str

TOOL_RESULT_PARSERS = {
    "code_sandbox_server": {
        "execute_code": code_execution_parser
    }
}

class SimpleAgent:

    def __init__(self, router: Router):
        self.id = str(uuid.uuid4())
        self.client = Client(self.add_context_id_to_server_config(MCP_SERVER_CONFIG))
        self.router = router
        self.llm_model = "gpt-5-nano"
        self.messages = []
        self.tool_result_parsers = self.get_tool_parsers(TOOL_RESULT_PARSERS)
    

    def get_tool_parsers(self, parsers_dict: dict):
        tool_parsers = {}
        for server_name, tool_parsers in parsers_dict.items():
            for tool_name, parser in tool_parsers.items():
                if len(parsers_dict) > 1:
                    tool_parsers[f"{server_name}_{tool_name}"] = parser
                else:
                    tool_parsers[tool_name] = parser
        print(f"Tool parsers: {tool_parsers}")
        return tool_parsers
    

    def add_context_id_to_server_config(self, mcp_config: dict):
        mcp_servers = mcp_config["mcpServers"]
        for server_name, server_config in mcp_servers.items():
            if "url" in server_config:
                mcp_server_url = server_config["url"]
                mcp_server_url = f"{mcp_server_url}?context_id={self.id}"
                mcp_config["mcpServers"][server_name]["url"] = mcp_server_url
        return mcp_config


    async def setup(self):
        self.mcp_tools = await self.client.list_tools()
        print("MCP Tools:")
        print(json.dumps([tool.model_dump() for tool in self.mcp_tools], indent=4))

        self.openai_tools = [transform_mcp_tool_to_openai_tool(tool) for tool in self.mcp_tools]
        print("OpenAI Tools:")
        print(json.dumps(self.openai_tools, indent=4))

        system_prompt = SYSTEM_PROMPT.format(mcp_tools=json.dumps(self.openai_tools, indent=4))
        self.messages.append({"role": "system", "content": system_prompt})


    def get_llm_response(self):
        kwargs = {
            "tools": self.openai_tools,
            "tool_choice": "auto"
        }
        model_response = self.router.completion(
            self.llm_model,
            self.messages,
            **kwargs 
        )
        return model_response.choices[0].message


    def parse_tool_result(self, tool_name: str, tool_result: CallToolResult):
        if tool_name in self.tool_result_parsers:
            print(f"Parsing tool result for {tool_name}")
            parser = self.tool_result_parsers[tool_name]
            return parser(tool_result)
        else:
            print(f"No parser found for {tool_name}")
            return tool_result.content


    async def run(self):
        async with self.client:
            await self.setup()
            exit_flag = False
            while not exit_flag:
                user_input = input("Enter a message or 'exit' to quit: ")
                if user_input.lower() == "exit":
                    exit_flag = True
                    continue
                self.messages.append({"role": "user", "content": user_input})
                response = self.get_llm_response()
                print(response)
                self.messages.append(response)
                if response.tool_calls:
                    for tool_call in response.tool_calls:
                        mcp_tool_call = transform_openai_tool_call_request_to_mcp_tool_call_request(
                            openai_tool=tool_call.model_dump()
                        )
                        tool_call_id = tool_call.id
                        tool_name = mcp_tool_call.name
                        tool_args = mcp_tool_call.arguments
                        try:
                            tool_result = await self.client.call_tool(
                                name=tool_name, 
                                arguments=tool_args
                            )
                        except Exception as e:
                            print(f"Tool call failed: {str(e)}")
                            break
                        tool_result = self.parse_tool_result(tool_name, tool_result)
                        print(f"parsed tool result: {tool_result}")
                        self.messages.append({
                            "role": "tool",
                            "content": tool_result,
                            "tool_call_id": tool_call_id
                        })
    


if __name__ == "__main__":
    router = Router(ROUTER_CONFIG)
    agent = SimpleAgent(router)
    asyncio.run(agent.run())

