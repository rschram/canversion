# Canversion. Sick of WYSIWYG but have to use Canvas? Undergo a Canversion.
# app/main.py
import argparse
from pathlib import Path
import sys
import json
import re
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import dateparser

# --- Import your application modules ---
try:
    from .config_loader import load_config
    from .data_loader import load_class_data
    from .data_processor import DataProcessor
    from .template_manager import TemplateManager
    from .output_generator import OutputGenerator
    from .connectors.canvas_api import CanvasAPI
    from .connectors.dokuwiki_handler import DokuWikiHandler
except ImportError:
    from config_loader import load_config
    from data_loader import load_class_data
    from data_processor import DataProcessor
    from template_manager import TemplateManager
    from output_generator import OutputGenerator
    from connectors.canvas_api import CanvasAPI
    from connectors.dokuwiki_handler import DokuWikiHandler

AVAILABLE_TASKS = [
    "canvas_weekly_pages",
    "tutorial_lesson_plans",
    "canvas_static_pages",
    "canvas_assignments",
    "dokuwiki_weekly_pages",
    "dokuwiki_class_overview",
    "dokuwiki_lecture_outlines",
    "lecture_scripts_printable",
    "generate_syllabus_docx",
    "wiki_weekly_pages",
    "wiki_overview",
    "wiki_assignments",
    "wiki_static_pages", 
    "create_skeletons", 
]







def get_citation_paths(config: Dict[str, Any], context_description: str) -> tuple[Optional[Path], Optional[Path]]:
    bib_filename_config_val = ((config.get('input_sources') or {}).get('yaml_files') or {}).get('bibliography')
    bibliography_path: Optional[Path] = None
    if isinstance(bib_filename_config_val, str) and bib_filename_config_val.strip():
        class_input_str_path = (config.get('paths') or {}).get('class_input')
        if isinstance(class_input_str_path, str):
            try:
                potential_bib_path = Path(class_input_str_path) / bib_filename_config_val.strip()
                if potential_bib_path.exists() and potential_bib_path.is_file():
                    bibliography_path = potential_bib_path
                    print(f"  Using bibliography for {context_description}: {bibliography_path}")
                else:
                    print(f"  Warning: Bibliography file '{potential_bib_path}' for {context_description} not found.")
            except TypeError: pass
        else:
            print(f"  Warning: 'paths.class_input' not configured correctly for {context_description}. Cannot locate bibliography.")
    elif bib_filename_config_val is not None:
        print(f"  Warning: 'bibliography' filename in config for {context_description} is not a valid string: '{bib_filename_config_val}'.")

    csl_style_path_config_val = (config.get('pandoc') or {}).get('default_csl_style')
    csl_style_path: Optional[Path] = None
    if isinstance(csl_style_path_config_val, str) and csl_style_path_config_val.strip():
        potential_csl_path = Path(csl_style_path_config_val.strip())
        if not potential_csl_path.is_absolute():
            project_root_str = (config.get('paths') or {}).get('project_root')
            if project_root_str: potential_csl_path = Path(project_root_str) / potential_csl_path
        if potential_csl_path.exists() and potential_csl_path.is_file():
            csl_style_path = potential_csl_path
            print(f"  Using CSL style for {context_description}: {csl_style_path}")
        else:
            print(f"  Warning: Default CSL style file '{potential_csl_path}' for {context_description} not found.")
    elif csl_style_path_config_val is not None:
        print(f"  Warning: 'default_csl_style' in config for {context_description} is not a valid string path: '{csl_style_path_config_val}'.")
    return bibliography_path, csl_style_path

# --- New Task: Create Skeleton Files ---
def create_skeleton_files(config, processed_data):
    print("\n>>> Task: Creating Skeleton Input Files <<<")
    
    skeleton_targets = config.get('skeleton_file_targets', {})
    if not skeleton_targets:
        print("  No 'skeleton_file_targets' defined in class_config.yaml. Skipping task.")
        return

    class_input_path = Path((config.get('paths') or {}).get('class_input', ''))
    if not class_input_path.is_dir():
        print(f"  Error: Class input path '{class_input_path}' not found. Cannot create skeleton files.")
        return

    # Helper function to create a file if it doesn't exist
    def create_file_if_not_exists(filepath: Path, initial_content: str = ""):
        if not filepath.exists():
            try:
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.touch()
                if initial_content:
                    filepath.write_text(initial_content, encoding='utf-8')
                print(f"    Created skeleton file: {filepath}")
            except Exception as e:
                print(f"    Error creating file {filepath}: {e}")
        else:
            print(f"    File already exists, skipping: {filepath}")

    # Process weekly-based skeletons
    all_weeks_data = processed_data.get('weeks')
    if all_weeks_data:
        for target_key, md_dir_key in skeleton_targets.items():
            if target_key in ["weekly_topics", "lecture_scripts", "lecture_outlines"]: # Add any other weekly targets here
                md_dir_name = ((config.get('input_sources') or {}).get('markdown_dirs') or {}).get(md_dir_key)
                if not md_dir_name:
                    print(f"  Warning: Markdown directory key '{md_dir_key}' for skeleton target '{target_key}' not found in input_sources config. Skipping.")
                    continue
                
                target_dir = class_input_path / md_dir_name
                print(f"\n  Processing weekly skeletons for '{target_key}' in directory: {target_dir}")
                for week_info in all_weeks_data:
                    week_num = str(week_info.get('week_number', '')).zfill(2)
                    # Define a consistent filename stem, e.g., week_01, week_02
                    # You can customize this based on your preference
                    filename_stem = f"week_{week_num}"
                    if "script" in target_key:
                        filename_stem += "_script"
                    elif "outline" in target_key:
                        filename_stem += "_outline"
                    elif "topic" in target_key:
                        filename_stem += "_topic"

                    filepath = target_dir / f"{filename_stem}.text"
                    # Add a simple H1 header as initial content
                    initial_content = f"# {week_info.get('title', f'Week {week_num}')}\n\n"
                    create_file_if_not_exists(filepath, initial_content)

    # Process assignment-based skeletons
    assignments_data = processed_data.get('assignments')
    if assignments_data and "assignment_instructions" in skeleton_targets:
        md_dir_key = skeleton_targets['assignment_instructions']
        md_dir_name = ((config.get('input_sources') or {}).get('markdown_dirs') or {}).get(md_dir_key)
        if md_dir_name:
            target_dir = class_input_path / md_dir_name
            print(f"\n  Processing assignment skeletons in directory: {target_dir}")
            for assign_info in assignments_data:
                # Use the 'instructions-file' field from assignments.csv to get the filename
                instructions_filename = assign_info.get('instructions-file')
                if instructions_filename and isinstance(instructions_filename, str):
                    filepath = target_dir / instructions_filename
                    initial_content = f"# Assignment: {assign_info.get('title', 'Assignment Instructions')}\n\n## Instructions\n\n"
                    create_file_if_not_exists(filepath, initial_content)
                else:
                    print(f"  Warning: Assignment '{assign_info.get('title')}' is missing the 'instructions-file' field in assignments.csv. Cannot create skeleton file.")
        else:
            print(f"  Warning: Markdown directory key '{md_dir_key}' for assignment_instructions not found in input_sources config. Skipping assignment skeletons.")



