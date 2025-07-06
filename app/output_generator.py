# app/output_generator.py
import subprocess
import tempfile # Not strictly used in current test, but good to keep if future tests need it
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
import shutil # For directory cleanup

class OutputGenerator:
    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the OutputGenerator with application configuration.
        """
        self.config = config
        self.pandoc_executable = config.get('pandoc', {}).get('executable', 'pandoc')
        self.default_csl_style_path = config.get('pandoc', {}).get('default_csl_style')
        self.class_output_path = Path(config.get('paths', {}).get('class_output', 'output'))
        self.class_output_path.mkdir(parents=True, exist_ok=True)

    def _run_pandoc_command(self, command: List[str], input_markdown: Optional[str] = None) -> bool:
        """
        Runs a Pandoc command using subprocess, expecting to write to a file.
        Returns True on success, False on failure.
        """
        print(f"Executing Pandoc command: {' '.join(command)}") # Can be verbose
        try:
            process_kwargs = {
                'check': True, 
                'capture_output': True, 
                'text': True, 
                'encoding': 'utf-8'
            }
            if input_markdown is not None:
                process_kwargs['input'] = input_markdown

            result = subprocess.run(command, **process_kwargs)
            
            if result.stderr:
                print(f"Pandoc stderr (may include warnings or info):\n{result.stderr}")
            return True
        except FileNotFoundError:
            print(f"Error: Pandoc executable not found at '{self.pandoc_executable}'. "
                  "Please ensure Pandoc is installed and in your PATH, or configure the path correctly.")
            return False
        except subprocess.CalledProcessError as e:
            print(f"Error during Pandoc execution: {' '.join(command)}")
            print(f"Return code: {e.returncode}")
            if e.stdout:
                print(f"Pandoc Stdout:\n{e.stdout}")
            if e.stderr:
                print(f"Pandoc Stderr:\n{e.stderr}")
            return False
        except Exception as e:
            print(f"An unexpected error occurred while running Pandoc: {e}")
            return False

    def md_to_html(self,
                   markdown_string: str,
                   output_filename: Path,
                   bibliography_path: Optional[Union[str, Path]] = None,
                   csl_path: Optional[Union[str, Path]] = None,
                   standalone: bool = True,
                   extra_pandoc_args: Optional[List[str]] = None) -> bool:
        """
        Converts a Markdown string to an HTML string, post-processes it for
        hanging indents in the bibliography, and saves it to a file.
        """
        output_filename.parent.mkdir(parents=True, exist_ok=True)
        command = [self.pandoc_executable, "-f", "markdown", "-t", "html"]
        if standalone:
            command.extend(["--standalone"])

        if bibliography_path:
            command.extend(["--bibliography", str(Path(bibliography_path).resolve())])
            command.append("--citeproc")
            actual_csl_path = csl_path or self.default_csl_style_path
            if actual_csl_path:
                command.extend(["--csl", str(Path(actual_csl_path).resolve())])
            else:
                print("Info: No CSL style file provided for HTML generation with bibliography.")

        if extra_pandoc_args:
            command.extend(extra_pandoc_args)

        print(f"Generating HTML for: {output_filename}")

        try:
            # 1. Run Pandoc and capture the HTML output as a string
            result = subprocess.run(
                command,
                input=markdown_string,
                capture_output=True,
                text=True,
                check=True,
                encoding='utf-8'
            )
            if result.stderr:
                print(f"Pandoc stderr (may include warnings or info):\n{result.stderr}")

            html_content = result.stdout

            # 2. Post-process the HTML to add hanging indents
            # This is a robust way to add the style attribute without breaking other attributes.
            hanging_indent_style = 'style="padding-left: 2em; text-indent: -2em;"'
            find_str = 'class="csl-entry"'
            replace_str = f'{find_str} {hanging_indent_style}'

            modified_html_content = html_content.replace(find_str, replace_str)

            if modified_html_content != html_content:
                print("    Successfully added hanging indent styles to bibliography.")

            # 3. Write the modified HTML string to the output file
            with open(output_filename, 'w', encoding='utf-8') as f:
                f.write(modified_html_content)

            return True

        except FileNotFoundError:
            print(f"Error: Pandoc executable not found at '{self.pandoc_executable}'.")
            return False
        except subprocess.CalledProcessError as e:
            print(f"Error during Pandoc execution: {' '.join(command)}")
            print(f"Return code: {e.returncode}")
            if e.stdout: print(f"Pandoc Stdout:\n{e.stdout}")
            if e.stderr: print(f"Pandoc Stderr:\n{e.stderr}")
            return False
        except Exception as e:
            print(f"An unexpected error occurred while writing HTML to {output_filename}: {e}")
            return False


    def md_to_pdf(self,
                  markdown_string: str,
                  output_filename: Path,
                  bibliography_path: Optional[Union[str, Path]] = None,
                  csl_path: Optional[Union[str, Path]] = None,
                  extra_pandoc_args: Optional[List[str]] = None,
                  pdf_engine: Optional[str] = None) -> bool:
        output_filename.parent.mkdir(parents=True, exist_ok=True)
        command = [self.pandoc_executable, "-f", "markdown"]
        command.extend(["-o", str(output_filename)]) 
        if pdf_engine: command.extend([f"--pdf-engine={pdf_engine}"])
        if not pdf_engine or pdf_engine in ['pdflatex', 'xelatex', 'lualatex', 'tectonic']:
             command.append("--standalone") 
        if bibliography_path:
            command.extend(["--bibliography", str(Path(bibliography_path).resolve())])
            command.append("--citeproc")
            actual_csl_path = csl_path or self.default_csl_style_path
            if actual_csl_path: command.extend(["--csl", str(Path(actual_csl_path).resolve())])
            else: print("Info: No CSL style file provided or configured for PDF generation with bibliography.")
        if extra_pandoc_args: command.extend(extra_pandoc_args)
        print(f"Generating PDF: {output_filename}")
        return self._run_pandoc_command(command, input_markdown=markdown_string)

    def md_to_dokuwiki_syntax(self,
                              markdown_string: str,
                              bibliography_path: Optional[Union[str, Path]] = None,
                              csl_path: Optional[Union[str, Path]] = None,
                              extra_pandoc_args: Optional[List[str]] = None) -> Optional[str]:
        command = [self.pandoc_executable, "-f", "markdown", "-t", "dokuwiki"]
        if bibliography_path:
            command.extend(["--bibliography", str(Path(bibliography_path).resolve())])
            command.append("--citeproc")
            actual_csl_path = csl_path or self.default_csl_style_path
            if actual_csl_path: command.extend(["--csl", str(Path(actual_csl_path).resolve())])
            else: print("Info: No CSL style file provided or configured for DokuWiki conversion with bibliography.")
        if extra_pandoc_args: command.extend(extra_pandoc_args)
        print(f"Converting Markdown to DokuWiki syntax...")
        try:
            result = subprocess.run(command, input=markdown_string, capture_output=True, text=True, check=True, encoding='utf-8')
            if result.stderr: print(f"Pandoc stderr (DokuWiki conversion may include warnings):\n{result.stderr}")
            return result.stdout
        except FileNotFoundError:
            print(f"Error: Pandoc executable not found at '{self.pandoc_executable}'.")
            return None
        except subprocess.CalledProcessError as e:
            print(f"Error during Pandoc execution (DokuWiki conversion): {' '.join(command)}\nReturn code: {e.returncode}\nStdout:\n{e.stdout}\nStderr:\n{e.stderr}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred while converting to DokuWiki syntax: {e}")
            return None

    def md_to_docx(self,
                   markdown_string: str,
                   output_filename: Path,
                   bibliography_path: Optional[Union[str, Path]] = None,
                   csl_path: Optional[Union[str, Path]] = None,
                   reference_docx: Optional[Union[str, Path]] = None, # Path to a reference.docx for styling
                   extra_pandoc_args: Optional[List[str]] = None) -> bool:
        """
        Converts a Markdown string to a DOCX file using Pandoc.
        """
        output_filename.parent.mkdir(parents=True, exist_ok=True)
        command = [self.pandoc_executable, "-f", "markdown", "-t", "docx"]
        command.extend(["-o", str(output_filename)])
        command.append("--standalone") # Usually good for DOCX

        if bibliography_path:
            command.extend(["--bibliography", str(Path(bibliography_path).resolve())])
            command.append("--citeproc")
            actual_csl_path = csl_path or self.default_csl_style_path
            if actual_csl_path: command.extend(["--csl", str(Path(actual_csl_path).resolve())])
            else: print("Info: No CSL style file provided or configured for DOCX generation with bibliography.")
        
        if reference_docx:
            if Path(reference_docx).exists():
                command.extend([f"--reference-doc={str(Path(reference_docx).resolve())}"])
            else:
                print(f"Warning: Reference DOCX file not found at {reference_docx}. Using Pandoc default styling.")

        if extra_pandoc_args: command.extend(extra_pandoc_args)
        print(f"Generating DOCX: {output_filename}")
        return self._run_pandoc_command(command, input_markdown=markdown_string)

if __name__ == '__main__':
    print("Testing OutputGenerator...")

    try:
        pandoc_version_result = subprocess.run(['pandoc', '--version'], capture_output=True, text=True, check=True, encoding='utf-8')
        print(f"Pandoc Version Info:\n{pandoc_version_result.stdout.splitlines()[0]}")
    except Exception as e:
        print(f"Could not get Pandoc version: {e}")

    PROJECT_ROOT_OG_TEST = Path(__file__).resolve().parent.parent
    DUMMY_TEST_CLASS_DIR = PROJECT_ROOT_OG_TEST / "courses" / "TEST_OG_CLASS_FINAL" 
    DUMMY_OUTPUT_DIR_OG = DUMMY_TEST_CLASS_DIR / "output"
    DUMMY_INPUT_DIR_OG = DUMMY_TEST_CLASS_DIR / "input"
    
    if DUMMY_TEST_CLASS_DIR.exists(): shutil.rmtree(DUMMY_TEST_CLASS_DIR)
    DUMMY_OUTPUT_DIR_OG.mkdir(parents=True, exist_ok=True)
    DUMMY_INPUT_DIR_OG.mkdir(parents=True, exist_ok=True)

    dummy_csl_content = """<?xml version="1.0" encoding="utf-8"?>
