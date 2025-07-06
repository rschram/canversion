# app/config_loader.py
import yaml
from pathlib import Path
import os
import shutil 

# Define base paths relative to this script's location or a known project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent # Parent of 'app/' dir
USER_CONFIG_DIR_NAME = "user_config" # Default, can be overridden by env var
COURSES_DIR_NAME = "courses" # The name of the directory holding all class folders
GLOBAL_CONFIG_FILE_NAME = "global_config.yaml"
CLASS_CONFIG_FILE_NAME = "class_config.yaml"

def load_yaml_file(file_path: Path) -> dict:
    """Loads a YAML file and returns its content as a dictionary."""
    if not file_path.is_file():
        print(f"Warning: YAML file not found at {file_path}")
        return {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file {file_path}: {e}")
        return {}
    except Exception as e:
        print(f"An unexpected error occurred while loading YAML file {file_path}: {e}")
        return {}

def merge_configs(global_config: dict, class_config: dict) -> dict:
    """
    Merges global and class-specific configurations.
    Class-specific configurations override global ones (deep merge for dicts).
    """
    merged = global_config.copy()
    for key, value in class_config.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_configs(merged[key], value)
        else:
            merged[key] = value
    return merged

def get_global_config_path() -> Path:
    """Determines the path to the global configuration file."""
    user_config_dir_env = os.getenv('COURSE_GEN_USER_CONFIG_DIR')
    if user_config_dir_env:
        # User explicitly set a directory for global_config.yaml
        global_config_base_dir = Path(user_config_dir_env)
        print(f"Using custom user config directory from COURSE_GEN_USER_CONFIG_DIR: {global_config_base_dir}")
    else:
        # Default: project_root/user_config/
        global_config_base_dir = PROJECT_ROOT / USER_CONFIG_DIR_NAME
    return global_config_base_dir / GLOBAL_CONFIG_FILE_NAME


def load_config(class_id: str) -> dict:
    """
    Loads and merges global and class-specific configurations.
    Allows 'course_data_root_dir' to be specified in global_config.yaml.
    """
    if not class_id:
        print("Error: class_id cannot be empty for load_config.")
        return {}

    global_config_file_path = get_global_config_path()
    print(f"Loading global configuration from: {global_config_file_path}")
    global_config = load_yaml_file(global_config_file_path)
    if not global_config and global_config_file_path.exists():
        print(f"Warning: Global config at {global_config_file_path} could not be parsed or is empty.")
    
    # --- Determine the parent directory for all 'courses' data ---
    # This path is the directory that *contains* the main 'COURSES_DIR_NAME' folder.
    courses_parent_dir_override = global_config.get('paths', {}).get('course_data_root_dir')
    
    actual_courses_parent_path: Path
    if courses_parent_dir_override:
        # Resolve to make absolute and normalize (e.g., handles '~')
        resolved_override_path = Path(courses_parent_dir_override).expanduser().resolve()
        print(f"Using custom course_data_root_dir from global_config.yaml: {resolved_override_path}")
        if not resolved_override_path.is_dir():
            print(f"Warning: Custom course_data_root_dir '{resolved_override_path}' "
                  f"from global_config.yaml not found or not a directory. Falling back to project root.")
            actual_courses_parent_path = PROJECT_ROOT
        else:
            actual_courses_parent_path = resolved_override_path
    else:
        actual_courses_parent_path = PROJECT_ROOT # Default: project_root is parent of 'courses' dir
        print(f"No 'paths.course_data_root_dir' in global_config.yaml. "
              f"Assuming '{COURSES_DIR_NAME}' directory is under project root: {PROJECT_ROOT}")

    # The main directory containing all individual class folders (e.g., .../courses)
    all_courses_main_dir_path = actual_courses_parent_path #/ COURSES_DIR_NAME

    # Path to the specific class directory: e.g., /path/to/root/courses/TEST001_S1_2025
    base_course_path = all_courses_main_dir_path / class_id
    
    # Path to the class-specific config file
    class_config_file_path = base_course_path / CLASS_CONFIG_FILE_NAME

    print(f"Loading class-specific configuration for '{class_id}' from: {class_config_file_path}")
    class_specific_config = load_yaml_file(class_config_file_path)
    if not class_specific_config and class_config_file_path.exists():
        print(f"Warning: Class config for {class_id} at {class_config_file_path} could not be parsed or is empty.")
    elif not class_config_file_path.exists():
        print(f"Error: Class configuration file not found for class_id '{class_id}' at {class_config_file_path}.")
        print(f"Please ensure '{COURSES_DIR_NAME}/{class_id}/{CLASS_CONFIG_FILE_NAME}' exists relative to your course data root.")
        return {} # Critical error if class config is missing

    # Merge configurations
    merged_config = merge_configs(global_config, class_specific_config)

    # Ensure essential 'paths' are in the merged_config and are absolute strings
    merged_config['paths'] = {
        'project_root': str(PROJECT_ROOT), # App's root directory
        'user_config_dir': str(global_config_file_path.parent),
        'course_data_root_actual': str(actual_courses_parent_path), # Actual parent of 'courses' dir
        'courses_dir_actual': str(all_courses_main_dir_path),       # Actual 'courses' dir path
        'class_base': str(base_course_path.resolve()),
        'class_input': str((base_course_path / "input").resolve()),
        'class_output': str((base_course_path / "output").resolve()),
        'templates': str((PROJECT_ROOT / "templates").resolve()), # Templates assumed with app code
        'global_config_file': str(global_config_file_path.resolve()),
        'class_config_file': str(class_config_file_path.resolve())
    }
    
    # Add class_id for easy access if not deeply nested somewhere already
    if 'class_meta' not in merged_config: merged_config['class_meta'] = {}
    merged_config['class_meta']['id'] = class_id


    # Ensure output directories exist for the class
    try:
        Path(merged_config['paths']['class_output']).mkdir(parents=True, exist_ok=True)
        (Path(merged_config['paths']['class_output']) / "canvas").mkdir(parents=True, exist_ok=True)
        (Path(merged_config['paths']['class_output']) / "dokuwiki").mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create output directories under {merged_config['paths']['class_output']}: {e}")


    print("Configurations loaded and merged successfully.")
    return merged_config

if __name__ == '__main__':
    print("Testing config_loader.py with custom course data root via global_config.yaml...")
    
    # --- Setup for testing custom course data root ---
    # 1. Create a temporary custom root directory for course data
    custom_data_root_for_test = PROJECT_ROOT / "temp_custom_course_data_root"
    custom_data_root_for_test.mkdir(exist_ok=True)

    # 2. Create the 'user_config' directory and a global_config.yaml inside PROJECT_ROOT
    # This global_config.yaml will point to the custom_data_root_for_test
    test_user_config_dir = PROJECT_ROOT / USER_CONFIG_DIR_NAME
    test_user_config_dir.mkdir(exist_ok=True)
    test_global_config_file = test_user_config_dir / GLOBAL_CONFIG_FILE_NAME
    
    global_config_content = {
        'user_details': {'name': 'Global Test User'},
        'paths': {
            'course_data_root_dir': str(custom_data_root_for_test) # Point to custom root
        },
        'pandoc': {'executable': 'pandoc_test'}
    }
    with open(test_global_config_file, 'w', encoding='utf-8') as f:
        yaml.dump(global_config_content, f)
    print(f"Created dummy global config: {test_global_config_file} pointing to custom data root: {custom_data_root_for_test}")

    # 3. Create the class structure *inside the custom data root*
    test_class_id_custom = "CUSTOM_LOC_TEST001"
    # This is actual_courses_parent_path / COURSES_DIR_NAME / class_id
    class_dir_in_custom_root = custom_data_root_for_test / COURSES_DIR_NAME / test_class_id_custom
    class_dir_in_custom_root.mkdir(parents=True, exist_ok=True)
    
    class_input_dir_in_custom_root = class_dir_in_custom_root / "input"
    class_input_dir_in_custom_root.mkdir(exist_ok=True)

    # Create class_config.yaml in the custom location
    class_config_content_custom = {
        'class_meta': {'title': 'Test Course in Custom Location'},
        'input_sources': {'yaml_files': {'class_info': 'info.yaml'}}
    }
    with open(class_dir_in_custom_root / CLASS_CONFIG_FILE_NAME, 'w', encoding='utf-8') as f:
        yaml.dump(class_config_content_custom, f)
    print(f"Created dummy class config in custom location: {class_dir_in_custom_root / CLASS_CONFIG_FILE_NAME}")

    # Create a dummy info.yaml for data_loader to find (optional for this specific test)
    with open(class_input_dir_in_custom_root / "info.yaml", "w", encoding='utf-8') as f:
        yaml.dump({"test_info": "Data from custom location"}, f)


    # --- Test loading the configuration ---
    # No environment variable for COURSE_GEN_USER_CONFIG_DIR, so it uses PROJECT_ROOT/user_config
    # No environment variable for COURSE_DATA_ROOT_DIR, so it relies on global_config.yaml
    config = load_config(test_class_id_custom)

    if config:
        print("\nSuccessfully loaded and merged configuration with custom course_data_root_dir:")
        import json # Moved import json here, only needed for this test block
        print(json.dumps(config, indent=2))

        # Verify paths point to the custom location
        expected_class_base = (custom_data_root_for_test / COURSES_DIR_NAME / test_class_id_custom).resolve()
        assert Path(config['paths']['class_base']) == expected_class_base, \
            f"Expected class_base {expected_class_base}, got {config['paths']['class_base']}"
        assert Path(config['paths']['class_input']).is_dir(), \
            f"Expected class_input dir {config['paths']['class_input']} to exist."
        assert Path(config['paths']['courses_dir_actual']) == (custom_data_root_for_test / COURSES_DIR_NAME).resolve()

        print("\nPath assertions for custom data root passed.")
    else:
        print("\nFailed to load configuration during custom data root test.")

    # --- Test fallback to default (project root for courses) ---
    print("\n--- Testing fallback to default course data root (project root) ---")
    # Temporarily use a global config *without* the custom path
    minimal_global_config_content = {'user_details': {'name': 'Minimal Global User'}}
    with open(test_global_config_file, 'w', encoding='utf-8') as f: # Overwrite global config
        yaml.dump(minimal_global_config_content, f)

    test_class_id_default = "DEFAULT_LOC_TEST002"
    # Create class structure in the default location: PROJECT_ROOT/courses/DEFAULT_LOC_TEST002
    class_dir_in_default_root = PROJECT_ROOT / COURSES_DIR_NAME / test_class_id_default
    class_dir_in_default_root.mkdir(parents=True, exist_ok=True)
    with open(class_dir_in_default_root / CLASS_CONFIG_FILE_NAME, 'w', encoding='utf-8') as f:
        yaml.dump({'class_meta': {'title': 'Test Course in Default Location'}}, f)
    print(f"Created dummy class config in default location: {class_dir_in_default_root / CLASS_CONFIG_FILE_NAME}")

    config_default = load_config(test_class_id_default)
    if config_default:
        print("\nSuccessfully loaded config with default course_data_root_dir:")
        if 'json' not in locals() and 'json' not in globals(): # Ensure json is imported if not already
            import json
        print(json.dumps(config_default, indent=2, default=str))
        expected_class_base_default = (PROJECT_ROOT / COURSES_DIR_NAME / test_class_id_default).resolve()
        assert Path(config_default['paths']['class_base']) == expected_class_base_default
        assert Path(config_default['paths']['courses_dir_actual']) == (PROJECT_ROOT / COURSES_DIR_NAME).resolve()
        print("\nPath assertions for default data root passed.")
    else:
        print("\nFailed to load configuration during default data root test.")


    # Clean up (optional, but good for repeatable tests)
    print("\nCleaning up test directories...")
    shutil.rmtree(custom_data_root_for_test, ignore_errors=True)
    shutil.rmtree(test_user_config_dir, ignore_errors=True) # Removes global_config.yaml too
    shutil.rmtree(class_dir_in_default_root, ignore_errors=True)
    # If 'courses' dir under project root might be empty after this, remove it
    default_courses_dir_path = PROJECT_ROOT / COURSES_DIR_NAME
    if default_courses_dir_path.exists() and not any(default_courses_dir_path.iterdir()):
        default_courses_dir_path.rmdir()

    print("\nConfig loader test with custom and default course data root completed.")