# --- Task Implementations ---
def generate_canvas_weekly_pages(config, processed_data, tm, og, canvas_api, target_weeks=None):
    print("\n>>> Task: Generating Canvas Weekly Pages <<<") 
    all_weeks_data = processed_data.get('weeks')
    if not all_weeks_data: print("  No weekly data found in processed_data. Skipping task."); return
    weeks_to_process = all_weeks_data
    if target_weeks:
        str_target_weeks = [str(w).strip() for w in target_weeks]
        weeks_to_process = [week for week in all_weeks_data if str(week.get('week_number')).strip() in str_target_weeks]
        if not weeks_to_process: print(f"  No weeks found matching target(s): {str_target_weeks}. Available: {[str(w.get('week_number')).strip() for w in all_weeks_data]}. Skipping."); return
        print(f"  Processing Canvas pages for week(s): {', '.join(str_target_weeks)}")
    else: print("  Processing all available Canvas weekly pages.")
    canvas_course_id = (config.get('class_meta') or {}).get('canvas_course_id')
    if not canvas_course_id: print("  Error: Canvas Course ID not configured. Skipping."); return
    bibliography_path, csl_style_path = get_citation_paths(config, "Canvas weekly pages")
    for week_info in weeks_to_process:
        week_num = week_info.get('week_number', 'N/A'); week_title = week_info.get('title', f"Week {week_num}")
        page_title = f"Week {week_num}: {week_title}"
        page_url_slug_raw = f"week-{str(week_num).lower().replace(' ', '_')}-{week_title.lower().replace(' ', '_').replace('/', '_')[:30]}"
        page_url_slug = "".join(c for c in page_url_slug_raw if c.isalnum() or c in ['-', '_'])
        if not page_url_slug: page_url_slug = f"week_{str(week_num).lower()}_page"
        print(f"\n  Processing Canvas Page: {page_title}")
        try:
            template_context = {'week': week_info, 'class_details': processed_data.get('class_details', {}), 'course': processed_data}; 
            intermediate_markdown = tm.render_template("canvas/weekly_page.md.j2", template_context) 
            class_output_path_str = (config.get('paths') or {}).get('class_output')
            if not class_output_path_str: print(f"    Error: 'paths.class_output' not configured for {page_title}."); continue
            html_output_dir = Path(class_output_path_str) / "canvas" / "weekly_pages"; html_output_dir.mkdir(parents=True, exist_ok=True)
            html_filename = html_output_dir / f"{page_url_slug}.html"
            success_html = og.md_to_html(intermediate_markdown, html_filename, bibliography_path, csl_style_path, standalone=False) 
            if not success_html: print(f"    Error converting to HTML for {page_title}. Skipping upload."); continue
            with open(html_filename, 'r', encoding='utf-8') as f: html_body_content = f.read()
            print(f"    Uploading to Canvas: {page_title} (slug: {page_url_slug})")
            canvas_page = canvas_api.create_or_update_page(course_id=canvas_course_id, title=page_title, body_html=html_body_content, page_url=page_url_slug, published=(config.get('canvas_content_defaults') or {}).get('publish_pages', False))
            if canvas_page: print(f"    Successfully created/updated Canvas page: {canvas_page.get('html_url', page_title)}")
            else: print(f"    Failed to create/update Canvas page for {page_title}.")
        except Exception as e: 
            print(f"  Error processing Canvas week {week_num} ('{week_title}'): {e}")
            import traceback 
            traceback.print_exc()

def generate_dokuwiki_lecture_outlines(config, processed_data, tm, og, dw_handler, target_weeks=None):
    print("\n>>> Task: Generating DokuWiki Lecture Outlines <<<")
    all_lecture_outlines = processed_data.get('lecture_outlines')
    if not all_lecture_outlines: print("  No lecture outlines found. Skipping."); return
    outlines_to_process = {}
    if target_weeks:
        str_target_weeks = [str(w).strip() for w in target_weeks]; print(f"  Filtering lecture outlines for week(s): {', '.join(str_target_weeks)}")
        for stem, content in all_lecture_outlines.items():
            match = re.search(r'(?:lecture_|lec_|week_|wk_)(\d+)', stem.lower())
            if match:
                week_num_in_stem = match.group(1).lstrip('0')
                if week_num_in_stem in str_target_weeks: outlines_to_process[stem] = content
        if not outlines_to_process: print(f"  No lecture outlines match target week(s): {str_target_weeks}. Skipping."); return
        print(f"  Processing specified lecture outlines: {list(outlines_to_process.keys())}")
    else: outlines_to_process = all_lecture_outlines; print(f"  Processing all lecture outlines: {list(outlines_to_process.keys())}")
    
    class_details = processed_data.get('class_details', {}); dokuwiki_base_ns = (config.get('class_meta') or {}).get('dokuwiki_namespace', 'playground')
    bibliography_path, csl_style_path = get_citation_paths(config, "DokuWiki lecture outlines")

    for outline_stem, raw_markdown_for_outline in outlines_to_process.items(): 
        page_title_for_template = outline_stem.replace('_', ' ').replace('-', ' ').capitalize()
        dokuwiki_pagename = outline_stem
        print(f"\n  Processing DokuWiki Lecture Outline for pagename: {dokuwiki_pagename}")
        try:
            template_context = {
                'outline_content_md': raw_markdown_for_outline, 
                'page_title': page_title_for_template, 
                'class_details': class_details,
                'course': processed_data 
            }
            intermediate_markdown = tm.render_template("dokuwiki/lecture_outline.md.j2", template_context)
            print(f"    Intermediate Markdown for {dokuwiki_pagename} generated.")

            final_content_for_dokuwiki = og.md_to_dokuwiki_syntax(
                intermediate_markdown, 
                bibliography_path, 
                csl_style_path
            )
            if final_content_for_dokuwiki is None: 
                print(f"    Error converting to DokuWiki syntax for {page_title_for_template}. Skipping save."); continue
            
            lecture_ns = f"{dokuwiki_base_ns}:lectures"
            success = dw_handler.save_page(dokuwiki_pagename, final_content_for_dokuwiki, lecture_ns)
            if success: print(f"    Successfully saved DokuWiki page: {lecture_ns}:{dokuwiki_pagename}")
            else: print(f"    Failed to save DokuWiki page: {lecture_ns}:{dokuwiki_pagename}")
        except Exception as e: 
            print(f"  Error processing DokuWiki outline {outline_stem}: {e}")
            import traceback 
            traceback.print_exc()

