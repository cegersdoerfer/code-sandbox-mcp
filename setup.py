from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="code-sandbox-mcp",
    version="0.1.0",
    author="Chris Egersdoerfer",
    author_email="cegersdo@udel.edu",
    description="A FastMCP-based code sandbox server with containerized execution",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/code_sandbox_mcp",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "fastmcp>=0.1.0",
        "starlette>=0.27.0",
        "aiohttp>=3.8.0",
        "pydantic>=2.5.0",
        "fastapi>=0.104.1",
        "uvicorn[standard]>=0.24.0",
        "jupyter-client>=8.6.0",
        "ipykernel>=6.26.0",
        "python-dotenv>=1.1.1",
    ],
    include_package_data=True,
    package_data={
        "code_sandbox_mcp": [
            "container_service/Dockerfile",
            "container_service/requirements.txt",
        ],
    },
)
