import os
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, List, Any
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ProjectContext:
    """Comprehensive project analysis context."""
    name: str
    root: str
    language: str
    framework: str
    test_framework: str
    build_tool: str
    package_manager: str
    main_dirs: List[str]
    source_files: List[str]
    test_files: List[str]
    config_files: List[str]
    dependencies: List[str]
    scripts: Dict[str, str]
    structure: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        return asdict(self)


class ProjectAnalyzer:
    """Analyzes project structure and context."""
    
    def __init__(self, root_path: Optional[str] = None):
        self.root = Path(root_path or os.getcwd()).resolve()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def analyze(self) -> ProjectContext:
        """Perform comprehensive project analysis."""
        self.logger.info(f"Analyzing project: {self.root}")
        
        return ProjectContext(
            name=self.root.name,
            root=str(self.root),
            language=self._detect_language(),
            framework=self._detect_framework(),
            test_framework=self._detect_test_framework(),
            build_tool=self._detect_build_tool(),
            package_manager=self._detect_package_manager(),
            main_dirs=self._find_main_directories(),
            source_files=self._find_source_files(),
            test_files=self._find_test_files(),
            config_files=self._find_config_files(),
            dependencies=self._extract_dependencies(),
            scripts=self._extract_scripts(),
            structure=self._generate_structure(),
        )
    
    def _detect_language(self) -> str:
        """Detect primary programming language."""
        indicators = {
            'python': ['setup.py', 'pyproject.toml', 'requirements.txt', '*.py'],
            'javascript': ['package.json', 'package-lock.json', '*.js', '*.jsx'],
            'typescript': ['tsconfig.json', '*.ts', '*.tsx'],
            'go': ['go.mod', '*.go'],
            'rust': ['Cargo.toml', '*.rs'],
            'java': ['pom.xml', 'build.gradle', '*.java'],
        }
        
        file_count = {}
        for lang, patterns in indicators.items():
            count = 0
            for pattern in patterns:
                if pattern.startswith('*'):
                    count += len(list(self.root.glob(f'**/{pattern}')))
                else:
                    count += (self.root / pattern).exists()
            file_count[lang] = count
        
        return max(file_count, key=file_count.get) if file_count else 'unknown'
    
    def _detect_framework(self) -> str:
        """Detect main framework."""
        framework_files = {
            'Django': 'django/',
            'FastAPI': 'fastapi',
            'Flask': 'flask',
            'React': 'react',
            'Vue': 'vue',
            'Angular': '@angular',
            'Next.js': 'next',
            'Express': 'express',
            'Spring': 'springframework',
        }
        
        # Check package.json or requirements.txt
        if (self.root / 'requirements.txt').exists():
            content = (self.root / 'requirements.txt').read_text()
            for framework, pkg in framework_files.items():
                if pkg in content.lower():
                    return framework
        
        if (self.root / 'package.json').exists():
            content = (self.root / 'package.json').read_text()
            for framework, pkg in framework_files.items():
                if pkg in content.lower():
                    return framework
        
        return 'unknown'
    
    def _detect_test_framework(self) -> str:
        """Detect testing framework."""
        test_indicators = {
            'pytest': ['pytest.ini', 'tests/', 'test_*.py'],
            'jest': ['jest.config', '__tests__', '*.test.js'],
            'mocha': ['mocha.opts', '.mocharc', 'test/*.js'],
            'unittest': ['tests/', 'test_*.py'],
        }
        
        for framework, patterns in test_indicators.items():
            for pattern in patterns:
                if (self.root / pattern).exists() or list(self.root.glob(f'**/{pattern}')):
                    return framework
        
        return 'unknown'
    
    def _detect_build_tool(self) -> str:
        """Detect build tool."""
        build_files = {
            'make': 'Makefile',
            'gradle': 'build.gradle',
            'maven': 'pom.xml',
            'cargo': 'Cargo.toml',
            'webpack': 'webpack.config.js',
            'vite': 'vite.config.js',
        }
        
        for tool, file in build_files.items():
            if (self.root / file).exists():
                return tool
        
        return 'unknown'
    
    def _detect_package_manager(self) -> str:
        """Detect package manager."""
        if (self.root / 'poetry.lock').exists():
            return 'poetry'
        if (self.root / 'package-lock.json').exists():
            return 'npm'
        if (self.root / 'yarn.lock').exists():
            return 'yarn'
        if (self.root / 'pnpm-lock.yaml').exists():
            return 'pnpm'
        if (self.root / 'Pipfile.lock').exists():
            return 'pipenv'
        if (self.root / 'requirements.txt').exists():
            return 'pip'
        return 'unknown'
    
    def _find_main_directories(self) -> List[str]:
        """Find main project directories."""
        common_dirs = ['src', 'lib', 'app', 'packages', 'modules', 'components']
        found = [d for d in common_dirs if (self.root / d).is_dir()]
        return found or ['.']
    
    def _find_source_files(self) -> List[str]:
        """Find source files."""
        patterns = ['**/*.py', '**/*.js', '**/*.ts', '**/*.tsx', '**/*.go', '**/*.rs', '**/*.java']
        files = []
        for pattern in patterns:
            files.extend([str(f.relative_to(self.root)) for f in self.root.glob(pattern)])
        return sorted(list(set(files)))[:100]  # Limit to 100
    
    def _find_test_files(self) -> List[str]:
        """Find test files."""
        patterns = ['**/test_*.py', '**/*.test.js', '**/*.spec.js', '**/tests/*']
        files = []
        for pattern in patterns:
            files.extend([str(f.relative_to(self.root)) for f in self.root.glob(pattern)])
        return sorted(list(set(files)))[:50]
    
    def _find_config_files(self) -> List[str]:
        """Find configuration files."""
        config_patterns = ['*.json', '*.yaml', '*.yml', '*.toml', '*.ini', '*.conf', '.env*']
        files = []
        for pattern in config_patterns:
            files.extend([str(f.relative_to(self.root)) for f in self.root.glob(pattern)])
        return sorted(list(set(files)))
    
    def _extract_dependencies(self) -> List[str]:
        """Extract project dependencies."""
        deps = []
        
        if (self.root / 'requirements.txt').exists():
            content = (self.root / 'requirements.txt').read_text()
            deps.extend([line.split('==')[0].strip() for line in content.split('\n') if line.strip() and not line.startswith('#')])
        
        if (self.root / 'package.json').exists():
            try:
                data = json.loads((self.root / 'package.json').read_text())
                deps.extend(list(data.get('dependencies', {}).keys()))
                deps.extend(list(data.get('devDependencies', {}).keys()))
            except Exception:
                pass
        
        return sorted(list(set(deps)))[:50]
    
    def _extract_scripts(self) -> Dict[str, str]:
        """Extract build/run scripts."""
        scripts = {}
        
        if (self.root / 'package.json').exists():
            try:
                data = json.loads((self.root / 'package.json').read_text())
                scripts.update(data.get('scripts', {}))
            except Exception:
                pass
        
        if (self.root / 'Makefile').exists():
            try:
                content = (self.root / 'Makefile').read_text()
                for line in content.split('\n'):
                    if ':' in line and not line.startswith('\t'):
                        target = line.split(':')[0].strip()
                        if target:
                            scripts[f'make {target}'] = target
            except Exception:
                pass
        
        return scripts
    
    def _generate_structure(self) -> Dict[str, Any]:
        """Generate directory structure."""
        def _build_tree(path: Path, max_depth: int = 3, current_depth: int = 0) -> Dict:
            if current_depth >= max_depth:
                return {}
            
            tree = {}
            try:
                for item in sorted(path.iterdir()):
                    if item.name.startswith('.'):
                        continue
                    if item.is_dir():
                        tree[item.name] = _build_tree(item, max_depth, current_depth + 1)
                    else:
                        tree[item.name] = 'file'
            except PermissionError:
                pass
            
            return tree
        
        return _build_tree(self.root)