def generate_lecture_scripts_printable(config, processed_data, tm, og, target_weeks=None):
    print("\n>>> Task: Generating Printable Lecture Scripts <<<") 
    all_lecture_scripts = processed_data.get('lecture_scripts')
    if not all_lecture_scripts: print("  No lecture scripts found. Skipping."); return
    scripts_to_process = {}
    if target_weeks:
        str_target_weeks = [str(w).strip() for w in target_weeks]; print(f"  Filtering lecture scripts for week(s): {', '.join(str_target_weeks)}")
        for stem, content in all_lecture_scripts.items():
            match = re.search(r'(?:lecture_|lec_|week_|wk_)(\d+)(?:_script)?', stem.lower())
            if match:
                week_num_in_stem = match.group(1).lstrip('0')
                if week_num_in_stem in str_target_weeks: scripts_to_process[stem] = content
        if not scripts_to_process: print(f"  No lecture scripts match target week(s): {str_target_weeks}. Skipping."); return
        print(f"  Processing specified lecture scripts: {list(scripts_to_process.keys())}")
    else: scripts_to_process = all_lecture_scripts; print(f"  Processing all lecture scripts: {list(scripts_to_process.keys())}")
    class_details = processed_data.get('class_details', {}); bibliography_path, csl_style_path = get_citation_paths(config, "printable lecture scripts")
    output_dir_base_str = (config.get('paths') or {}).get('class_output')
    if not output_dir_base_str: print("  Error: 'paths.class_output' not configured. Cannot save scripts."); return
    printable_scripts_output_dir = Path(output_dir_base_str) / "lecture_scripts_printable"; printable_scripts_output_dir.mkdir(parents=True, exist_ok=True)
    weeks_data = {str(w.get('week_number')).strip(): w for w in processed_data.get('weeks', [])}
    for script_stem, script_md_content in scripts_to_process.items():
        week_num_for_script = "N/A"; week_title_for_script = script_stem.replace("_", " ").capitalize(); lecture_date_for_script = "Not specified"
        match = re.search(r'(?:lecture_|lec_|week_|wk_)(\d+)', script_stem.lower())
        if match:
            week_num_for_script = match.group(1).lstrip('0'); week_info_for_script = weeks_data.get(week_num_for_script)
            if week_info_for_script: week_title_for_script = week_info_for_script.get('title', week_title_for_script); lecture_date_for_script = week_info_for_script.get('date', lecture_date_for_script)
        base_output_filename = printable_scripts_output_dir / script_stem; print(f"\n  Processing lecture script: {script_stem} (Week {week_num_for_script})")
        try:
            template_context = {'lecture_script_content_md': script_md_content, 'lecture_title': f"Lecture: {week_title_for_script}", 'week_number': week_num_for_script, 'week_title': week_title_for_script, 'lecture_date': lecture_date_for_script, 'class_details': class_details, 'bibliography_path': bibliography_path, 'course': processed_data}
            intermediate_markdown = tm.render_template("lecture_scripts/printable_script.md.j2", template_context)
            pdf_filename = base_output_filename.with_suffix(".pdf"); print(f"    Generating PDF: {pdf_filename}")
            pdf_success = og.md_to_pdf(intermediate_markdown, pdf_filename, bibliography_path, csl_style_path)
            if pdf_success: print(f"    Successfully generated PDF: {pdf_filename}")
            else: print(f"    FAILED to generate PDF for {script_stem}")
            docx_filename = base_output_filename.with_suffix(".docx"); print(f"    Generating DOCX: {docx_filename}")
            docx_success = og.md_to_docx(intermediate_markdown, docx_filename, bibliography_path, csl_style_path)
            if docx_success: print(f"    Successfully generated DOCX: {docx_filename}")
            else: print(f"    FAILED to generate DOCX for {script_stem}")
        except Exception as e: 
            print(f"  Error processing lecture script {script_stem}: {e}")
            import traceback 
            traceback.print_exc()

