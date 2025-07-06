# app/connectors/dokuwiki_handler.py
import os
from pathlib import Path
from typing import Dict, Any, Optional
import re
import shutil # For test cleanup

class DokuWikiHandler:
    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the DokuWikiHandler.

        Args:
            config (Dict[str, Any]): The application configuration, expected to contain:
                                     'dokuwiki': {'base_path': '/path/to/dokuwiki/data/pages'}
                                     'class_meta': {'dokuwiki_namespace': 'your:class:namespace'}
        """
        self.dokuwiki_config = config.get('dokuwiki', {})
        self.dokuwiki_base_data_path = self.dokuwiki_config.get('base_path') # Path to .../data/pages
        
        # The specific namespace for the current class, e.g., "courses:anth1001:s1_2024"
        self.class_namespace = config.get('class_meta', {}).get('dokuwiki_namespace')

        if not self.dokuwiki_base_data_path:
            raise ValueError("DokuWiki base_path (to data/pages) must be configured.")
        if not self.class_namespace:
            raise ValueError("DokuWiki class_namespace must be configured in class_meta.")
            
        self.dokuwiki_pages_path = Path(self.dokuwiki_base_data_path) # Ensure it's a Path object
        
        # FTP and XML-RPC are other ways to interact but are not implemented here.
        # self.ftp_host = self.dokuwiki_config.get('ftp_host')
        # self.xmlrpc_url = self.dokuwiki_config.get('xmlrpc_url')
        print(f"DokuWikiHandler initialized. Base pages path: {self.dokuwiki_pages_path}, Class namespace: {self.class_namespace}")

    def _sanitize_pagename(self, pagename: str) -> str:
        """
        Sanitizes a page name for DokuWiki.
        - Converts to lowercase.
        - Replaces spaces and invalid characters with underscores.
        - Removes leading/trailing underscores.
        - Ensures it doesn't contain colons (reserved for namespaces).
        """
        pagename = pagename.lower()
        pagename = pagename.replace(":", "_") # Colons are not allowed in page names themselves
        pagename = re.sub(r'[^a-z0-9_]+', '_', pagename) # Allow alphanumeric and underscore
        pagename = re.sub(r'_+', '_', pagename) # Replace multiple underscores with one
        pagename = pagename.strip('_')
        return pagename

    def _get_page_filepath(self, pagename: str, namespace: Optional[str] = None) -> Path:
        """
        Constructs the full file path for a DokuWiki page.

        Args:
            pagename (str): The name of the page (will be sanitized).
            namespace (Optional[str]): The DokuWiki namespace (e.g., "courses:current").
                                       If None, uses self.class_namespace.

        Returns:
            Path: The full path to the .txt file for the DokuWiki page.
        """
        target_namespace = namespace if namespace is not None else self.class_namespace
        if not target_namespace:
            raise ValueError("Namespace must be provided or configured for the class.")

        # Convert namespace (e.g., "foo:bar") to directory path parts ("foo/bar")
        namespace_parts = target_namespace.split(':')
        
        sanitized_pagename = self._sanitize_pagename(pagename)
        if not sanitized_pagename:
            raise ValueError("Pagename cannot be empty after sanitization.")

        # Full path: base_path / namespace_part1 / namespace_part2 / ... / pagename.txt
        page_path = self.dokuwiki_pages_path
        for part in namespace_parts:
            page_path = page_path / self._sanitize_pagename(part) # Sanitize namespace parts too

        return page_path / f"{sanitized_pagename}.txt"

    def save_page(self,
                  pagename: str,
                  content: str,
                  namespace: Optional[str] = None,
                  overwrite: bool = True) -> bool:
        """
        Saves content to a DokuWiki page file using direct file system access.

        Args:
            pagename (str): The desired name for the DokuWiki page.
            content (str): The content of the page (DokuWiki syntax or allowed HTML).
            namespace (Optional[str]): The DokuWiki namespace for the page.
                                       Defaults to the class_namespace.
            overwrite (bool): Whether to overwrite the page if it already exists.

        Returns:
            bool: True if the page was saved successfully, False otherwise.
        """
        try:
            filepath = self._get_page_filepath(pagename, namespace)
            
            if not overwrite and filepath.exists():
                print(f"Page already exists and overwrite is False: {filepath}")
                return False

            # Ensure the directory for the page (namespace path) exists
            filepath.parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"Successfully saved DokuWiki page: {filepath}")
            return True
        except ValueError as ve:
            print(f"Error preparing to save DokuWiki page: {ve}")
            return False
        except IOError as e:
            print(f"IOError saving DokuWiki page {filepath}: {e}")
            return False
        except Exception as e:
            print(f"An unexpected error occurred while saving DokuWiki page {filepath}: {e}")
            return False

    # Future methods could include:
    # def upload_media(self, filepath, media_id, namespace=None): ...
    # def page_exists(self, pagename, namespace=None) -> bool: ...
    # def get_page_content(self, pagename, namespace=None) -> Optional[str]: ...

if __name__ == '__main__':
    print("Testing DokuWikiHandler (direct file system access)...")

    # --- Setup for testing ---
    # Create a dummy DokuWiki 'data/pages' structure in a temporary location
    PROJECT_ROOT_DW_TEST = Path(__file__).resolve().parent.parent
    # Use a unique name for the test DokuWiki root to avoid conflicts
    DUMMY_DOKUWIKI_ROOT = PROJECT_ROOT_DW_TEST / "temp_dokuwiki_test_root"
    DUMMY_DOKUWIKI_PAGES_PATH = DUMMY_DOKUWIKI_ROOT / "data" / "pages"

    # Clean up any previous test run
    if DUMMY_DOKUWIKI_ROOT.exists():
        print(f"Cleaning up old dummy DokuWiki root: {DUMMY_DOKUWIKI_ROOT}")
        shutil.rmtree(DUMMY_DOKUWIKI_ROOT)
    
    DUMMY_DOKUWIKI_PAGES_PATH.mkdir(parents=True, exist_ok=True)
    print(f"Created dummy DokuWiki pages path for testing: {DUMMY_DOKUWIKI_PAGES_PATH}")

    dummy_config_dokuwiki = {
        'dokuwiki': {
            'base_path': str(DUMMY_DOKUWIKI_PAGES_PATH) # Points to .../data/pages
        },
        'class_meta': {
            'dokuwiki_namespace': 'courses:test101:s1_2025'
        }
    }

    try:
        dw_handler = DokuWikiHandler(config=dummy_config_dokuwiki)

        # --- Test Sanitization ---
        print("\n--- Testing pagename sanitization ---")
        dirty_name = "My Test Page: With !@#$ Chars and Spaces"
        clean_name = dw_handler._sanitize_pagename(dirty_name)
        expected_clean_name = "my_test_page_with_chars_and_spaces"
        print(f"Original: '{dirty_name}', Sanitized: '{clean_name}'")
        assert clean_name == expected_clean_name

        # --- Test File Path Construction ---
        print("\n--- Testing file path construction ---")
        test_page_name = "Weekly Topic 1"
        expected_namespace_path = Path("courses") / "test101" / "s1_2025"
        expected_filename = "weekly_topic_1.txt"
        
        # Test with class_namespace
        filepath1 = dw_handler._get_page_filepath(test_page_name)
        expected_path1 = DUMMY_DOKUWIKI_PAGES_PATH / expected_namespace_path / expected_filename
        print(f"Filepath for '{test_page_name}' in class namespace: {filepath1}")
        assert filepath1 == expected_path1

        # Test with a different, explicit namespace
        custom_ns = "playground:my_stuff"
        filepath2 = dw_handler._get_page_filepath("Another Page", namespace=custom_ns)
        expected_path2 = DUMMY_DOKUWIKI_PAGES_PATH / "playground" / "my_stuff" / "another_page.txt"
        print(f"Filepath for 'Another Page' in '{custom_ns}': {filepath2}")
        assert filepath2 == expected_path2


        # --- Test Saving a Page ---
        print("\n--- Testing saving a page ---")
        page_content = "====== My First Test Page ======\n\nThis is the content of the test page.\n\n  * Item 1\n  * Item 2"
        page_name_to_save = "First Test Page"
        
        save_success = dw_handler.save_page(page_name_to_save, page_content)
        assert save_success is True
        
        # Verify the file was created with correct content
        saved_filepath = DUMMY_DOKUWIKI_PAGES_PATH / expected_namespace_path / "first_test_page.txt"
        assert saved_filepath.exists()
        with open(saved_filepath, 'r', encoding='utf-8') as f:
            read_content = f.read()
        assert read_content == page_content
        print(f"Content of saved page {saved_filepath} verified.")

        # Test saving to a different namespace
        page_content_ns2 = "Content for playground page."
        save_success_ns2 = dw_handler.save_page("Playground Page", page_content_ns2, namespace="playground")
        assert save_success_ns2 is True
        saved_filepath_ns2 = DUMMY_DOKUWIKI_PAGES_PATH / "playground" / "playground_page.txt"
        assert saved_filepath_ns2.exists()
        print(f"Page saved to custom namespace {saved_filepath_ns2} verified.")


        # Test overwrite (default is True)
        overwrite_content = "====== Overwritten Content ======"
        save_overwrite_success = dw_handler.save_page(page_name_to_save, overwrite_content) # Same page name
        assert save_overwrite_success is True
        with open(saved_filepath, 'r', encoding='utf-8') as f:
            read_content_overwritten = f.read()
        assert read_content_overwritten == overwrite_content
        print(f"Page {saved_filepath} successfully overwritten.")

        # Test no overwrite
        no_overwrite_content = "This should not be written."
        save_no_overwrite_fail = dw_handler.save_page(page_name_to_save, no_overwrite_content, overwrite=False)
        assert save_no_overwrite_fail is False # Should fail as overwrite is False
        with open(saved_filepath, 'r', encoding='utf-8') as f:
            read_content_not_overwritten = f.read()
        assert read_content_not_overwritten == overwrite_content # Content should be the overwritten one
        print(f"Page {saved_filepath} correctly not overwritten when overwrite=False.")


    except ValueError as e:
        print(f"Configuration error during testing: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during DokuWikiHandler testing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up the dummy DokuWiki root directory
        if DUMMY_DOKUWIKI_ROOT.exists():
            print(f"\nCleaning up dummy DokuWiki root: {DUMMY_DOKUWIKI_ROOT}")
            shutil.rmtree(DUMMY_DOKUWIKI_ROOT)
        print("\nDokuWikiHandler test completed.")