class ProjectContextGenerator:
    """Generates useful context strings for prompts."""
    
    def __init__(self, context: ProjectContext):
        self.context = context
    
    def generate_system_prompt(self) -> str:
        """Generate enhanced system prompt with project context."""
        return f"""You are XYZ, an expert agentic AI coding assistant integrated with a {self.context.language} project.

PROJECT CONTEXT:
- Name: {self.context.name}
- Language: {self.context.language}
- Framework: {self.context.framework}
- Build Tool: {self.context.build_tool}
- Package Manager: {self.context.package_manager}
- Test Framework: {self.context.test_framework}

PROJECT STRUCTURE:
{self._format_structure()}

AVAILABLE SCRIPTS:
{self._format_scripts()}

KEY DEPENDENCIES:
{self._format_dependencies()}

CABILITIES:
1. Analyze and modify code in {self.context.language}
2. Run tests and debug failures
3. Execute build commands
4. Search and understand codebase
5. Create new files and features
6. Refactor existing code
7. Handle dependencies and packages

GUIDELINES:
1. Always understand the project structure before making changes
2. Run tests after modifications
3. Follow existing code patterns and conventions
4. Ask for clarification on ambiguous requirements
5. Suggest improvements and refactoring opportunities
6. Provide detailed explanations for changes

WORKING DIRECTORY: {self.context.root}
"""
    
    def _format_structure(self) -> str:
        """Format project structure."""
        lines = []
        for dir_name in self.context.main_dirs:
            lines.append(f"  - {dir_name}/")
        lines.append(f"\nTotal source files: {len(self.context.source_files)}")
        lines.append(f"Test files: {len(self.context.test_files)}")
        return "\n".join(lines)
    
    def _format_scripts(self) -> str:
        """Format available scripts."""
        if not self.context.scripts:
            return "  None found"
        return "\n".join([f"  - {k}: {v}" for k, v in list(self.context.scripts.items())[:10]])
    
    def _format_dependencies(self) -> str:
        """Format key dependencies."""
        if not self.context.dependencies:
            return "  None found"
        return "\n".join([f"  - {dep}" for dep in self.context.dependencies[:15]])
    
    def generate_file_context(self, file_path: str) -> str:
        """Generate context for a specific file."""
        full_path = self.context.root / file_path
        if not full_path.exists():
            return f"File not found: {file_path}"
        
        try:
            content = full_path.read_text()
            lines = content.split('\n')
            
            context = f"""FILE: {file_path}
SIZE: {len(content)} bytes ({len(lines)} lines)
LANGUAGE: {self._detect_file_language(file_path)}

STRUCTURE:
"""
            # Extract function/class names
            if file_path.endswith('.py'):
                for i, line in enumerate(lines[:100], 1):
                    if line.startswith(('def ', 'class ')):
                        context += f"  Line {i}: {line.strip()}\n"
            
            context += f"\nCONTENT:\n{content[:2000]}"
            if len(content) > 2000:
                context += "\n... (truncated)"
            
            return context
        except Exception as e:
            return f"Error reading file: {e}"
    
    def _detect_file_language(self, file_path: str) -> str:
        """Detect file programming language."""
        ext_map = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.ts': 'TypeScript',
            '.tsx': 'TypeScript React',
            '.jsx': 'JavaScript React',
            '.go': 'Go',
            '.rs': 'Rust',
            '.java': 'Java',
            '.cpp': 'C++',
            '.c': 'C',
            '.rb': 'Ruby',
            '.php': 'PHP',
        }
        ext = Path(file_path).suffix
        return ext_map.get(ext, 'Unknown')