def generate_tutorial_lesson_plans(config, processed_data, tm, og, target_weeks=None):
    print("\n>>> Task: Generating Tutorial Lesson Plans <<<")
    all_weeks_data = processed_data.get('weeks')
    if not all_weeks_data: print("  No weekly data found. Skipping."); return
    weeks_to_process = all_weeks_data
    if target_weeks:
        str_target_weeks = [str(w).strip() for w in target_weeks]
        weeks_to_process = [week for week in all_weeks_data if str(week.get('week_number')).strip() in str_target_weeks]
        if not weeks_to_process: print(f"  No weeks match target(s): {str_target_weeks}. Available: {[str(w.get('week_number')).strip() for w in all_weeks_data]}. Skipping."); return
        print(f"  Processing lesson plans for week(s): {', '.join(str_target_weeks)}")
    else: print("  Processing all lesson plans.")
    class_details = processed_data.get('class_details', {}); bibliography_path, csl_style_path = get_citation_paths(config, "tutorial lesson plans")
    output_dir_base_str = (config.get('paths') or {}).get('class_output')
    if not output_dir_base_str: print("  Error: 'paths.class_output' not configured. Cannot save."); return
    lesson_plans_output_dir = Path(output_dir_base_str) / "tutorial_lesson_plans"; lesson_plans_output_dir.mkdir(parents=True, exist_ok=True)
    for week_info in weeks_to_process:
        week_num = week_info.get('week_number', 'N/A'); week_title = week_info.get('title', f"Week {week_num}")
        base_output_filename = lesson_plans_output_dir / f"week_{str(week_num).zfill(2)}_lesson_plan"
        print(f"\n  Processing lesson plan for: Week {week_num} - {week_title}")
        try:
            template_context = {'week': week_info, 'class_details': class_details, 'bibliography_path': bibliography_path, 'course': processed_data}
            intermediate_markdown = tm.render_template("shared/tutorial_lesson_plan.md.j2", template_context)
            pdf_filename = base_output_filename.with_suffix(".pdf"); print(f"    Generating PDF: {pdf_filename}")
            pdf_success = og.md_to_pdf(intermediate_markdown, pdf_filename, bibliography_path, csl_style_path)
            if pdf_success: print(f"    Successfully generated PDF: {pdf_filename}")
            else: print(f"    FAILED to generate PDF for Week {week_num}")
            html_filename = base_output_filename.with_suffix(".html"); print(f"    Generating HTML: {html_filename}")
            html_success = og.md_to_html(intermediate_markdown, html_filename, bibliography_path, csl_style_path, standalone=True)
            if html_success: print(f"    Successfully generated HTML: {html_filename}")
            else: print(f"    FAILED to generate HTML for Week {week_num}")
        except Exception as e: 
            print(f"  Error processing lesson plan for Week {week_num} ('{week_title}'): {e}")
            import traceback 
            traceback.print_exc()

def generate_canvas_static_pages(config, processed_data, tm, og, canvas_api):
    print("\n>>> Task: Generating Canvas Static Pages <<<")
    structured_static_pages = processed_data.get('static_pages_structured')
    if not structured_static_pages:
        print("  No structured static pages data found. Skipping.")
        return

    canvas_course_id = (config.get('class_meta') or {}).get('canvas_course_id')
    if not canvas_course_id:
        print("  Error: Canvas Course ID not configured. Skipping.")
        return

    bibliography_path, csl_style_path = get_citation_paths(config, "Canvas static pages")
    class_output_path_str = (config.get('paths') or {}).get('class_output')

    print(f"  Processing {len(structured_static_pages)} static page(s) from structured data.")
    for page_slug, page_definition in structured_static_pages.items():
        try:
            raw_markdown_content = page_definition.get('markdown_content', '')
            page_title = page_definition.get('title', page_slug.replace('_', ' ').replace('-', ' ').title())
            print(f"\n  Processing Canvas Static Page: {page_title} (slug: {page_slug})")

            intermediate_markdown_for_pandoc = raw_markdown_content
            special_template_path = page_definition.get('template')

            # Determine the final markdown content, either from a template or raw
            if special_template_path:
                print(f"    Using special template: {special_template_path}")
                template_context = {
                    'course': processed_data,
                    'overview_prose_content': raw_markdown_content,
                    'page_title': page_title,
                    'class_details': processed_data.get('class_details', {})
                }
                intermediate_markdown_for_pandoc = tm.render_template(special_template_path, template_context)
            else:
                print(f"    No special template specified. Using raw Markdown content.")

            # --- NEW PRE-SCAN LOGIC ---
            # Check for citations and add the heading if needed.
            if bibliography_path and re.search(r'@[a-zA-Z0-9_:-]+', intermediate_markdown_for_pandoc):
                intermediate_markdown_for_pandoc += "\n\n## References"
                print("    Found citations, adding 'References' heading.")
            # --- END OF NEW LOGIC ---

            # Process the final markdown through Pandoc
            html_body_content = None
            if not class_output_path_str:
                print(f"    Error: 'paths.class_output' not configured for {page_title}. Cannot generate HTML.")
                continue

            html_output_dir = Path(class_output_path_str) / "canvas" / "static_pages"
            html_output_dir.mkdir(parents=True, exist_ok=True)
            html_filename = html_output_dir / f"{page_slug}.html"

            success_html = og.md_to_html(
                markdown_string=intermediate_markdown_for_pandoc,
                output_filename=html_filename,
                bibliography_path=bibliography_path,
                csl_path=csl_style_path,
                standalone=False
            )

            if not success_html:
                print(f"    Error converting Markdown to HTML for static page {page_title}. Skipping Canvas upload.")
                continue
            with open(html_filename, 'r', encoding='utf-8') as f:
                html_body_content = f.read()

            if not html_body_content:
                print(f"    No HTML content generated for {page_title}. Skipping upload.")
                continue

            # Upload to Canvas
            print(f"    Uploading to Canvas: {page_title} (slug: {page_slug})")
            canvas_page = canvas_api.create_or_update_page(
                course_id=canvas_course_id,
                title=page_title,
                body_html=html_body_content,
                page_url=page_slug,
                published=(config.get('canvas_content_defaults') or {}).get('publish_pages', False)
            )
            if canvas_page:
                print(f"    Successfully created/updated Canvas static page: {canvas_page.get('html_url', page_title)}")
            else:
                print(f"    Failed to create/update Canvas static page for {page_title}.")

        except Exception as e:
            print(f"  Error processing Canvas static page {page_slug}: {e}")
            import traceback
            traceback.print_exc()

