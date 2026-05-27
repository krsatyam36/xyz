from setuptools import setup, find_packages

setup(
    name="xyz",
    version="0.2.0",
    description="XYZ - Open Source AI Coding Agent",
    author="Kumar Satyam",
    author_email="kumarsatyam3135@gmail.com",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "typer>=0.9.0",
        "rich>=13.7.0",
        "textual>=0.47.0",
        "prompt_toolkit>=3.0.0",
        "fastapi>=0.104.0",
        "uvicorn>=0.24.0",
        "httpx>=0.25.0",
        "pydantic>=2.5.0",
        "orjson>=3.9.0",
        "keyring>=24.3.0",
    ],
    entry_points={
        "console_scripts": [
            "xyz=xyz.main:cli",
        ],
    },
)
