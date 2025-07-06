# app/data_loader.py
import yaml
import csv
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Union

# --- Default input file and directory names ---
DEFAULT_INPUT_SOURCES = {
    "yaml_files": {
        "class_info": "class_info.yaml",
        "bibliography": "bibliography.csl.yaml"
    },
    "csv_files_df": {
        "weekly_schedule": "weekly_schedule.csv",
        "assignments": "assignments.csv",
        "weekly_keywords": "weekly_keywords.csv",
        "weekly_outcomes": "weekly_outcomes.csv",
        "weekly_brain_candy": "weekly_brain_candy.csv",
        "weekly_discussion_questions": "weekly_discussion_questions.csv",
    },
    "markdown_dirs": { # For collections of markdown files like weekly topics, lecture outlines
        "topics": "markdown_topics",
        "assignment_instructions": "markdown_assignments",
        "lecture_scripts": "markdown_lectures",
        "lecture_outlines": "markdown_lectures"
    },
    "static_pages_definitions": [] # Default is empty
}

def _get_source_category_mappings(config: Dict[str, Any], category: str) -> Dict[str, str]:
    """Helper to get all mappings for a category (like yaml_files, csv_files_df, markdown_dirs)."""
    mappings = DEFAULT_INPUT_SOURCES.get(category, {}).copy()
    config_category_specific_mappings = (config.get('input_sources', {}) or {}).get(category)
    if isinstance(config_category_specific_mappings, dict):
        mappings.update(config_category_specific_mappings)
    elif config_category_specific_mappings is not None:
        print(f"Warning: Expected a dictionary for input_sources.{category}, but found type {type(config_category_specific_mappings)}. Using defaults for this category.")
    return mappings