def generate_dokuwiki_class_overview(config, processed_data, tm, og, dw_handler): # Renamed dw_handler parameter
    print("\n>>> Task: Generating DokuWiki Class Overview Page <<<")
    class_details = processed_data.get('class_details', {}) 
    dokuwiki_base_ns = (config.get('class_meta') or {}).get('dokuwiki_namespace', 'playground')
    if not dokuwiki_base_ns: print("  Error: DokuWiki Class Namespace not configured. Skipping task."); return
    
    overview_prose_md_key = (config.get('dokuwiki') or {}).get('overview_prose_slug_key', 'class_overview_content')
    overview_page_definition = (processed_data.get('static_pages_structured') or {}).get(overview_prose_md_key)
    
    overview_prose_md = ""
    if overview_page_definition and isinstance(overview_page_definition, dict):
        overview_prose_md = overview_page_definition.get('markdown_content', "''No specific overview prose content found.''")
    else:
        print(f"  Warning: Prose content for DokuWiki overview (slug_key: '{overview_prose_md_key}') not found in structured static pages.")
        overview_prose_md = "''Prose content for overview page is missing.''";

    bibliography_path, csl_style_path = get_citation_paths(config, "DokuWiki class overview")
    overview_pagename = (config.get('dokuwiki') or {}).get('overview_page_name', 'start')
    page_title_for_template = class_details.get('title') + " Class Overview" if class_details.get('title') else "Class Overview"

    print(f"\n  Processing DokuWiki Class Overview Page: {overview_pagename} in namespace {dokuwiki_base_ns}")
    try:
        template_context = {
            'course': processed_data, 'overview_prose_md': overview_prose_md, 
            'page_title': page_title_for_template, 
        }
        intermediate_markdown_content = tm.render_template("dokuwiki/class_overview.md.j2", template_context)
        print(f"    Intermediate Markdown for DokuWiki overview generated from template.")

        final_content_for_dokuwiki_page = og.md_to_dokuwiki_syntax(intermediate_markdown_content, bibliography_path, csl_style_path)
        if final_content_for_dokuwiki_page is None: print(f"    Error converting overview Markdown to DokuWiki syntax. Skipping save."); return

        success = dw_handler.save_page(pagename=overview_pagename, content=final_content_for_dokuwiki_page, namespace=dokuwiki_base_ns) # Used dw_handler
        if success: print(f"    Successfully saved DokuWiki Class Overview page: {dokuwiki_base_ns}:{overview_pagename}")
        else: print(f"    Failed to save DokuWiki Class Overview page: {dokuwiki_base_ns}:{overview_pagename}")
    except Exception as e:
        print(f"  Error processing DokuWiki Class Overview page: {e}")
        import traceback 
        traceback.print_exc()

def generate_canvas_assignments(config, processed_data, tm, og, canvas_api):
    print("\n>>> Task: Generating Canvas Assignments <<<")
    assignments_data = processed_data.get('assignments')
    if not assignments_data:
        print("  No assignments data found in processed_data. Skipping task.")
        return

    canvas_course_id = (config.get('class_meta') or {}).get('canvas_course_id')
    if not canvas_course_id:
        print("  Error: Canvas Course ID not configured. Skipping task.")
        return

    # Get bibliography and output paths once before the loop
    bibliography_path, csl_style_path = get_citation_paths(config, "Canvas assignments")
    class_output_path_str = (config.get('paths') or {}).get('class_output')

    print(f"  Processing {len(assignments_data)} assignment(s).")

    for assign_info in assignments_data:
        assign_title = assign_info.get('title', 'Untitled Assignment')
        assign_slug = assign_title.lower().replace(' ', '_').replace('/', '_')
        assign_slug = "".join(c for c in assign_slug if c.isalnum() or c in ['-', '_'])[:50]
        if not assign_slug: assign_slug = "assignment_" + str(assign_info.get("id", "unknown"))

        print(f"\n  Processing Canvas Assignment: {assign_title}")

        try:
            # 1. Render the initial Markdown from the template
            template_context = {
                'assignment': assign_info,
                'course': processed_data,
                'class_details': processed_data.get('class_details', {}),
            }
            description_markdown = tm.render_template("canvas/assignment_description.md.j2", template_context)

            # 2. Pre-scan for citations and add heading if necessary
            if bibliography_path and re.search(r'@[a-zA-Z0-9_:-]+', description_markdown):
                description_markdown += "\n\n## References"
                print("    Found citations, adding 'References' heading.")

            # 3. Process Markdown through Pandoc to get final HTML
            description_html = None
            if class_output_path_str:
                html_output_dir = Path(class_output_path_str) / "canvas" / "assignments"
                html_output_dir.mkdir(parents=True, exist_ok=True)
                html_filename = html_output_dir / f"{assign_slug}_description.html"

                success_html = og.md_to_html(
                    markdown_string=description_markdown,
                    output_filename=html_filename,
                    bibliography_path=bibliography_path,
                    csl_path=csl_style_path,
                    standalone=False
                )

                if not success_html:
                    print(f"    Error converting description to HTML for '{assign_title}'. Skipping.")
                    continue
                with open(html_filename, 'r', encoding='utf-8') as f:
                    description_html = f.read()
            else:
                print(f"    Error: 'paths.class_output' not configured. Skipping.")
                continue

            if not description_html:
                print(f"    Error: No HTML description generated for '{assign_title}'. Skipping.")
                continue

            # 4. Handle due dates and other API parameters
            due_at_iso = None
            raw_due_date = assign_info.get('due')
            if raw_due_date:
                try:
                    parsed_date = dateparser.parse(str(raw_due_date))
                    if parsed_date:
                        due_at_iso = parsed_date.isoformat()
                except (ValueError, TypeError):
                    pass

            submission_types_str = assign_info.get('submission_types', 'online_text_entry')
            submission_types_list = [s.strip() for s in str(submission_types_str).split(',') if s.strip()] or ['none']

            points_str = assign_info.get('points')
            points_possible = None
            if points_str is not None:
                try: points_possible = float(points_str)
                except ValueError: pass

            # 5. Call the Canvas API with the processed HTML
            canvas_assignment = canvas_api.create_assignment(
                name=assign_title,
                description_html=description_html,
                points_possible=points_possible,
                due_at=due_at_iso,
                submission_types=submission_types_list,
                published=(config.get('canvas_content_defaults') or {}).get('publish_assignments', False),
                course_id=canvas_course_id
            )

            if canvas_assignment:
                print(f"    Successfully created Canvas assignment: {canvas_assignment.get('name')}")
            else:
                print(f"    Failed to create Canvas assignment for '{assign_title}'.")

        except Exception as e:
            print(f"  Error processing Canvas assignment '{assign_title}': {e}")
            import traceback
            traceback.print_exc()