<style xmlns="http://purl.org/net/xbiblio/csl" class="in-text" version="1.0"><info><title>Minimal Example CSL</title><id>http://example.com/minimal-csl</id><link href="http://example.com/minimal-csl" rel="self"/><updated>2024-05-24T00:00:00+00:00</updated></info><citation><layout prefix="(" suffix=")" delimiter="; "><text variable="citation-label"/></layout></citation><bibliography entry-spacing="0"><sort><key variable="author"/><key variable="issued"/></sort><layout><text variable="citation-label" suffix=". "/><text variable="title"/><date variable="issued" prefix=" (" suffix=")."/></layout></bibliography></style>"""
    dummy_csl_path = DUMMY_INPUT_DIR_OG / "test_style.csl"
    with open(dummy_csl_path, "w", encoding="utf-8") as f: f.write(dummy_csl_content)
    print(f"Created dummy CSL style file: {dummy_csl_path}")

    working_csl_yaml_content = """---
references:
- id: zigon
  author: [{family: Zigon, given: Jarrett}]
  issued: {year: 2013, month: 11}
  title: 'Human Rights as Moral Progress?: A Critique'
  type: article-journal
  volume: '28'
  issue: '4'
  page: "716-736"
  container-title: Cultural Anthropology
..."""
    csl_yaml_bib_path = DUMMY_INPUT_DIR_OG / "test_references.csl.yaml" 
    with open(csl_yaml_bib_path, "w", encoding="utf-8") as f: f.write(working_csl_yaml_content.strip())
    print(f"Created working CSL YAML bibliography file: {csl_yaml_bib_path}")

    dummy_config_og = {
        'pandoc': {'executable': 'pandoc', 'default_csl_style': str(dummy_csl_path)},
        'paths': {'class_output': str(DUMMY_OUTPUT_DIR_OG)}
    }
    og = OutputGenerator(config=dummy_config_og)
    sample_md_with_citation = "# Title with Citation\n\nThis is a paragraph with a citation [@zigon].\n\n## References"

    print("\n--- Testing HTML with CSL-YAML bibliography ---")
    html_out_path = DUMMY_OUTPUT_DIR_OG / "output_with_citations.html"
    success_html = og.md_to_html(sample_md_with_citation, html_out_path, bibliography_path=csl_yaml_bib_path)
    print(f"HTML with citations gen {'SUCCESSFUL' if success_html else 'FAILED'}.")
    if success_html:
        with open(html_out_path, "r", encoding="utf-8") as f: content = f.read()
        if "[@zigon]" not in content: print("  Citation processed in HTML.")
        else: print("  ERROR: Citation key still raw in HTML.")

    print("\n--- Testing DOCX with CSL-YAML bibliography ---")
    docx_out_path = DUMMY_OUTPUT_DIR_OG / "output_with_citations.docx"
    # You can create a dummy reference.docx for styling if desired.
    # For example: Path(DUMMY_INPUT_DIR_OG / "reference.docx").touch() 
    success_docx = og.md_to_docx(sample_md_with_citation, docx_out_path, bibliography_path=csl_yaml_bib_path) #, reference_docx="path/to/your/reference.docx")
    print(f"DOCX with citations gen {'SUCCESSFUL' if success_docx else 'FAILED'}.")
    if success_docx: print(f"  DOCX file created: {docx_out_path}. Please inspect manually.")
    
    print("\nOutputGenerator test completed.")