def load_yaml_file(file_path: Path) -> Dict[str, Any]:
    if not file_path.is_file():
        print(f"Warning: YAML file not found at {file_path}")
        return {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Error loading/parsing YAML file {file_path}: {e}")
        return {}

def load_csv_file_to_dataframe(file_path: Path) -> Union[pd.DataFrame, None]:
    if not file_path.is_file():
        print(f"Warning: CSV file not found at {file_path}")
        return None
    try:
        df = pd.read_csv(file_path, dtype=str)
        df = df.fillna('')
        # # Attempt to convert columns to numeric where possible, otherwise leave as string
        # for col in df.columns:
        #     try:
        #         df[col] = pd.to_numeric(df[col].str.strip())
        #     except (ValueError, TypeError):
        #         pass # Keep as object/string type
        return df
    except pd.errors.EmptyDataError:
        print(f"Warning: CSV file {file_path} is empty.")
        return pd.DataFrame()
    except Exception as e:
        print(f"Error reading CSV file {file_path} to DataFrame: {e}")
        return None

def load_markdown_file(file_path: Path) -> Union[str, None]:
    if not file_path.is_file():
        # This warning is now more contextual when called from the static page loader
        return None
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading Markdown file {file_path}: {e}")
        return None

def load_markdown_directory(directory_path: Path, config: Dict[str, Any]) -> Dict[str, str]:
    """
    Loads all markdown files from a directory using the extension defined in the config.
    """
    markdown_content = {}
    # Get the markdown extension from config, falling back to '.md' as a sensible default.
    markdown_ext = config.get('markdown_extension', '.md')

    if not directory_path.is_dir():
        print(f"Warning: Markdown directory not found at {directory_path}")
        return markdown_content
        
    for md_file in directory_path.glob(f"*{markdown_ext}"):
        if md_file.is_file():
            content = load_markdown_file(md_file)
            if content is not None:
                markdown_content[md_file.stem] = content
    return markdown_content

def load_class_data(config: Dict[str, Any]) -> Dict[str, Any]:
    class_input_path = Path((config.get('paths') or {}).get('class_input', ''))
    if not class_input_path.is_dir():
        print(f"Error: Class input directory not found at {class_input_path}. Cannot load data.")
        return {}

    data = {'yaml_data': {}, 'csv_data_df': {}, 'markdown_data': {}, 'static_pages_content': []}
    print(f"\nLoading data from class input directory: {class_input_path}")

    # --- Load YAML files ---
    yaml_file_mappings = _get_source_category_mappings(config, "yaml_files")
    for key, filename in yaml_file_mappings.items():
        if not filename: continue
        file_path = class_input_path / filename
        data['yaml_data'][key] = load_yaml_file(file_path)

    # --- Load CSV files to DataFrames ---
    csv_df_mappings = _get_source_category_mappings(config, "csv_files_df")
    for key, filename in csv_df_mappings.items():
        if not filename: continue
        file_path = class_input_path / filename
        df = load_csv_file_to_dataframe(file_path)
        if df is not None:
            data['csv_data_df'][key] = df
    
    # --- Load Markdown directories ---
    markdown_dir_mappings = _get_source_category_mappings(config, "markdown_dirs")
    for key, dirname in markdown_dir_mappings.items():
        if not dirname: continue
        dir_path = class_input_path / dirname
        # Pass the config to the function so it can find the correct file extension
        data['markdown_data'][key] = load_markdown_directory(dir_path, config)

    # --- Load Static Pages based on definitions in config ---
    static_page_definitions = (config.get('input_sources') or {}).get('static_pages', DEFAULT_INPUT_SOURCES.get('static_pages_definitions', []))
    
    if not isinstance(static_page_definitions, list):
        print(f"Warning: 'input_sources.static_pages' is not a list in config. Found type: {type(static_page_definitions)}. Cannot load static pages.")
        static_page_definitions = []

    loaded_static_pages = []
    for page_def in static_page_definitions:
        if not isinstance(page_def, dict):
            print(f"Warning: Invalid static page definition (not a dict): {page_def}. Skipping.")
            continue
        
        slug = page_def.get('slug')
        source_file_rel_path = page_def.get('source_file')
        
        if not slug or not isinstance(slug, str) or not slug.strip():
            print(f"Warning: Static page definition missing valid 'slug': {page_def}. Skipping.")
            continue
        if not source_file_rel_path or not isinstance(source_file_rel_path, str) or not source_file_rel_path.strip():
            print(f"Warning: Static page definition for slug '{slug}' missing valid 'source_file': {page_def}. Skipping.")
            continue

        source_file_abs_path = class_input_path / source_file_rel_path.strip()
        markdown_content = load_markdown_file(source_file_abs_path)
        
        if markdown_content is None:
            print(f"Warning: Could not load Markdown content for static page '{slug}' from '{source_file_abs_path}'. It will be empty.")
            markdown_content = ""

        loaded_static_pages.append({
            'slug': slug.strip(),
            'title': page_def.get('title'),
            'source_file': source_file_rel_path.strip(),
            'template': page_def.get('template'),
            'markdown_content': markdown_content
        })
    data['static_pages_content'] = loaded_static_pages
    if loaded_static_pages:
        print(f"Loaded {len(loaded_static_pages)} static page definitions and their content.")

    print("Data loading phase complete.")
    return data

if __name__ == '__main__':
    # This test block remains largely the same but will now function correctly.
    print("Testing data_loader.py...")
    PROJECT_ROOT_DL = Path(__file__).resolve().parent.parent
    
    dummy_class_input_for_static_test = PROJECT_ROOT_DL / "temp_dl_static_test_input"
    dummy_class_input_for_static_test.mkdir(parents=True, exist_ok=True)
    (dummy_class_input_for_static_test / "prose").mkdir(exist_ok=True)

    with open(dummy_class_input_for_static_test / "prose" / "syllabus.md", "w") as f:
        f.write("# Syllabus Main Text\nContent for syllabus.")
    with open(dummy_class_input_for_static_test / "prose" / "contact.md", "w") as f:
        f.write("Contact us here.")

    test_config = {
        'paths': {'class_input': str(dummy_class_input_for_static_test)},
        'input_sources': {
            'static_pages': [
                {'slug': 'syllabus', 'title': 'Course Syllabus', 'source_file': 'prose/syllabus.md', 'template': 'canvas/syllabus_template.md.j2'},
                {'slug': 'contact', 'source_file': 'prose/contact.md'},
                {'slug': 'invalid_no_source'},
                {'slug': 'policy', 'source_file': 'non_existent_policy.md'}
            ],
            'markdown_extension': '.md' # Example for testing
        }
    }
    loaded_data = load_class_data(test_config)
    print("\n--- Loaded Static Pages Data ---")
    if loaded_data.get('static_pages_content'):
        for page_data in loaded_data['static_pages_content']:
            print(f"  Slug: {page_data['slug']}, Title: {page_data.get('title')}, Template: {page_data.get('template')}, "
                  f"MD Loaded: {bool(page_data['markdown_content'])}, MD Preview: '{page_data['markdown_content'][:30]}...'")
    else:
        print("  No static pages content loaded.")
    
    import shutil
    shutil.rmtree(dummy_class_input_for_static_test)
    print("\nData loader test completed.")