def generate_wiki_assignments(config, processed_data, tm):
    print("\n>>> Task: Generating Wiki Assignment Pages <<<")

    assignments_data = processed_data.get('assignments', [])
    if not assignments_data:
        print("  No assignment data found. Skipping task.")
        return

    output_dir_base_str = (config.get('paths') or {}).get('class_output')
    wiki_output_dir = Path(output_dir_base_str) / "wiki" / "assignments"
    wiki_output_dir.mkdir(parents=True, exist_ok=True)

    for assign_info in assignments_data:
        assign_title = assign_info.get('title', 'Untitled Assignment')
        print(f"  Processing assignment: {assign_title}...")

        # Create a URL-friendly slug for the filename
        slug = assign_title.lower().replace(' ', '-').replace('/', '_')
        slug = "".join(c for c in slug if c.isalnum() or c in ['-', '_'])

        template_context = {'assignment': assign_info, 'course': processed_data}
        rendered_content = tm.render_template("wiki/assignment_page.md.j2", template_context)

        output_filename = wiki_output_dir / f"{slug}.md"
        output_filename.write_text(rendered_content, encoding='utf-8')
        print(f"    Successfully created: {output_filename}")

            
def generate_dokuwiki_weekly_pages(config, processed_data, tm, og, dw_handler, target_weeks=None): # Renamed dw_handler parameter
    print("\n>>> Task: Generating DokuWiki Weekly Pages <<<")
    all_weeks_data = processed_data.get('weeks')
    if not all_weeks_data:
        print("  No weekly data found in processed_data. Skipping task.")
        return

    weeks_to_process = all_weeks_data
    if target_weeks:
        str_target_weeks = [str(w).strip() for w in target_weeks]
        weeks_to_process = [
            week for week in all_weeks_data 
            if str(week.get('week_number')).strip() in str_target_weeks
        ]
        if not weeks_to_process:
            available_week_numbers = [str(w.get('week_number')).strip() for w in all_weeks_data]
            print(f"  No weeks found matching the specified target week(s): {str_target_weeks}. "
                  f"Available weeks: {available_week_numbers}. Skipping task.")
            return
        print(f"  Processing DokuWiki weekly pages for week(s): {', '.join(str_target_weeks)}")
    else:
        print("  Processing all available DokuWiki weekly pages.")

    class_details = processed_data.get('class_details', {})
    dokuwiki_base_ns = (config.get('class_meta') or {}).get('dokuwiki_namespace', 'playground')
    bibliography_path, csl_style_path = get_citation_paths(config, "DokuWiki weekly pages")

    for week_info in weeks_to_process:
        week_num = week_info.get('week_number', 'N/A')
        week_title = week_info.get('title', f"Week {week_num}")
        dokuwiki_pagename = f"week_{str(week_num).zfill(2)}"
        
        print(f"\n  Processing DokuWiki Weekly Page: {dokuwiki_pagename} (Topic: {week_title})")

        try:
            template_context = {
                'week': week_info,
                'class_details': class_details,
                'course': processed_data, 
                'bibliography_path': bibliography_path
            }
            intermediate_markdown_content = tm.render_template("dokuwiki/weekly_page.md.j2", template_context)
            print(f"    Intermediate Markdown for DokuWiki page '{dokuwiki_pagename}' generated.")

            final_content_for_dokuwiki = og.md_to_dokuwiki_syntax(
                markdown_string=intermediate_markdown_content,
                bibliography_path=bibliography_path,
                csl_path=csl_style_path
            )

            if final_content_for_dokuwiki is None:
                print(f"    Error converting Markdown to DokuWiki syntax for {dokuwiki_pagename}. Skipping save.")
                continue
            
            weekly_pages_ns = f"{dokuwiki_base_ns}:weekly"

            success = dw_handler.save_page( # Used dw_handler
                pagename=dokuwiki_pagename,
                content=final_content_for_dokuwiki, 
                namespace=weekly_pages_ns 
            )
            if success:
                print(f"    Successfully saved DokuWiki Weekly Page: {weekly_pages_ns}:{dokuwiki_pagename}")
            else:
                print(f"    Failed to save DokuWiki Weekly Page: {weekly_pages_ns}:{dokuwiki_pagename}")

        except Exception as e:
            print(f"  Error processing DokuWiki Weekly Page for week {week_num} ('{week_title}'): {e}")
            import traceback
            traceback.print_exc()

# --- New Task: Generate DOCX Syllabus ---
def generate_syllabus_docx(config, processed_data, tm, og):
    print("\n>>> Task: Generating DOCX Syllabus <<<")

    class_details = processed_data.get('class_details', {})
    bibliography_path, csl_style_path = get_citation_paths(config, "DOCX syllabus")
    
    # Optional: Get specific prose for the syllabus if it's stored as a static page
    # This key 'syllabus_prose_content' should match a slug defined for a static page
    # in your class_config.yaml -> input_sources.static_pages
    syllabus_prose_slug_key = (config.get('syllabus_settings') or {}).get('prose_slug_key', 'syllabus_main_text')
    syllabus_prose_definition = (processed_data.get('static_pages_structured') or {}).get(syllabus_prose_slug_key)
    
    syllabus_prose_content_md = ""
    if syllabus_prose_definition and isinstance(syllabus_prose_definition, dict):
        syllabus_prose_content_md = syllabus_prose_definition.get('markdown_content', 
                                                                "''Syllabus prose content not found.''")
    else:
        print(f"  Info: Prose content for syllabus (slug_key: '{syllabus_prose_slug_key}') not found in structured static pages. Syllabus will be generated without it.")


    output_dir_base_str = (config.get('paths') or {}).get('class_output')
    if not output_dir_base_str:
        print("  Error: 'paths.class_output' not configured. Cannot save DOCX syllabus.")
        return
    
    syllabus_output_dir = Path(output_dir_base_str) / "syllabus_documents"
    syllabus_output_dir.mkdir(parents=True, exist_ok=True)
    
    # Define filename for the DOCX syllabus
    course_title_slug = class_details.get('title', 'course').lower().replace(' ', '_')
    course_title_slug = "".join(c for c in course_title_slug if c.isalnum() or c == '_')[:30]
    docx_filename = syllabus_output_dir / f"{course_title_slug}_syllabus.docx"

    print(f"\n  Processing DOCX Syllabus: {docx_filename}")

    try:
        template_context = {
            'datetime': datetime,
            'course': processed_data, # Full context for the template
            'class_details': class_details, # Convenience
            'syllabus_prose_content': syllabus_prose_content_md, # Prose from MD file
            'bibliography_path': bibliography_path # For conditional "References" section
        }
        # Render the Jinja2 template to get a complete Markdown document for the syllabus
        intermediate_markdown = tm.render_template("syllabus/syllabus_template.md.j2", template_context)
        print(f"    Intermediate Markdown for DOCX syllabus generated.")

        # Optional: Path to a reference.docx for styling
        reference_docx_path = (config.get('pandoc') or {}).get('reference_docx_syllabus') 
        if reference_docx_path and not Path(reference_docx_path).exists():
            print(f"    Warning: Syllabus reference DOCX '{reference_docx_path}' not found. Using Pandoc defaults.")
            reference_docx_path = None


        # Convert the intermediate Markdown to DOCX
        success_docx = og.md_to_docx(
            markdown_string=intermediate_markdown,
            output_filename=docx_filename,
            bibliography_path=bibliography_path,
            csl_path=csl_style_path,
            reference_docx=reference_docx_path
        )

        if success_docx:
            print(f"    Successfully generated DOCX Syllabus: {docx_filename}")
        else:
            print(f"    FAILED to generate DOCX Syllabus for {class_details.get('title', 'the course')}")

    except Exception as e:
        print(f"  Error processing DOCX syllabus: {e}")
        import traceback
        traceback.print_exc()



