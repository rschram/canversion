# app/template_manager.py
from jinja2 import Environment, FileSystemLoader, select_autoescape, StrictUndefined
from pathlib import Path
from typing import Dict, Any, Union 
from datetime import datetime, timedelta
import dateparser



class TemplateManager:
    def __init__(self, template_dir: Union[str, Path]):
        """
        Initializes the Jinja2 environment.

        Args:
            template_dir (Union[str, Path]): The path to the directory containing Jinja2 templates.
        """
        if not Path(template_dir).is_dir():
            # It might be better to let this raise FileNotFoundError directly
            # or handle it more specifically if template_dir is None or empty string.
            raise FileNotFoundError(f"Template directory not found or is not a directory: {template_dir}")

        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml', 'md', 'dw']), # Add 'dw' for DokuWiki if needed
            undefined=StrictUndefined,  # Raise errors for undefined variables in templates
            trim_blocks=True,      # Good for cleaning up whitespace
            lstrip_blocks=True     # Good for cleaning up whitespace
        )
        # You can add custom filters or global functions to the environment here if needed
        # For example: self.env.filters['custom_filter'] = my_custom_filter_function

        def anydate(d,f="%m %d, %Y"):
            try: 
                return datetime.strftime(dateparser.parse(str(d)),f)
            except:
                return d

        self.env.filters['anydate'] = anydate
        
        print(f"Jinja2 Environment initialized with template directory: {template_dir}")

    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Renders a specified template with the given context.

        Args:
            template_name (str): The name of the template file (e.g., "canvas/weekly_page.md.j2").
            context (Dict[str, Any]): A dictionary containing data to pass to the template.

        Returns:
            str: The rendered content as a string.
        
        Raises:
            jinja2.exceptions.TemplateNotFound: If the template cannot be found.
            jinja2.exceptions.UndefinedError: If a variable used in the template is not in the context.
            Exception: For other rendering errors.
        """
        try:
            template = self.env.get_template(template_name)
            rendered_content = template.render(context)
            return rendered_content
        except Exception as e:
            print(f"Error rendering template '{template_name}': {e}")
            # Depending on your error handling strategy, you might want to re-raise,
            # return an error message, or handle it differently.
            raise

if __name__ == '__main__':
    # This is an example of how to use the TemplateManager.
    # For this to run, you need:
    # 1. A 'templates' directory at the project root (course_material_generator/templates).
    # 2. A dummy template file, e.g., 'templates/test_template.txt.j2'.

    PROJECT_ROOT_TEMPLATE_MANAGER = Path(__file__).resolve().parent.parent
    DUMMY_TEMPLATES_DIR = PROJECT_ROOT_TEMPLATE_MANAGER / "templates"
    DUMMY_TEMPLATES_DIR.mkdir(exist_ok=True) # Create if it doesn't exist

    # Create a dummy template file for testing
    dummy_template_name = "test_template.txt.j2"
    dummy_template_path = DUMMY_TEMPLATES_DIR / dummy_template_name
    with open(dummy_template_path, "w", encoding="utf-8") as f:
        f.write("Hello, {{ name }}!\n")
        f.write("Your course is: {{ course.title }} ({{ course.code }})\n")
        f.write("Items:\n")
        f.write("{% for item in items %}- {{ item }}\n{% endfor %}")

    print(f"Dummy template created at: {dummy_template_path}")

    try:
        # Initialize the template manager
        template_manager = TemplateManager(template_dir=DUMMY_TEMPLATES_DIR)

        # Create some dummy context data
        test_context = {
            "name": "Test User",
            "course": {
                "title": "Advanced Course Generation",
                "code": "GEN101"
            },
            "items": ["Apple", "Banana", "Cherry"]
        }

        # Render the template
        print(f"\nRendering template '{dummy_template_name}'...")
        rendered_output = template_manager.render_template(dummy_template_name, test_context)
        print("\n--- Rendered Output ---")
        print(rendered_output)
        print("--- End of Rendered Output ---")

    except FileNotFoundError as e:
        print(f"Error during test: {e}")
        print("Please ensure the 'templates' directory exists at the project root.")
    except NameError as e:
        print(f"A NameError occurred: {e}. This might be due to a missing import for type hinting.")
    except Exception as e:
        print(f"An error occurred during the test: {e}")
    finally:
        # Clean up dummy template (optional)
        # if dummy_template_path.exists():
        #     dummy_template_path.unlink()
        # if not any(DUMMY_TEMPLATES_DIR.iterdir()): # if templates dir is empty
        #     DUMMY_TEMPLATES_DIR.rmdir()
        print("\nTemplate manager test completed.")
