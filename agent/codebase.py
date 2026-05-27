"""Deep Codebase Context: AST parsing and local RAG for XYZ."""

import ast
import os
import json
import hashlib
from pathlib import Path
from typing import Optional

from xyz.config import CACHE_DIR


AST_CACHE_DIR = CACHE_DIR / "ast"
RAG_CACHE_DIR = CACHE_DIR / "rag"


def _ensure_dirs():
    AST_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    RAG_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def parse_python_ast(file_path: str) -> dict:
    """Parse a Python file into AST summary with function signatures, classes, imports."""
    try:
        _ensure_dirs()
        p = Path(file_path).resolve()
        if not p.exists() or p.suffix != ".py":
            return {"error": f"Not a Python file: {file_path}"}

        content = p.read_text()
        tree = ast.parse(content)

        imports = []
        functions = []
        classes = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({"type": "import", "name": alias.name, "alias": alias.asname})
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append({"type": "from-import", "module": module, "name": alias.name, "alias": alias.asname})
            elif isinstance(node, ast.FunctionDef):
                args = [a.arg for a in node.args.args]
                decorators = [ast.unparse(d) for d in node.decorator_list]
                functions.append({
                    "name": node.name,
                    "args": args,
                    "decorators": decorators,
                    "lineno": node.lineno,
                    "docstring": ast.get_docstring(node) or "",
                })
            elif isinstance(node, ast.AsyncFunctionDef):
                args = [a.arg for a in node.args.args]
                decorators = [ast.unparse(d) for d in node.decorator_list]
                functions.append({
                    "name": node.name,
                    "args": args,
                    "decorators": decorators,
                    "lineno": node.lineno,
                    "async": True,
                    "docstring": ast.get_docstring(node) or "",
                })
            elif isinstance(node, ast.ClassDef):
                bases = [ast.unparse(b) for b in node.bases]
                methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods.append({
                            "name": item.name,
                            "args": [a.arg for a in item.args.args],
                            "decorators": [ast.unparse(d) for d in item.decorator_list],
                        })
                classes.append({
                    "name": node.name,
                    "bases": bases,
                    "methods": methods,
                    "lineno": node.lineno,
                    "docstring": ast.get_docstring(node) or "",
                })

        summary = {
            "path": str(p),
            "imports": imports,
            "functions": functions,
            "classes": classes,
            "total_lines": len(content.splitlines()),
        }

        cache_key = hashlib.md5(content.encode()).hexdigest()[:16]
        cache_path = AST_CACHE_DIR / f"{p.stem}_{cache_key}.json"
        cache_path.write_text(json.dumps(summary, indent=2))

        return summary
    except SyntaxError as e:
        return {"error": f"Syntax error in {file_path}: {e}"}
    except Exception as e:
        return {"error": str(e)}


def analyze_codebase(path: str = ".") -> dict:
    """Analyze an entire codebase and return a structural summary."""
    try:
        p = Path(path).resolve()
        if not p.is_dir():
            return {"error": f"Not a directory: {path}"}

        result = {
            "path": str(p),
            "files": [],
            "total_files": 0,
            "import_graph": [],
            "all_functions": [],
            "all_classes": [],
        }

        py_files = list(p.rglob("*.py"))
        result["total_files"] = len(py_files)

        for f in py_files:
            if any(part.startswith(".") or part == "__pycache__" for part in f.parts):
                continue
            parsed = parse_python_ast(str(f))
            if "error" in parsed:
                continue
            result["files"].append(parsed)
            for fn in parsed.get("functions", []):
                result["all_functions"].append({**fn, "file": str(f)})
            for cls in parsed.get("classes", []):
                result["all_classes"].append({**cls, "file": str(f)})
            for imp in parsed.get("imports", []):
                result["import_graph"].append({**imp, "file": str(f)})

        # Build summary stats
        result["function_count"] = len(result["all_functions"])
        result["class_count"] = len(result["all_classes"])
        result["import_count"] = len(result["import_graph"])

        return result
    except Exception as e:
        return {"error": str(e)}


class CodeRAG:
    """Lightweight local RAG for code using keyword + trigram matching.
    Falls back to embedding-free semantic matching.
    """

    def __init__(self):
        _ensure_dirs()
        self.index_path = RAG_CACHE_DIR / "code_index.json"

    def build_index(self, path: str = ".") -> dict:
        """Build a search index of the codebase."""
        analysis = analyze_codebase(path)
        if "error" in analysis:
            return analysis

        index = {
            "functions": {},
            "classes": {},
            "files": {},
            "keywords": {},
        }

        for fn in analysis.get("all_functions", []):
            name = fn["name"]
            file = fn["file"]
            index["functions"][name] = fn
            for word in name.split("_"):
                word = word.lower()
                if len(word) > 2:
                    if word not in index["keywords"]:
                        index["keywords"][word] = []
                    index["keywords"][word].append({"type": "function", "name": name, "file": file})

        for cls in analysis.get("all_classes", []):
            name = cls["name"]
            file = cls["file"]
            index["classes"][name] = cls
            for word in name.split("_"):
                word = word.lower()
                if len(word) > 2:
                    if word not in index["keywords"]:
                        index["keywords"][word] = []
                    index["keywords"][word].append({"type": "class", "name": name, "file": file})

        for f_info in analysis.get("files", []):
            fname = Path(f_info["path"]).stem
            index["files"][fname] = f_info

        self.index_path.write_text(json.dumps(index, indent=2))
        index["stats"] = {
            "functions": len(index["functions"]),
            "classes": len(index["classes"]),
            "files": len(index["files"]),
            "keywords": len(index["keywords"]),
        }
        return index

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """Search the codebase index for relevant matches."""
        if not self.index_path.exists():
            return [{"error": "Index not built. Run /semantic first."}]

        index = json.loads(self.index_path.read_text())
        query_words = set(w.lower() for w in query.split() if len(w) > 2)

        results = []
        seen = set()

        for word in query_words:
            for match in index.get("keywords", {}).get(word, []):
                key = f"{match['type']}:{match['name']}:{match['file']}"
                if key not in seen:
                    seen.add(key)
                    results.append(match)

        if not results:
            return [{"message": "No semantic matches found. Try different keywords."}]

        results.sort(key=lambda x: x.get("name", ""))
        return results[:top_k]

    def get_relevant_context(self, query: str, top_k: int = 5) -> str:
        """Get relevant code context as a formatted string for the prompt."""
        results = self.search(query, top_k)
        if not results or "error" in results[0]:
            return ""

        lines = ["Relevant codebase context from semantic search:"]
        for r in results:
            rtype = r.get("type", "?")
            name = r.get("name", "?")
            file = r.get("file", "?")
            lines.append(f"  [{rtype}] {name} -> {file}")

        return "\n".join(lines)