def generate_wiki_weekly_pages(config, processed_data, tm, og, target_weeks=None):
    print("\n>>> Task: Generating Wiki Weekly Pages <<<")
    
    # 1. Get the data to process
    all_weeks_data = processed_data.get('weeks', [])
    if not all_weeks_data:
        print("  No weekly data found. Skipping task.")
        return

    # (Optional) Filter for specific weeks if --week argument is used
    weeks_to_process = all_weeks_data
    if target_weeks:
        str_target_weeks = [str(w).strip() for w in target_weeks]
        weeks_to_process = [w for w in all_weeks_data if str(w.get('week_number')).strip() in str_target_weeks]

    # 2. Define the output directory
    output_dir_base_str = (config.get('paths') or {}).get('class_output')
    wiki_output_dir = Path(output_dir_base_str) / "wiki" / "weekly"
    wiki_output_dir.mkdir(parents=True, exist_ok=True)

    # 3. Loop through data, render template, and save file
    for week_info in weeks_to_process:
        week_num = str(week_info.get('week_number', 'N_A')).zfill(2)
        print(f"  Processing wiki page for week {week_num}...")
        
        template_context = {'week': week_info, 'course': processed_data}
        rendered_content = tm.render_template("wiki/weekly_page.md.j2", template_context)

        # --- TEMPORARY PANDOC CHECK ---
        print("  Running Pandoc to check for bibliography warnings...")
        bibliography_path, csl_style_path = get_citation_paths(config, "Wiki weekly pages")
        dummy_html_path = wiki_output_dir / f"week_{week_num}_citation_check.html"

        # This call will trigger Pandoc and show citeproc warnings
        og.md_to_html(
            markdown_string=rendered_content,
            output_filename=dummy_html_path,
            bibliography_path=bibliography_path,
            csl_path=csl_style_path
        )
        # --- END OF CHECK ---
        
        output_filename = wiki_output_dir / f"{week_num}.text"
        
        try:
            output_filename.write_text(rendered_content, encoding='utf-8')
            print(f"    Successfully created: {output_filename}")
        except Exception as e:
            print(f"    Error writing file for week {week_num}: {e}")
        

def generate_wiki_overview(config, processed_data, tm):
    print("\n>>> Task: Generating Wiki Overview Page <<<")

    # Get the specific prose content for the overview
    overview_prose_slug_key = (config.get('dokuwiki') or {}).get('overview_prose_slug_key', 'class_overview_content')
    overview_page_def = (processed_data.get('static_pages_structured') or {}).get(overview_prose_slug_key, {})
    overview_prose_md = overview_page_def.get('markdown_content', 'Overview content not found.')

    template_context = {
        'datetime': datetime,
        'course': processed_data, # Full context for the template
        #'class_details': class_details,
        'overview_prose_content': overview_prose_md, # Prose from MD file
    }
    rendered_content = tm.render_template("wiki/overview_page.md.j2", template_context)

    output_dir_base_str = (config.get('paths') or {}).get('class_output')
    wiki_output_dir = Path(output_dir_base_str) / "wiki"
    wiki_output_dir.mkdir(parents=True, exist_ok=True)
    
    output_filename = wiki_output_dir / "overview.text"
    output_filename.write_text(rendered_content, encoding='utf-8')
    print(f"  Successfully created: {output_filename}")

def generate_wiki_static_pages(config, processed_data, tm):
    print("\n>>> Task: Generating Wiki Static Pages <<<")

    static_pages = processed_data.get('static_pages_structured', {}).values()
    if not static_pages:
        print("  No static pages found. Skipping task.")
        return

    output_dir_base_str = (config.get('paths') or {}).get('class_output')
    wiki_output_dir = Path(output_dir_base_str) / "wiki" / "static"
    wiki_output_dir.mkdir(parents=True, exist_ok=True)

    for page_def in static_pages:
        page_slug = page_def.get('slug')
        print(f"  Processing static page: {page_slug}...")

        template_context = {'page': page_def, 'course': processed_data}
        rendered_content = tm.render_template("wiki/static_page.md.j2", template_context)

        output_filename = wiki_output_dir / f"{page_slug}.md"
        output_filename.write_text(rendered_content, encoding='utf-8')
        print(f"    Successfully created: {output_filename}")
            