class CodeAnalyzer:
    """Analyzes code quality and structure."""
    
    def __init__(self, root_path: Optional[str] = None):
        self.root = Path(root_path or os.getcwd()).resolve()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """Analyze a single file."""
        full_path = self.root / file_path
        if not full_path.exists():
            return {"error": f"File not found: {file_path}"}
        
        try:
            content = full_path.read_text()
            lines = content.split('\n')
            
            return {
                "file": file_path,
                "size": len(content),
                "lines": len(lines),
                "language": self._detect_language(file_path),
                "complexity": self._calculate_complexity(content, file_path),
                "issues": self._find_issues(content, file_path),
                "functions": self._extract_functions(content, file_path),
                "imports": self._extract_imports(content, file_path),
            }
        except Exception as e:
            self.logger.error(f"Error analyzing file: {e}")
            return {"error": str(e)}
    
    def _detect_language(self, file_path: str) -> str:
        """Detect file language."""
        ext = Path(file_path).suffix.lower()
        lang_map = {
            '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript',
            '.go': 'Go', '.rs': 'Rust', '.java': 'Java', '.rb': 'Ruby',
        }
        return lang_map.get(ext, 'Unknown')
    
    def _calculate_complexity(self, content: str, file_path: str) -> int:
        """Calculate code complexity (cyclomatic)."""
        complexity = 1
        keywords = ['if', 'elif', 'else', 'for', 'while', 'except', 'case']
        for keyword in keywords:
            complexity += content.count(f' {keyword}(')
        return complexity
    
    def _find_issues(self, content: str, file_path: str) -> List[str]:
        """Find potential code issues."""
        issues = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines, 1):
            # Check for common issues
            if 'TODO' in line or 'FIXME' in line:
                issues.append(f"Line {i}: {line.strip()[:50]}")
            if 'pass' in line and line.strip() == 'pass':
                issues.append(f"Line {i}: Empty function/class")
            if len(line) > 100:
                issues.append(f"Line {i}: Line too long ({len(line)} chars)")
        
        return issues[:10]
    
    def _extract_functions(self, content: str, file_path: str) -> List[str]:
        """Extract function/method names."""
        functions = []
        lines = content.split('\n')
        
        if file_path.endswith('.py'):
            for line in lines:
                if line.startswith('def '):
                    func_name = line.split('(')[0].replace('def ', '').strip()
                    functions.append(func_name)
        
        return functions[:20]
    
    def _extract_imports(self, content: str, file_path: str) -> List[str]:
        """Extract imports."""
        imports = []
        lines = content.split('\n')
        
        if file_path.endswith('.py'):
            for line in lines:
                if line.startswith(('import ', 'from ')):
                    imports.append(line.strip())
        
        return imports[:15]


