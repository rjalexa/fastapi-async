"""
Prompt management utilities for loading and formatting prompts from files.
"""

import os
from pathlib import Path
from typing import Dict, Any


def load_prompt(prompt_name: str) -> str:
    """
    Load a prompt template from the prompts directory.
    
    Args:
        prompt_name: Name of the prompt file (without .txt extension)
        
    Returns:
        The prompt template as a string
        
    Raises:
        FileNotFoundError: If the prompt file doesn't exist
        IOError: If there's an error reading the file
    """
    # Get the project root directory (assuming we're in src/worker/)
    current_dir = Path(__file__).parent
    project_root = current_dir.parent.parent
    prompt_file = project_root / "prompts" / f"{prompt_name}.txt"
    
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except IOError as e:
        raise IOError(f"Error reading prompt file {prompt_file}: {e}")


def format_prompt(template: str, **kwargs: Any) -> str:
    """
    Format a prompt template with the provided variables.
    
    Args:
        template: The prompt template string
        **kwargs: Variables to substitute in the template
        
    Returns:
        The formatted prompt string
    """
    try:
        return template.format(**kwargs)
    except KeyError as e:
        raise ValueError(f"Missing required variable for prompt template: {e}")
    except Exception as e:
        raise ValueError(f"Error formatting prompt template: {e}")


def load_and_format_prompt(prompt_name: str, **kwargs: Any) -> str:
    """
    Convenience function to load and format a prompt in one step.
    
    Args:
        prompt_name: Name of the prompt file (without .txt extension)
        **kwargs: Variables to substitute in the template
        
    Returns:
        The formatted prompt string
    """
    template = load_prompt(prompt_name)
    return format_prompt(template, **kwargs)