# --- Main Function ---
def main():
    parser = argparse.ArgumentParser(description="Canversion, for plaintext enthusiasts who use Canvas. Yes, we Canversion.")
    parser.add_argument("class_id", help="Class ID (e.g., ANTH1001_S1_2024)")
    parser.add_argument("--tasks", nargs="+", choices=AVAILABLE_TASKS,
                        help=f"Specific tasks to run. Available: {', '.join(AVAILABLE_TASKS)}")
    parser.add_argument("--all-tasks", action="store_true", help="Run all available tasks.")
    parser.add_argument("--week", nargs="+", type=str,
                        help="Specify one or more week numbers to process for relevant tasks (e.g., 1 2 10).")

    args = parser.parse_args()

    print(f"--- Course Material Generator for Class: {args.class_id} ---")
    if args.week: print(f"Targeting specific week(s): {', '.join(args.week)}")

    print("\n[Phase 1/5] Loading configuration...")
    config = load_config(args.class_id)
    if not config: print(f"Error: Failed to load configuration for class '{args.class_id}'. Exiting."); sys.exit(1)

    MARKDOWN_EXTENSION = config.get('markdown_extension', '.text')
    
    # For 'create_skeletons', we only need config and some basic data, not the full processed_context
    if args.tasks and "create_skeletons" in args.tasks:
        if len(args.tasks) > 1:
            print("Warning: 'create_skeletons' task should be run by itself. It will run before any other specified tasks.")
        
        # Skeletons task only needs a subset of data to run
        print("\n[Phase 2/5 - Skeletons] Loading minimal data for skeleton creation...")
        minimal_loaded_data = {
            'csv_data_df': {
                'weekly_schedule': load_class_data(config).get('csv_data_df', {}).get('weekly_schedule'),
                'assignments': load_class_data(config).get('csv_data_df', {}).get('assignments')
            }
        }
        minimal_processed_context = DataProcessor(config).process_data(minimal_loaded_data)

        create_skeleton_files(config, minimal_processed_context)

        # Exit after creating skeletons to avoid running other tasks with incomplete input files
        print("\n--- Skeleton creation task completed. Please fill in the new files before running other tasks. ---")
        sys.exit(0)


    # --- Full Workflow for other tasks ---
    print("\n[Phase 2/5] Loading class data...")
    loaded_data = load_class_data(config)
    if not loaded_data: print(f"Warning: Failed to load some or all data for class '{args.class_id}'. Some tasks may fail or be incomplete.")

    print("\n[Phase 3/5] Processing data...")
    try:
        data_processor = DataProcessor(config)
        processed_context = data_processor.process_data(loaded_data)
    except Exception as e:
        print(f"Error during data processing: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n[Phase 4/5] Initializing services...")
    try:
        template_dir_path_str = (config.get('paths') or {}).get('templates')
        if not template_dir_path_str or not Path(template_dir_path_str).is_dir():
            print(f"Error: Templates directory path '{template_dir_path_str}' not found or not a directory."); sys.exit(1)
        template_manager = TemplateManager(template_dir=template_dir_path_str)
        output_generator = OutputGenerator(config=config)
        canvas_api = CanvasAPI(config=config)
        dokuwiki_handler = DokuWikiHandler(config=config)
    except Exception as e:
        print(f"Error initializing services: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n[Phase 5/5] Executing tasks...")
    tasks_to_run = []
    if args.all_tasks: tasks_to_run = AVAILABLE_TASKS
    elif args.tasks:
        tasks_to_run = [task for task in args.tasks if task in AVAILABLE_TASKS and task != "create_skeletons"] # Exclude skeletons from normal run
        if len(tasks_to_run) != len(args.tasks):
            unknown_tasks = [t for t in args.tasks if t not in tasks_to_run and t != "create_skeletons"]
            if unknown_tasks: print(f"Warning: Unknown tasks specified and will be ignored: {', '.join(unknown_tasks)}")
    
    if not tasks_to_run: print("No tasks specified or matched. Use --tasks or --all-tasks. Exiting."); sys.exit(0)
    print(f"Selected tasks to run: {', '.join(tasks_to_run)}")

    # (Task dispatch loop remains here, but 'create_skeletons' is handled separately above)
    for task_name in tasks_to_run:
        if task_name == "canvas_weekly_pages":
            generate_canvas_weekly_pages(config, processed_context, template_manager, output_generator, canvas_api, target_weeks=args.week)
        elif task_name == "dokuwiki_lecture_outlines": 
            generate_dokuwiki_lecture_outlines(config, processed_context, template_manager, output_generator, dokuwiki_handler, target_weeks=args.week)
        elif task_name == "lecture_scripts_printable":
            generate_lecture_scripts_printable(config, processed_context, template_manager, output_generator, target_weeks=args.week)
        elif task_name == "tutorial_lesson_plans": 
            generate_tutorial_lesson_plans(config, processed_context, template_manager, output_generator, target_weeks=args.week)
        elif task_name == "canvas_static_pages": 
            generate_canvas_static_pages(config, processed_context, template_manager, output_generator, canvas_api) 
        elif task_name == "dokuwiki_class_overview": 
            generate_dokuwiki_class_overview(config, processed_context, template_manager, output_generator, dokuwiki_handler) # Corrected parameter
        elif task_name == "canvas_assignments": 
            generate_canvas_assignments(config, processed_context, template_manager, output_generator, canvas_api)
        elif task_name == "dokuwiki_weekly_pages": 
            generate_dokuwiki_weekly_pages(config, processed_context, template_manager, output_generator, dokuwiki_handler, target_weeks=args.week) # Corrected parameter
        elif task_name == "generate_syllabus_docx":
             generate_syllabus_docx(config, processed_context, template_manager, output_generator)
        elif task_name == "wiki_weekly_pages":
            generate_wiki_weekly_pages(config, processed_context, template_manager, output_generator, target_weeks=args.week)
        elif task_name == "wiki_overview":
            generate_wiki_overview(config, processed_context, template_manager)        
        elif task_name == "wiki_assignments":
            generate_wiki_assignments(config, processed_context, template_manager)
        elif task_name == "wiki_static_pages":
            generate_wiki_static_pages(config, processed_context, template_manager)        
        else:
            print(f"Notice: Task '{task_name}' is defined but no implementation function is mapped in main.py.")
    
    print("\n--- All selected tasks completed. ---")

if __name__ == '__main__':
    main()