class ExecutionEnv:
    """Manages command execution with context."""
    
    def __init__(self, root_path: Optional[str] = None):
        self.root = Path(root_path or os.getcwd()).resolve()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def run_tests(self, test_framework: str = 'pytest', pattern: Optional[str] = None) -> Dict[str, Any]:
        """Run tests and capture results."""
        cmd = self._build_test_command(test_framework, pattern)
        return self._execute(cmd, "Run tests")
    
    def run_build(self, build_tool: str = 'make') -> Dict[str, Any]:
        """Run build command."""
        cmd = self._build_build_command(build_tool)
        return self._execute(cmd, "Build")
    
    def run_lint(self, linter: str = 'pylint') -> Dict[str, Any]:
        """Run linter."""
        cmd = self._build_lint_command(linter)
        return self._execute(cmd, "Lint")
    
    def run_script(self, script_name: str) -> Dict[str, Any]:
        """Run npm/package script."""
        cmd = f"npm run {script_name}"
        return self._execute(cmd, f"Run script: {script_name}")
    
    def _build_test_command(self, framework: str, pattern: Optional[str] = None) -> str:
        """Build test command."""
        commands = {
            'pytest': f"pytest {pattern or 'tests/'} -v",
            'jest': f"npm test -- {pattern or ''}",
            'unittest': f"python -m unittest {pattern or 'discover'}",
        }
        return commands.get(framework, f"{framework} test")
    
    def _build_build_command(self, tool: str) -> str:
        """Build build command."""
        commands = {
            'make': 'make',
            'maven': 'mvn build',
            'gradle': 'gradle build',
            'cargo': 'cargo build',
        }
        return commands.get(tool, f"{tool} build")
    
    def _build_lint_command(self, linter: str) -> str:
        """Build lint command."""
        commands = {
            'pylint': 'pylint **/*.py',
            'flake8': 'flake8 .',
            'eslint': 'eslint .',
            'ruff': 'ruff check .',
        }
        return commands.get(linter, f"{linter} .")
    
    def _execute(self, cmd: str, description: str) -> Dict[str, Any]:
        """Execute command and capture output."""
        self.logger.info(f"{description}: {cmd}")
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300,
                cwd=self.root,
            )
            return {
                "status": "success" if result.returncode == 0 else "failed",
                "code": result.returncode,
                "stdout": result.stdout[:5000],
                "stderr": result.stderr[:5000],
                "command": cmd,
            }
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "error": f"Command timed out: {cmd}"}
        except Exception as e:
            self.logger.error(f"Error executing command: {e}")
            return {"status": "error", "error": str(e)}
