import re
import orjson
from typing import Optional


def parse_tool_calls(content: str) -> list[dict]:
    calls = []

    calls.extend(_parse_native(content))
    calls.extend(_parse_json_objects(content))
    calls.extend(_parse_xml(content))
    calls.extend(_parse_function_call(content))

    return calls


def _parse_json_objects(content: str) -> list[dict]:
    calls = []
    if not content or not isinstance(content, str):
        return calls
    
    tool_names = {"read_file", "write_file", "list_directory", "execute_shell", "search_files"}

    depth = 0
    start = -1

    for i, char in enumerate(content):
        if char == '{':
            if depth == 0:
                start = i
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0 and start >= 0:
                json_str = content[start:i+1]
                try:
                    data = orjson.loads(json_str)
                    if isinstance(data, dict):
                        name = data.get("tool") or data.get("name", "")
                        if name in tool_names or "tool" in data or "function" in data:
                            args = (data.get("args") or data.get("arguments") or
                                   data.get("parameters") or data.get("input", {}))
                            if isinstance(args, str):
                                try:
                                    args = orjson.loads(args)
                                except Exception:
                                    args = {}
                            calls.append({"name": name, "args": args})
                        elif isinstance(data.get("function"), dict):
                            fn = data["function"]
                            calls.append({
                                "name": fn.get("name", ""),
                                "args": fn.get("arguments", fn.get("parameters", {})),
                            })
                except Exception:
                    pass
                start = -1

    return calls


def _parse_xml(content: str) -> list[dict]:
    calls = []
    tool_pattern = r'<tool\s+name="([^"]+)">(.*?)</tool>'
    args_pattern = r'<args>(.*?)</args>'

    for match in re.finditer(tool_pattern, content, re.DOTALL):
        name = match.group(1)
        body = match.group(2)
        args_match = re.search(args_pattern, body, re.DOTALL)
        args = {}
        if args_match:
            args_str = args_match.group(1).strip()
            try:
                args = orjson.loads(args_str)
            except Exception:
                for pair in re.finditer(r'(\w+)="([^"]*)"', args_str):
                    args[pair.group(1)] = pair.group(2)
        calls.append({"name": name, "args": args})

    return calls


def _parse_native(content: str) -> list[dict]:
    calls = []
    pattern = r'__TOOL_CALL__:(.*?)__'
    for match in re.finditer(pattern, content):
        try:
            data = orjson.loads(match.group(1))
            calls.append({
                "name": data.get("function", {}).get("name", data.get("name", "")),
                "args": data.get("function", {}).get("arguments", data.get("arguments", {})),
            })
        except Exception:
            continue
    return calls


def _parse_function_call(content: str) -> list[dict]:
    calls = []
    tool_names = ["read_file", "write_file", "list_directory", "execute_shell", "search_files"]

    for tool_name in tool_names:
        pattern = rf'{tool_name}\s*\((.*?)\)'
        for match in re.finditer(pattern, content, re.DOTALL):
            args_str = match.group(1)
            args = {}
            pairs = re.findall(r'(\w+)\s*=\s*("([^"]*?)"|\'([^\']*?)\'|(\S+))', args_str)
            for key, val, q1, q2, plain in pairs:
                args[key] = q1 or q2 or plain
            if args:
                calls.append({"name": tool_name, "args": args})

    return calls


def extract_text_response(content: str) -> str:
    if not content or not isinstance(content, str):
        return ""
    
    for pattern in [
        r'\{[^{}]*\}',
        r'<tool\s+name="[^"]+">.*?</tool>',
        r'__TOOL_CALL__:.*?__',
        r'(?:read_file|write_file|list_directory|execute_shell|search_files)\s*\([^)]*\)',
    ]:
        content = re.sub(pattern, '', content, flags=re.DOTALL)
    return content.strip()
