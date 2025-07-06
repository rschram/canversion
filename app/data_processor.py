# app/data_processor.py
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional

class DataProcessor:
    def __init__(self, config: Dict[str, Any]):
        """
        Initializes the DataProcessor with application configuration.
        """
        self.config = config

    def _get_markdown_content(self, md_data_category: Dict[str, str], base_filename: str) -> Optional[str]:
        """
        Safely retrieves markdown content by base filename (without extension).
        Compares case-insensitively.
        """
        normalized_base_filename = base_filename.lower()
        for key, content in md_data_category.items():
            if key.lower() == normalized_base_filename:
                return content
        return None

    def process_data(self, loaded_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes the raw loaded data into a structured context for templating.
        """
        processed_context = {}

        # --- Process Class Details ---
        class_info = loaded_data.get('yaml_data', {}).get('class_info', {})
        processed_context['class_details'] = {
            **class_info, 
            'department_code': self.config.get('class_meta', {}).get('department_code'),
            'unit_code': self.config.get('class_meta', {}).get('unit_code'),
            'semester': self.config.get('class_meta', {}).get('semester'),
            'year': self.config.get('class_meta', {}).get('year'),
            'title': self.config.get('class_meta', {}).get('title', class_info.get('title')),
            'description': self.config.get('class_meta', {}).get('description', class_info.get('description')),
            'teaching_staff': self.config.get('teaching_staff', {}),
            'user_details': self.config.get('user_details', {}),
            'canvas_course_id': self.config.get('class_meta',{}).get('canvas_course_id'),
            'dokuwiki_namespace': self.config.get('class_meta',{}).get('dokuwiki_namespace')
        }
        processed_context['bibliography_data'] = loaded_data.get('yaml_data', {}).get('bibliography', [])

        # --- Process Weekly Data ---
        weekly_schedule_df = loaded_data.get('csv_data_df', {}).get('weekly_schedule')
        processed_weeks = []
        detail_csv_keys = ['keywords', 'learning_outcomes', 'brain_candy', 'discussion_questions', 'other_readings']

        if weekly_schedule_df is not None and not weekly_schedule_df.empty:
            week_col_names = ['week_number', 'Week', 'week', 'Week Number']
            week_identifier_col = None
            available_cols_normalized = {str(col).strip().lower(): str(col) for col in weekly_schedule_df.columns}
            for target_name in week_col_names:
                if target_name.lower() in available_cols_normalized:
                    week_identifier_col = available_cols_normalized[target_name.lower()]
                    break
            
            current_weekly_df = weekly_schedule_df.copy()

            if not week_identifier_col:
                print("Warning: Could not find a 'week_number' or similar column in weekly_schedule.csv. Advanced weekly processing will be limited.")
                merged_weekly_df = current_weekly_df
                for key in detail_csv_keys:
                    if key not in merged_weekly_df.columns:
                        merged_weekly_df[key] = [[] for _ in range(len(merged_weekly_df))]
            else:
                if week_identifier_col != 'week_number':
                     current_weekly_df = current_weekly_df.rename(columns={week_identifier_col: 'week_number'})
                current_weekly_df['week_number'] = current_weekly_df['week_number'].astype(str).str.strip()

                weekly_data_dfs_map = {
                    'keywords': loaded_data.get('csv_data_df', {}).get('weekly_keywords'),
                    'learning_outcomes': loaded_data.get('csv_data_df', {}).get('weekly_outcomes'),
                    'brain_candy': loaded_data.get('csv_data_df', {}).get('weekly_brain_candy'),
                    'discussion_questions': loaded_data.get('csv_data_df', {}).get('weekly_discussion_questions')
                }
                
                aggregated_weekly_data = {}
                for key, df_detail in weekly_data_dfs_map.items():
                    if df_detail is not None and not df_detail.empty:
                        current_week_id_col_detail = None
                        available_detail_cols_normalized = {str(col).strip().lower(): str(col) for col in df_detail.columns}
                        for target_name in week_col_names:
                            if target_name.lower() in available_detail_cols_normalized:
                                current_week_id_col_detail = available_detail_cols_normalized[target_name.lower()]
                                break
                        
                        if not current_week_id_col_detail:
                            print(f"Warning: No week identifier column found in '{key}' CSV. Skipping merge for this data.")
                            continue
                        
                        temp_df_detail = df_detail.copy()
                        if current_week_id_col_detail != 'week_number':
                             temp_df_detail = temp_df_detail.rename(columns={current_week_id_col_detail: 'week_number'})
                        temp_df_detail['week_number'] = temp_df_detail['week_number'].astype(str).str.strip()
                        
                        value_col = None
                        potential_value_cols = [c for c in temp_df_detail.columns if c.lower() != 'week_number']
                        if potential_value_cols: value_col = potential_value_cols[0]
                        
                        if value_col:
                            aggregated_df = temp_df_detail.groupby('week_number')[value_col].apply(list).reset_index(name=key)
                            aggregated_weekly_data[key] = aggregated_df
                        else: print(f"Warning: Could not determine value column for '{key}' CSV. Skipping aggregation.")
                
                merged_weekly_df = current_weekly_df
                for key, agg_df in aggregated_weekly_data.items():
                    merged_weekly_df = pd.merge(merged_weekly_df, agg_df, on='week_number', how='left')
                
                for key in detail_csv_keys:
                    if key not in merged_weekly_df.columns:
                        merged_weekly_df[key] = [[] for _ in range(len(merged_weekly_df))]
                    else:
                        merged_weekly_df[key] = merged_weekly_df[key].apply(
                            lambda x: x if isinstance(x, list) else ([] if pd.isna(x) else [x])
                        )
            
            for _, week_row in merged_weekly_df.iterrows():
                week_data = week_row.to_dict()
                week_num_str = str(week_data.get('week_number', '')).zfill(2)
                topic_md_filename_stems = [ f"{week_data.get('week_number','')}",
                    f"week_{week_num_str}", f"week_{week_data.get('week_number','')}",
                    f"week{week_data.get('week_number','')}", f"topic_week_{week_data.get('week_number','')}"
                ]
                week_data['topic_summary_md'] = None
                weekly_topics_md = loaded_data.get('markdown_data', {}).get('topics', {})
                for stem_candidate in topic_md_filename_stems:
                    summary = self._get_markdown_content(weekly_topics_md, stem_candidate) 
                    if summary: week_data['topic_summary_md'] = summary; break
                if not week_data['topic_summary_md']:
                    print(f"Warning: No topic summary Markdown found for week {week_data.get('week_number')}")
                processed_weeks.append(week_data)
        
        elif weekly_schedule_df is not None:
            print("Info: weekly_schedule.csv is empty. No weekly data to process.")
        else: 
            print("Warning: weekly_schedule.csv not loaded. No weekly data to process.")
        processed_context['weeks'] = processed_weeks

        # --- Process Assignments ---
        assignments_df = loaded_data.get('csv_data_df', {}).get('assignments')
        processed_assignments = []
        if assignments_df is not None and not assignments_df.empty:
            assignment_instructions_md_map = loaded_data.get('markdown_data', {}).get('assignment_instructions', {})
            for _, assign_row in assignments_df.iterrows():
                assignment_data = assign_row.to_dict()
                instructions_file_stem = None
                raw_instr_file = assignment_data.get('instructions-file')
                if isinstance(raw_instr_file, str) and raw_instr_file.strip():
                    instructions_file_stem = Path(raw_instr_file.strip()).stem
                
                assignment_data['instructions_md'] = None
                if instructions_file_stem:
                    assignment_data['instructions_md'] = self._get_markdown_content(
                        assignment_instructions_md_map, instructions_file_stem
                    )
                if not assignment_data['instructions_md'] and instructions_file_stem:
                     print(f"Warning: No instructions Markdown found for assignment (file stem: {instructions_file_stem})")
                processed_assignments.append(assignment_data)
        processed_context['assignments'] = processed_assignments

        # --- Process Static Pages (New Structure) ---
        # 'static_pages_content' from data_loader is a list of dicts.
        # We'll transform it into a dictionary keyed by slug for easier access in main.py.
        # Each value will be the full page definition dict (slug, title, template, markdown_content).
        
        structured_static_pages = {}
        raw_static_pages_list = loaded_data.get('static_pages_content', [])
        for page_def_item in raw_static_pages_list:
            if isinstance(page_def_item, dict) and 'slug' in page_def_item:
                slug = page_def_item['slug']
                # Ensure title exists, deriving from slug if necessary
                if 'title' not in page_def_item or not page_def_item['title']:
                    page_def_item['title'] = slug.replace('_', ' ').replace('-', ' ').title()
                
                structured_static_pages[slug] = page_def_item
            else:
                print(f"Warning: Invalid static page item found in loaded_data: {page_def_item}")
        
        processed_context['static_pages_structured'] = structured_static_pages
        if structured_static_pages:
             print(f"Processed {len(structured_static_pages)} static pages into structured format.")


        # --- Process other Markdown collections (Lecture Outlines, Scripts) ---
        # These are already dictionaries of {stem: content} from data_loader, so just pass them through.
        processed_context['lecture_outlines'] = loaded_data.get('markdown_data', {}).get('lecture_outlines', {})
        processed_context['lecture_scripts'] = loaded_data.get('markdown_data', {}).get('lecture_scripts', {})

        return processed_context

if __name__ == '__main__':
    # Test block for DataProcessor
    print("Testing DataProcessor with new static page structure...")

    # Minimal config for testing
    test_config_dp = {
        'class_meta': {'title': "DP Test Course"},
        'paths': {'class_input': 'dummy_input'} # Not actually used if loaded_data is mocked
    }
    processor = DataProcessor(config=test_config_dp)

    # Mock loaded_data, especially the new 'static_pages_content' structure
    mock_loaded_data = {
        'yaml_data': {'class_info': {'name': 'Test Class Info'}},
        'csv_data_df': {}, # Keep other parts minimal for this specific test
        'markdown_data': {},
        'static_pages_content': [ # This is what data_loader now provides
            {
                'slug': 'syllabus', 
                'title': 'Course Syllabus (from config)', 
                'source_file': 'prose/syllabus.md', 
                'template': 'canvas/syllabus_dynamic_page.md.j2', 
                'markdown_content': '# Syllabus Content\nMain text here.'
            },
            {
                'slug': 'contact_info', 
                # 'title': None, # Test title derivation
                'source_file': 'prose/contact.md', 
                'template': None, # Test no template
                'markdown_content': 'Email us at test@example.com'
            }
        ]
    }

    processed_context = processor.process_data(mock_loaded_data)

    print("\n--- Processed Static Pages (Structured) ---")
    static_pages_output = processed_context.get('static_pages_structured')
    if static_pages_output:
        for slug, page_data in static_pages_output.items():
            print(f"  Slug: {slug}")
            print(f"    Title: {page_data.get('title')}")
            print(f"    Template: {page_data.get('template')}")
            print(f"    MD Preview: '{page_data.get('markdown_content', '')[:30]}...'")
        
        # Assertions for test
        assert 'syllabus' in static_pages_output
        assert static_pages_output['syllabus']['title'] == 'Course Syllabus (from config)'
        assert 'contact_info' in static_pages_output
        assert static_pages_output['contact_info']['title'] == 'Contact Info' # Derived
        assert static_pages_output['contact_info']['template'] is None

    else:
        print("  No structured static pages found in processed_context.")
    
    print("\nDataProcessor test for static pages completed.")

