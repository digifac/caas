"""Shared fixtures for all tests - imports from the new modular structure."""

# Imports of common fixtures (applied to all tests via autouse=True)
from .fixtures.common import (  # noqa: F401
    async_client,
    clean_caas_env,
    disable_rate_limiting,
    reset_task_manager,
    sample_scanned_pdf_bytes,
)

# Imports of fixtures by input format
from .fixtures.pdf import (  # noqa: F401
    sample_pdf_bytes,
    sample_pdf_with_link_bytes,
)

from .fixtures.docx import (  # noqa: F401
    sample_docx_bytes,
)

from .fixtures.html import (  # noqa: F401
    sample_html_bytes,
    sample_html_minimal_bytes,
    sample_html_latin1_bytes,
)

from .fixtures.xlsx import (  # noqa: F401
    sample_xlsx_bytes,
    sample_xlsx_multi_sheet_bytes,
    sample_xlsx_merged_cells_bytes,
    sample_xlsx_dates_numbers_bytes,
    sample_xlsx_special_chars_bytes,
    sample_xlsx_empty_sheet_bytes,
)

from .fixtures.pptx import (  # noqa: F401
    sample_pptx_bytes,
    sample_pptx_with_table_bytes,
    sample_pptx_empty_slide_bytes,
)

from .fixtures.ods import (  # noqa: F401
    sample_ods_bytes,
    sample_ods_multi_sheet_bytes,
    sample_ods_empty_sheet_bytes,
    sample_ods_special_chars_bytes,
)

from .fixtures.odt import (  # noqa: F401
    sample_odt_bytes,
    sample_odt_with_list_bytes,
    sample_odt_with_special_chars_bytes,
)

from .fixtures.odp import (  # noqa: F401
    sample_odp_bytes,
    sample_odp_multi_sheet_bytes,
    sample_odp_empty_slide_bytes,
    sample_odp_with_list_bytes,
    sample_odp_with_special_chars_bytes,
    sample_odp_with_groups_bytes,
)

# Imports of expected output fixtures (JSON and JSONL)
from .fixtures.expected_outputs import (  # noqa: F401
    expected_json_output_pdf,
    expected_jsonl_output_pdf,
    expected_json_output_docx,
    expected_jsonl_output_docx,
    expected_json_output_odt,
    expected_jsonl_output_odt,
    expected_json_output_xlsx,
    expected_jsonl_output_xlsx,
    expected_json_output_pptx,
    expected_jsonl_output_pptx,
    expected_json_output_html,
    expected_jsonl_output_html,
    expected_json_output_ods,
    expected_jsonl_output_ods,
    expected_json_output_odp,
    expected_jsonl_output_odp,
)
