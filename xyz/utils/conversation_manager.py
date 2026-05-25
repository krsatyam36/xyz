import os
import json
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class ConversationManager:
    """Manages multi-turn conversations with persistent memory."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages = []
        self.context_stack = []  # Stack of file contexts
        self.last_action = None
        self.action_history = []
    
    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None):
        """Add message to conversation."""
        msg = {
            "role": role,
            "content": content,
            "timestamp": self._timestamp(),
        }
        if metadata:
            msg.update(metadata)
        self.messages.append(msg)
    
    def get_context_window(self, max_messages: int = 10) -> List[Dict]:
        """Get recent context for prompt."""
        return self.messages[-max_messages:]
    
    def push_context(self, file_path: str, context: str):
        """Push file context onto stack."""
        self.context_stack.append({
            "file": file_path,
            "context": context,
            "timestamp": self._timestamp(),
        })
    
    def pop_context(self) -> Optional[Dict]:
        """Pop file context from stack."""
        return self.context_stack.pop() if self.context_stack else None
    
    def get_current_context(self) -> Optional[Dict]:
        """Get current file context."""
        return self.context_stack[-1] if self.context_stack else None
    
    def record_action(self, action_type: str, details: Dict):
        """Record an action performed."""
        self.action_history.append({
            "type": action_type,
            "details": details,
            "timestamp": self._timestamp(),
        })
        self.last_action = action_type
    
    def get_summary(self) -> Dict[str, Any]:
        """Get conversation summary."""
        return {
            "session_id": self.session_id,
            "message_count": len(self.messages),
            "action_count": len(self.action_history),
            "current_context": self.get_current_context(),
            "last_action": self.last_action,
        }
    
    @staticmethod
    def _timestamp() -> str:
        from datetime import datetime
        return datetime.now().isoformat()


class InteractiveFeatures:
    """Interactive features for CLI conversations."""
    
    @staticmethod
    def parse_command(user_input: str) -> tuple[str, List[str]]:
        """Parse user commands and arguments."""
        if not user_input.startswith('/'):
            return ('chat', [])
        
        parts = user_input.split()
        command = parts[0].lower()
        args = parts[1:]
        return (command, args)
    
    @staticmethod
    def format_response(response: str, code_blocks: Optional[List[Dict]] = None) -> str:
        """Format AI response with proper highlighting."""
        if code_blocks:
            for block in code_blocks:
                language = block.get('language', 'text')
                code = block.get('code', '')
                response += f"\n\n```{language}\n{code}\n```\n"
        return response
    
    @staticmethod
    def create_file_patch(old_content: str, new_content: str) -> str:
        """Create a unified diff patch."""
        import difflib
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = difflib.unified_diff(old_lines, new_lines)
        return ''.join(diff)


class FeatureFlags:
    """Feature flags for enabling/disabling capabilities."""
    
    FEATURES = {
        'code_execution': True,
        'file_modification': True,
        'shell_commands': True,
        'project_analysis': True,
        'test_running': True,
        'lint_checking': True,
        'git_integration': True,
        'dependency_management': True,
        'multi_file_edit': True,
        'interactive_debugging': True,
    }
    
    @classmethod
    def is_enabled(cls, feature: str) -> bool:
        """Check if feature is enabled."""
        return cls.FEATURES.get(feature, False)
    
    @classmethod
    def enable(cls, feature: str):
        """Enable feature."""
        cls.FEATURES[feature] = True
        logger.info(f"Enabled feature: {feature}")
    
    @classmethod
    def disable(cls, feature: str):
        """Disable feature."""
        cls.FEATURES[feature] = False
        logger.info(f"Disabled feature: {feature}")


class GitIntegration:
    """Git operations helper."""
    
    def __init__(self, repo_path: Optional[str] = None):
        self.repo_path = Path(repo_path or os.getcwd()).resolve()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get git status."""
        try:
            result = self._run_git('status --porcelain')
            return {
                "status": "ok",
                "changes": result.strip().split('\n') if result else [],
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def get_diff(self, file_path: Optional[str] = None) -> str:
        """Get diff for file or all changes."""
        try:
            if file_path:
                return self._run_git(f'diff {file_path}')
            return self._run_git('diff')
        except Exception as e:
            return f"Error: {e}"
    
    def create_branch(self, branch_name: str) -> Dict[str, Any]:
        """Create new git branch."""
        try:
            self._run_git(f'checkout -b {branch_name}')
            return {"status": "ok", "branch": branch_name}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def commit(self, message: str) -> Dict[str, Any]:
        """Create git commit."""
        try:
            self._run_git(f'add .')
            self._run_git(f'commit -m "{message}"')
            return {"status": "ok", "message": message}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def _run_git(self, cmd: str) -> str:
        """Run git command."""
        import subprocess
        result = subprocess.run(
            f'git {cmd}',
            shell=True,
            capture_output=True,
            text=True,
            cwd=self.repo_path,
        )
        if result.returncode != 0:
            raise Exception(result.stderr)
        return result.stdout


class DependencyManager:
    """Manage project dependencies."""
    
    def __init__(self, repo_path: Optional[str] = None):
        self.repo_path = Path(repo_path or os.getcwd()).resolve()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def detect_package_manager(self) -> str:
        """Detect package manager."""
        managers = {
            'poetry.lock': 'poetry',
            'package-lock.json': 'npm',
            'yarn.lock': 'yarn',
            'pnpm-lock.yaml': 'pnpm',
            'Pipfile.lock': 'pipenv',
            'requirements.txt': 'pip',
        }
        
        for file, manager in managers.items():
            if (self.repo_path / file).exists():
                return manager
        return 'unknown'
    
    def list_dependencies(self) -> List[str]:
        """List all dependencies."""
        try:
            if (self.repo_path / 'requirements.txt').exists():
                content = (self.repo_path / 'requirements.txt').read_text()
                return [line.split('==')[0].strip() for line in content.split('\n') if line.strip()]
            
            if (self.repo_path / 'package.json').exists():
                data = json.loads((self.repo_path / 'package.json').read_text())
                deps = list(data.get('dependencies', {}).keys())
                deps.extend(list(data.get('devDependencies', {}).keys()))
                return deps
        except Exception as e:
            self.logger.error(f"Error listing dependencies: {e}")
        
        return []
    
    def add_dependency(self, package: str, dev: bool = False) -> Dict[str, Any]:
        """Add new dependency."""
        manager = self.detect_package_manager()
        commands = {
            'pip': f'pip install {package}',
            'npm': f'npm install {"--save-dev" if dev else ""} {package}',
            'poetry': f'poetry add {"--dev" if dev else ""} {package}',
            'yarn': f'yarn add {"--dev" if dev else ""} {package}',
        }
        
        cmd = commands.get(manager, f'{manager} install {package}')
        self.logger.info(f"Installing {package}: {cmd}")
        
        try:
            import subprocess
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                cwd=self.repo_path,
            )
            return {
                "status": "ok" if result.returncode == 0 else "failed",
                "package": package,
                "manager": manager,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
